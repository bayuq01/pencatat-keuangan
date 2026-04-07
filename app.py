import streamlit as st
import pandas as pd
import os
from datetime import date
from PIL import Image
from google import genai
import json

# ==========================================
# 1. PENGATURAN API GEMINI 
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = "PASTE_API_KEY_KAMU_DI_SINI" 

client = genai.Client(api_key=API_KEY)
NAMA_FILE = "catatan_detail_keuangan.csv"

st.set_page_config(page_title="Monitor Keuanganku Pro", layout="wide")

# --- FUNGSI DATA ---
def hitung_ringkasan():
    if os.path.exists(NAMA_FILE):
        df = pd.read_csv(NAMA_FILE)
        if 'Tipe' in df.columns and 'Total_Harga' in df.columns:
            masuk = df[df['Tipe'] == 'Uang Masuk']['Total_Harga'].sum()
            keluar = df[df['Tipe'] == 'Uang Keluar']['Total_Harga'].sum()
            return masuk, keluar, masuk - keluar
    return 0, 0, 0

def simpan_data_batch(df_baru):
    # Pastikan urutan 8 kolom selalu konsisten
    kolom_standar = ['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan']
    df_baru = df_baru[kolom_standar] # Mengatur ulang urutan kolom
    
    if not os.path.exists(NAMA_FILE):
        df_baru.to_csv(NAMA_FILE, index=False)
    else:
        df_baru.to_csv(NAMA_FILE, mode='a', header=False, index=False)

