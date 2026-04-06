import streamlit as st
import pandas as pd
import os
from datetime import date
from PIL import Image
from google import genai
import json

# ==========================================
# 1. PENGATURAN API GEMINI (VERSI HYBRID: LOKAL & CLOUD)
# ==========================================
try:
    # Ini akan jalan otomatis saat di-online-kan ke Streamlit Cloud
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # Ini akan jalan saat kamu ngetes di laptop (Lokal)
    API_KEY = "AIzaSyDzbfRVjMvOGv_745egmud_80rN4siNj58" 

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
    if not os.path.exists(NAMA_FILE):
        df_baru.to_csv(NAMA_FILE, index=False)
    else:
        df_baru.to_csv(NAMA_FILE, mode='a', header=False, index=False)

def analisa_nota_dengan_gemini(gambar):
    try:
        instruksi = "Analisa nota ini, ekstrak barang ke JSON: [{'Nama_Barang': 'X', 'Harga_Satuan': 0, 'Qty': 1, 'Total_Harga': 0}]"
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
        return json.loads(response.text.replace('```json', '').replace('```', '').strip())
    except: return []

# --- TAMPILAN UTAMA ---
st.title("Monitor Keuangan v2.0 📊")

total_masuk, total_keluar, saldo = hitung_ringkasan()
c1, c2, c3 = st.columns(3)
c1.metric("Total Uang Masuk", f"Rp {total_masuk:,}")
c2.metric("Total Uang Keluar", f"Rp {total_keluar:,}")
c3.metric("Saldo Akhir", f"Rp {saldo:,}")
st.markdown("---")

metode = st.radio("Pilih Metode Pencatatan:", ["✍️ Input Manual", "📸 Scan Nota AI"], horizontal=True)
st.markdown("---")

if metode == "✍️ Input Manual":
    st.subheader("Pencatatan Manual")
    col1, col2 = st.columns(2)
    with col1:
        tgl = st.date_input("Tanggal Transaksi", date.today())
        tipe = st.radio("Tipe Transaksi", ["Uang Keluar", "Uang Masuk"], horizontal=True)
        
        if tipe == "Uang Masuk":
            opsi_kat = ["Gaji", "Pendapatan Ojol", "Lain-lain"]
        else:
            opsi_kat = ["Makan & Minum", "Transport/Bensin", "Belanja", "Bayar Tagihan", "Cicilan", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
        
    with col2:
        nama = st.text_input("Keterangan/Nama Barang")
        
        if tipe == "Uang Masuk":
            harga = st.number_input("Nominal (Rp)", min_value=0, step=1000)
            qty = 1 
        else:
            harga = st.number_input("Harga Satuan (Rp)", min_value=0, step=1000)
            qty = st.number_input("Jumlah (Qty)", min_value=1, step=1)
    
    if st.button("💾 Simpan Transaksi"):
        if nama and harga > 0:
            df = pd.DataFrame({
                "Tanggal": [tgl], "Tipe": [tipe], "Kategori": [kat],
                "Nama_Barang": [nama], "Harga_Satuan": [harga],
                "Qty": [qty], "Total_Harga": [harga * qty]
            })
            simpan_data_batch(df)
            st.success(f"Data {tipe} berhasil disimpan!")
            st.rerun()
        else:
            st.error("Mohon isi keterangan dan nominalnya!")

else:
    st.subheader("Scan Nota dengan Gemini AI")
    if API_KEY == "PASTE_API_KEY_KAMU_DI_SINI":
        st.error("⚠️ Masukkan API Key di baris 14 kode Python-mu!")
        st.stop()
        
    upload = st.file_uploader("Upload Foto", type=['jpg', 'jpeg', 'png'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("Mulai Analisa AI"):
            hasil = analisa_nota_dengan_gemini(img)
            st.session_state['scan'] = hasil
        
        if 'scan' in st.session_state:
            df_scan = pd.DataFrame(st.session_state['scan'])
            edited = st.data_editor(df_scan, num_rows="dynamic", hide_index=True)
            if st.button("Simpan Hasil Scan"):
                edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                edited.insert(0, 'Kategori', "Belanja (Dari Nota)")
                edited.insert(0, 'Tipe', 'Uang Keluar')
                edited.insert(0, 'Tanggal', date.today())
                simpan_data_batch(edited)
                st.success("Nota Berhasil Dicatat!")
                st.session_state.pop('scan', None) # Bersihkan memori scan setelah disimpan
                st.rerun()

# --- AREA BACKUP DATA (FITUR PENYELAMAT) ---
st.markdown("---")
st.subheader("⚙️ Pengaturan & Backup Data")
col_down, col_up = st.columns(2)

if os.path.exists(NAMA_FILE):
    df_download = pd.read_csv(NAMA_FILE)
    csv_data = df_download.to_csv(index=False).encode('utf-8')
    
    with col_down:
        st.info("Download data ke HP/Laptop sebelum server reset.")
        st.download_button(
            label="📥 Download Backup CSV",
            data=csv_data,
            file_name=f"backup_keuangan_{date.today()}.csv",
            mime='text/csv',
        )

with col_up:
    st.info("Upload file CSV lama jika data hilang.")
    file_backup = st.file_uploader("📤 Restore dari Backup", type=['csv'], label_visibility="collapsed")
    if file_backup is not None:
        df_restored = pd.read_csv(file_backup)
        df_restored.to_csv(NAMA_FILE, index=False)
        st.success("Data berhasil dipulihkan! Refresh halaman ini.")
        if st.button("🔄 Refresh Data"):
            st.rerun()

# --- TAMPILAN DATA ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    st.subheader("Riwayat Transaksi Terakhir")
    st.dataframe(pd.read_csv(NAMA_FILE).tail(10), use_container_width=True)