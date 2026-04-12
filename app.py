import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import date
from PIL import Image
from google import genai
import json

# ==========================================
# 1. INITIAL SETUP
# ==========================================
st.set_page_config(page_title="Catatan Keuangan Pro", layout="wide")

# Mengambil API Key dari Secrets
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error("⚠️ API Key Gemini tidak ditemukan atau salah pasang di Secrets!")
    st.stop()

# Membuat koneksi ke Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def ambil_data_fresh():
    try:
        # Mengambil data dari sheet utama
        return conn.read(ttl="0")
    except:
        # Jika sheet kosong, buat kolom standar
        return pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan'])

# ==========================================
# 2. FUNGSI ANALISA AI
# ==========================================
def analisa_ai_dokumen(gambar):
    with st.spinner("AI sedang membaca nota..."):
        try:
            # Gunakan 1.5-flash agar jatah quota lebih banyak (Gratis & Stabil)
            MODEL_AI = 'gemini-1.5-flash'
            
            instruksi = """
            Analisa gambar nota/transfer ini. 
            Ambil data: Nama Barang/Toko, Harga Satuan, dan Qty.
            JIKA BUKTI TRANSFER: Nama Barang = Nama Penerima, Qty = 1.
            BERIKAN HASIL HANYA DALAM FORMAT JSON ARRAY:
            [{"Nama_Barang": "Contoh", "Harga_Satuan": 1000, "Qty": 1}]
            JANGAN ADA TEKS TAMBAHAN.
            """
            
            response = client.models.generate_content(model=MODEL_AI, contents=[instruksi, gambar])
            teks_hasil = response.text.strip()
            
            # Pembersihan format JSON
            if "```json" in teks_hasil:
                teks_hasil = teks_hasil.split("```json")[1].split("```")[0]
            elif "```" in teks_hasil:
                teks_hasil = teks_hasil.split("```")[1].split("```")[0]
            
            return json.loads(teks_hasil.strip())
        except Exception as e:
            if "429" in str(e):
                st.error("❌ Jatah harian AI habis (Quota Limit). Silakan coba lagi nanti atau besok.")
            else:
                st.error(f"❌ Terjadi kesalahan: {e}")
            return None

# ==========================================
# 3. TAMPILAN DASHBOARD
# ==========================================
st.title("Catatan Keuangan Digital ☁️")
st.caption("Data terhubung otomatis ke Google Sheets Anda")

df_db = ambil_data_fresh()

# Hitung Ringkasan
if not df_db.empty:
    df_db['Total_Harga'] = pd.to_numeric(df_db['Total_Harga'], errors='coerce').fillna(0)
    total_masuk = df_db[df_db['Tipe'] == 'Uang Masuk']['Total_Harga'].sum()
    total_keluar = df_db[df_db['Tipe'] == 'Uang Keluar']['Total_Harga'].sum()
else:
    total_masuk, total_keluar = 0, 0

m1, m2, m3 = st.columns(3)
m1.metric("Pemasukan", f"Rp {total_masuk:,.0f}")
m2.metric("Pengeluaran", f"Rp {total_keluar:,.0f}")
m3.metric("Saldo Akhir", f"Rp {total_masuk - total_keluar:,.0f}")

st.markdown("---")

# ==========================================
# 4. MENU INPUT
# ==========================================
pilihan = st.sidebar.selectbox("Pilih Menu:", ["➕ Input Data", "📁 Riwayat Transaksi", "⚙️ Pengaturan"])

if pilihan == "➕ Input Data":
    metode = st.radio("Metode:", ["✍️ Manual", "📸 Scan AI"], horizontal=True)
    
    if metode == "✍️ Manual":
        with st.form("form_manual"):
            c1, c2 = st.columns(2)
            with c1:
                tgl = st.date_input("Tanggal", date.today())
                tp = st.selectbox("Tipe", ["Uang Keluar", "Uang Masuk"])
                kat_opsi = ["Makan", "Belanja", "Transport", "Tagihan", "Transfer", "Lainnya"]
                kat = st.selectbox("Kategori", kat_opsi)
            with c2:
                nm = st.text_input("Nama Barang/Subjek")
                hrg = st.number_input("Harga Satuan", min_value=0, step=100)
                q = st.number_input("Jumlah (Qty)", min_value=1, step=1)
            
            ctt = st.text_area("Catatan Tambahan")
            btn_simpan = st.form_submit_button("Simpan ke Cloud")
            
            if btn_simpan:
                if nm and hrg > 0:
                    data_baru = pd.DataFrame([{
                        "Tanggal": str(tgl), "Tipe": tp, "Kategori": kat, "Nama_Barang": nm,
                        "Harga_Satuan": hrg, "Qty": q, "Total_Harga": hrg * q, "Catatan": ctt
                    }])
                    df_final = pd.concat([df_db, data_baru], ignore_index=True)
                    conn.update(data=df_final)
                    st.success("Data tersimpan!")
                    st.rerun()

    else:
        file_img = st.file_uploader("Upload Bukti", type=['jpg', 'png', 'jpeg'])
        if file_img:
            img_show = Image.open(file_img)
            st.image(img_show, width=300)
            if st.button("🔍 Proses dengan AI"):
                hasil_ai = analisa_ai_dokumen(img_show)
                if hasil_ai:
                    st.session_state['temp_scan'] = hasil_ai
            
            if 'temp_scan' in st.session_state:
                st.markdown("### Konfirmasi Data AI")
                tp_s = st.radio("Tipe:", ["Uang Keluar", "Uang Masuk"], key="tp_s")
                kat_s = st.selectbox("Kategori:", ["Makan", "Belanja", "Transfer", "Lainnya"], key="kat_s")
                
                df_scan = pd.DataFrame(st.session_state['temp_scan'])
                edited_df = st.data_editor(df_scan, num_rows="dynamic", hide_index=True)
                ctt_s = st.text_input("Catatan untuk semua item ini:")
                
                if st.button("✔️ Konfirmasi & Simpan"):
                    edited_df['Total_Harga'] = edited_df['Harga_Satuan'] * edited_df['Qty']
                    edited_df['Tanggal'] = str(date.today())
                    edited_df['Tipe'] = tp_s
                    edited_df['Kategori'] = kat_s
                    edited_df['Catatan'] = ctt_s
                    
                    df_final = pd.concat([df_db, edited_df], ignore_index=True)
                    conn.update(data=df_final)
                    st.session_state.pop('temp_scan')
                    st.success("Data scan berhasil masuk cloud!")
                    st.rerun()

elif pilihan == "📁 Riwayat Transaksi":
    if not df_db.empty:
        df_db['Tanggal'] = pd.to_datetime(df_db['Tanggal'], errors='coerce')
        df_db = df_db.dropna(subset=['Tanggal'])
        df_db['Bulan'] = df_db['Tanggal'].dt.strftime('%B %Y')
        list_bulan = df_db['Bulan'].unique()
        
        tabs = st.tabs(list(list_bulan))
        for i, tab in enumerate(tabs):
            with tab:
                df_filter = df_db[df_db['Bulan'] == list_bulan[i]].drop(columns=['Bulan'])
                df_filter['Tanggal'] = df_filter['Tanggal'].dt.strftime('%Y-%m-%d')
                st.dataframe(df_filter, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data transaksi.")

else:
    st.subheader("Pengaturan")
    if st.button("🗑️ Reset Semua Data di Google Sheets"):
        df_kosong = pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan'])
        conn.update(data=df_kosong)
        st.warning("Semua data di spreadsheet telah dihapus.")
        st.rerun()