# --- FUNGSI AI TERBARU (DENGAN DEBUGER) ---
def analisa_dokumen_dengan_gemini(gambar):
    # Beri tahu pengguna di layar kalau proses sedang berjalan
    with st.spinner("AI sedang membaca nota... mohon tunggu..."):
        try:
            # PROMPT LEBIH TEGAS: Fokus ambil Total Akhir
            instruksi = """
            Tolong analisa gambar ini (nota belanja/bukti transfer/QRIS).
            Aturan:
            1. Temukan nama penerima/nama toko (Masukkan ke 'Nama_Barang').
            2. Temukan TOTAL NOMINAL AKHIR (Grand Total) yang harus dibayar (Masukkan ke 'Harga_Satuan'). Jangan ambil harga per item.
            
            Keluarkan HANYA dalam format JSON Array mentah seperti contoh ini:
            [{"Nama_Barang": "Nama Toko / Pengirim", "Harga_Satuan": 50000}]
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
            hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
            
            # 1. CEK HASIL KOSONG
            if not hasil_teks:
                st.error("Gagal analisa: AI tidak mengembalikan teks sama sekali. Mungkin API Google sedang down atau gambar tidak jelas.")
                return None

            # 2. TAMPILKAN HASIL MENTAH UNTUK DEBUGGING (PENTING!)
            st.write("**Debugging: Teks Mentah dari AI:**")
            st.code(hasil_teks, language='json')
            
            # 3. ATTEMPT PARSING JSON
            try:
                data = json.loads(hasil_teks)
            except json.JSONDecodeError:
                st.error("Gagal analisa: AI mengembalikan teks yang bukan format JSON. Mungkin AI-nya sedang bingung membaca dokumen.")
                return None
            
            # Otomatis menambahkan Qty=1 dan Catatan kosong
            for item in data:
                item["Qty"] = 1
                item["Catatan"] = ""
                
            return data
        except Exception as e: 
            # Menangkap error asli dari API call
            st.error(f"Gagal analisa: Terjadi kesalahan teknis saat menghubungi AI. Error: {str(e)}")
            return None

# --- TAMPILAN UTAMA (DASHBOARD) ---
st.title("Monitor Keuangan v4.1 Debugger 📊")

total_masuk, total_keluar, saldo = hitung_ringkasan()
c1, c2, c3 = st.columns(3)
c1.metric("Total Uang Masuk", f"Rp {total_masuk:,}")
c2.metric("Total Uang Keluar", f"Rp {total_keluar:,}")
c3.metric("Saldo Akhir", f"Rp {saldo:,}")
st.markdown("---")

# --- AREA BACKUP CLEAN ---
col_down, col_up = st.columns(2)
with col_down:
    if os.path.exists(NAMA_FILE):
        df_download = pd.read_csv(NAMA_FILE)
        csv_data = df_download.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Backup", data=csv_data, file_name=f"backup_keuangan_{date.today()}.csv", mime='text/csv', use_container_width=True)
    else:
        st.download_button("📥 Download Backup (Data Kosong)", data="", disabled=True, use_container_width=True)

with col_up:
    file_backup = st.file_uploader("Upload Backup", type=['csv'], label_visibility="collapsed")
    if file_backup is not None:
        pd.read_csv(file_backup).to_csv(NAMA_FILE, index=False)
        st.rerun()

st.markdown("---")

# --- AREA INPUT TRANSAKSI ---
metode = st.radio("Pilih Metode Pencatatan:", ["✍️ Input Manual", "📸 Scan Dokumen/Transfer"], horizontal=True)

if metode == "✍️ Input Manual":
    st.markdown("#### 📝 Catat Manual")
    col1, col2 = st.columns(2)
    with col1:
        tgl = st.date_input("Tanggal Transaksi", date.today())
        tipe = st.radio("Tipe Transaksi", ["Uang Keluar", "Uang Masuk"], horizontal=True)
        opsi_kat = ["Gaji", "Pendapatan Ojol", "Transfer Masuk", "Lain-lain"] if tipe == "Uang Masuk" else ["Makan & Minum", "Transport/Bensin", "Belanja", "Bayar Tagihan", "Cicilan", "Transfer Keluar", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
        
    with col2:
        nama = st.text_input("Subjek (Nama Toko/Pengirim/Barang)")
        if tipe == "Uang Masuk":
            harga = st.number_input("Nominal (Rp)", min_value=0, step=1000)
            qty = 1 
        else:
            harga = st.number_input("Harga Satuan (Rp)", min_value=0, step=1000)
            qty = st.number_input("Jumlah (Qty)", min_value=1, step=1)
            
    catatan_manual = st.text_input("Catatan Tambahan (Opsional):", placeholder="Contoh: Bayar utang makan, beli 3 kopi untuk teman, dll.")
    
    if st.button("💾 Simpan Transaksi"):
        if nama and harga > 0:
            df = pd.DataFrame({
                "Tanggal": [tgl], "Tipe": [tipe], "Kategori": [kat],
                "Nama_Barang": [nama], "Harga_Satuan": [harga],
                "Qty": [qty], "Total_Harga": [harga * qty], "Catatan": [catatan_manual]
            })
            simpan_data_batch(df)
            st.rerun()

else:
    st.markdown("#### 🔍 Scan Otomatis AI")
    if API_KEY == "PASTE_API_KEY_KAMU_DI_SINI":
        st.error("⚠️ API Key belum terpasang!")
        st.stop()
        
    upload = st.file_uploader("Upload Foto Nota / Bukti Transfer / QRIS", type=['jpg', 'jpeg', 'png'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("🔍 Mulai Analisa AI"):
            # Panggil fungsi analisa baru yang punya debugar
            hasil = analisa_dokumen_dengan_gemini(img)
            
            # Cek apakah analisa sukses mengembalikan data
            if hasil is not None:
                st.session_state['scan'] = hasil
        
        if 'scan' in st.session_state:
            st.info("💡 Pilih Tipe & Kategori. Kamu bisa mengedit Nama, Harga, atau menambahkan Catatan langsung di dalam tabel bawah ini.")
            
            col_t, col_k = st.columns(2)
            with col_t:
                tipe_scan = st.radio("Tipe Transaksi Scan:", ["Uang Keluar", "Uang Masuk"], horizontal=True, key="tipe_scan")
            with col_k:
                opsi_kat_scan = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe_scan == "Uang Masuk" else ["Belanja", "Makan & Minum", "Transfer Keluar", "Tagihan", "Lain-lain"]
                kat_scan = st.selectbox("Kategori Scan:", opsi_kat_scan)
            
            df_scan = pd.DataFrame(st.session_state['scan'])
            # Tabel interaktif (bisa edit Catatan langsung di tabel)
            edited = st.data_editor(df_scan, num_rows="dynamic", hide_index=True, use_container_width=True)
            
            if st.button("💾 Simpan Hasil Scan"):
                try:
                    edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                    edited['Kategori'] = kat_scan
                    edited['Tipe'] = tipe_scan
                    edited['Tanggal'] = date.today()
                    
                    simpan_data_batch(edited)
                    st.session_state.pop('scan', None) 
                    st.rerun()
                except Exception as e:
                    st.error("Gagal menyimpan! Pastikan angka tidak kosong.")

# --- TAMPILAN DATA BAWAH ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    st.subheader("Buku Kas Bulanan 📅")
    df_tampil = pd.read_csv(NAMA_FILE)
    df_tampil['Tanggal'] = pd.to_datetime(df_tampil['Tanggal'])
    df_tampil['Bulan_Tahun'] = df_tampil['Tanggal'].dt.strftime('%B %Y')
    daftar_bulan = df_tampil['Bulan_Tahun'].unique()
    
    if len(daftar_bulan) > 0:
        tabs = st.tabs(list(daftar_bulan))
        for i, tab in enumerate(tabs):
            with tab:
                df_filter = df_tampil[df_tampil['Bulan_Tahun'] == daftar_bulan[i]]
                df_bersih = df_filter.drop(columns=['Bulan_Tahun'])
                df_bersih['Tanggal'] = df_bersih['Tanggal'].dt.strftime('%Y-%m-%d')
                st.dataframe(df_bersih, use_container_width=True)
