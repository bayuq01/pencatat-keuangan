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

def analisa_dokumen_dengan_gemini(gambar):
    try:
        # LOGIKA BARU: Sangat Sederhana
        instruksi = """
        Ekstrak info dari gambar ini (nota/bukti transfer/QRIS).
        Cari 2 hal saja:
        1. Nama pengirim / penerima / nama toko (Masukkan ke Nama_Barang)
        2. Total nominal uang (Masukkan ke Harga_Satuan)
        
        Keluarkan HANYA dalam format JSON Array ini:
        [{"Nama_Barang": "Nama Disini", "Harga_Satuan": 50000}]
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
        hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(hasil_teks)
        
        # Otomatis menambahkan Qty=1 dan Catatan kosong untuk disesuaikan pengguna
        for item in data:
            item["Qty"] = 1
            item["Catatan"] = ""
            
        if len(data) > 0 and "Harga_Satuan" in data[0]:
            return data
        else:
            return [{"Nama_Barang": "", "Harga_Satuan": 0, "Qty": 1, "Catatan": ""}]
    except: 
        return [{"Nama_Barang": "Gagal dibaca AI", "Harga_Satuan": 0, "Qty": 1, "Catatan": ""}]

# --- TAMPILAN UTAMA (DASHBOARD) ---
st.title("Monitor Keuangan v4.0 📊")

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
            hasil = analisa_dokumen_dengan_gemini(img)
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

# --- TAMPILAN DATA BAWAH (VISUAL TABS PER BULAN) ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    st.subheader("Buku Kas Bulanan 📅")
    df_tampil = pd.read_csv(NAMA_FILE)
    
    # Memastikan kolom Tanggal terbaca sebagai format Waktu
    df_tampil['Tanggal'] = pd.to_datetime(df_tampil['Tanggal'])
    
    # Membuat kolom baru khusus untuk nama Bulan & Tahun (Contoh: "April 2026")
    df_tampil['Bulan_Tahun'] = df_tampil['Tanggal'].dt.strftime('%B %Y')
    
    # Mengambil daftar bulan apa saja yang ada di catatan
    daftar_bulan = df_tampil['Bulan_Tahun'].unique()
    
    if len(daftar_bulan) > 0:
        # Membuat Tab (Visual Sheet) otomatis
        tabs = st.tabs(list(daftar_bulan))
        
        # Mengisi setiap Tab dengan data yang sesuai bulannya
        for i, tab in enumerate(tabs):
            with tab:
                df_filter = df_tampil[df_tampil['Bulan_Tahun'] == daftar_bulan[i]]
                # Sembunyikan kolom bantuan Bulan_Tahun agar rapi
                df_bersih = df_filter.drop(columns=['Bulan_Tahun'])
                # Mengubah format tanggal kembali ke tulisan rapi (YYYY-MM-DD)
                df_bersih['Tanggal'] = df_bersih['Tanggal'].dt.strftime('%Y-%m-%d')
                
                st.dataframe(df_bersih, use_container_width=True)
