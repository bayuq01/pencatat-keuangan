import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date
from PIL import Image
from google import genai
import json

# ==========================================
# 1. KONFIGURASI API & KONEKSI
# ==========================================
st.set_page_config(page_title="Monitor Keuangan Pro v5.0", layout="wide")

# Ambil API Key Gemini dari Secrets
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except:
    st.error("⚠️ API Key Gemini tidak ditemukan di Secrets!")
    st.stop()

# Buat Koneksi ke Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Fungsi untuk mengambil data terbaru dari Sheets
def ambil_data():
    try:
        # Mengambil data dari sheet pertama (index 0)
        return conn.read(ttl="0") # ttl="0" artinya data selalu fresh, tidak nyangkut di cache
    except:
        # Jika sheet masih kosong, buat DataFrame baru dengan 8 kolom sesuai rancanganmu
        return pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan'])

# --- LOGIKA AI HYBRID ---
def analisa_ai(gambar):
    with st.spinner("AI sedang mengenali dokumen..."):
        try:
            instruksi = """
            Analisa gambar ini (Nota atau Bukti Transfer).
            1. Jika NOTA: Ekstrak tiap barang (Nama_Barang, Harga_Satuan, Qty).
            2. Jika TRANSFER/QRIS: Ekstrak Nama Toko/Penerima (Nama_Barang) dan Total (Harga_Satuan) dengan Qty 1.
            Keluarkan format JSON Array saja: [{"Nama_Barang": "X", "Harga_Satuan": 1000, "Qty": 1}]
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
            hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(hasil_teks)
        except Exception as e:
            st.error(f"AI gagal membaca: {e}")
            return None

# ==========================================
# 2. TAMPILAN DASHBOARD
# ==========================================
st.title("Monitor Keuangan Pro v5.0 ☁️")
st.caption("Data tersimpan otomatis di Google Sheets")

df_current = ambil_data()

# Pastikan kolom angka bertipe numerik agar bisa dijumlahkan
if not df_current.empty:
    df_current['Total_Harga'] = pd.to_numeric(df_current['Total_Harga'], errors='coerce').fillna(0)
    masuk = df_current[df_current['Tipe'] == 'Uang Masuk']['Total_Harga'].sum()
    keluar = df_current[df_current['Tipe'] == 'Uang Keluar']['Total_Harga'].sum()
else:
    masuk, keluar = 0, 0

c1, c2, c3 = st.columns(3)
c1.metric("Total Masuk", f"Rp {masuk:,.0f}")
c2.metric("Total Keluar", f"Rp {keluar:,.0f}")
c3.metric("Saldo", f"Rp {masuk - keluar:,.0f}")

st.markdown("---")

# ==========================================
# 3. INPUT DATA (MANUAL & AI)
# ==========================================
metode = st.radio("Metode Input:", ["✍️ Manual", "📸 Scan AI"], horizontal=True)

if metode == "✍️ Manual":
    col1, col2 = st.columns(2)
    with col1:
        tgl = st.date_input("Tanggal", date.today())
        tipe = st.radio("Tipe", ["Uang Keluar", "Uang Masuk"], horizontal=True)
        opsi_kat = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe == "Uang Masuk" else ["Makan", "Belanja", "Transport", "Tagihan", "Transfer Keluar", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
    with col2:
        nama = st.text_input("Nama Barang / Subjek")
        harga = st.number_input("Harga Satuan", min_value=0, step=1000)
        qty = 1 if tipe == "Uang Masuk" else st.number_input("Qty", min_value=1, step=1)
    
    catatan = st.text_area("Catatan Tambahan")
    
    if st.button("💾 Simpan ke Cloud"):
        if nama and harga > 0:
            data_baru = pd.DataFrame([{
                "Tanggal": str(tgl), "Tipe": tipe, "Kategori": kat, "Nama_Barang": nama,
                "Harga_Satuan": harga, "Qty": qty, "Total_Harga": harga * qty, "Catatan": catatan
            }])
            df_update = pd.concat([df_current, data_baru], ignore_index=True)
            conn.update(data=df_update)
            st.success("Berhasil disimpan ke Google Sheets!")
            st.rerun()

else:
    upload = st.file_uploader("Upload Foto Nota/Transfer", type=['jpg', 'png', 'jpeg'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("🔍 Jalankan AI"):
            st.session_state['scan_res'] = analisa_ai(img)
            
        if 'scan_res' in st.session_state:
            t_scan = st.radio("Tipe Scan:", ["Uang Keluar", "Uang Masuk"], horizontal=True)
            k_scan = st.selectbox("Kategori Scan:", ["Belanja", "Makan", "Transfer", "Lain-lain"])
            
            df_edit = pd.DataFrame(st.session_state['scan_res'])
            edited = st.data_editor(df_edit, num_rows="dynamic", hide_index=True)
            c_scan = st.text_input("Catatan untuk hasil scan ini:")
            
            if st.button("💾 Simpan Hasil Scan"):
                edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                edited['Tanggal'] = str(date.today())
                edited['Tipe'] = t_scan
                edited['Kategori'] = k_scan
                edited['Catatan'] = c_scan
                
                df_update = pd.concat([df_current, edited], ignore_index=True)
                conn.update(data=df_update)
                st.session_state.pop('scan_res')
                st.success("Data Scan berhasil masuk ke Google Sheets!")
                st.rerun()

# ==========================================
# 4. RIWAYAT TABS (BULANAN)
# ==========================================
if not df_current.empty:
    st.markdown("---")
    st.subheader("Riwayat Transaksi (Google Sheets) 📅")
    
    df_current['Tanggal'] = pd.to_datetime(df_current['Tanggal'], errors='coerce')
    df_current = df_current.dropna(subset=['Tanggal']) # Hapus baris yang tanggalnya rusak
    df_current['Bulan'] = df_current['Tanggal'].dt.strftime('%B %Y')
    bulans = df_current['Bulan'].unique()
    
    if len(bulans) > 0:
        tabs = st.tabs(list(bulans))
        for i, tab in enumerate(tabs):
            with tab:
                df_f = df_current[df_current['Bulan'] == bulans[i]].drop(columns=['Bulan'])
                df_f['Tanggal'] = df_f['Tanggal'].dt.strftime('%Y-%m-%d')
                st.dataframe(df_f, use_container_width=True, hide_index=True)

    if st.button("🗑️ Reset Semua Data (Hapus Sheet)"):
        # Cara reset paling aman: kirim DataFrame kosong ke Google Sheets
        df_reset = pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan'])
        conn.update(data=df_reset)
        st.warning("Data di Google Sheets telah dikosongkan.")
        st.rerun()
