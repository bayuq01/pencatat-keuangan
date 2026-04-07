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
            return (masuk, keluar, masuk - keluar)
    return (0, 0, 0)

def simpan_data_batch(df_baru):
    # Kolom standar 8 sesuai rancanganmu
    kolom_standar = ['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan']
    
    # Pastikan semua kolom ada, jika tidak ada isi dengan default
    for col in kolom_standar:
        if col not in df_baru.columns:
            df_baru[col] = "" if col == 'Catatan' or col == 'Nama_Barang' else 0
            
    df_baru = df_baru[kolom_standar]
    
    if not os.path.exists(NAMA_FILE):
        df_baru.to_csv(NAMA_FILE, index=False)
    else:
        df_baru.to_csv(NAMA_FILE, mode='a', header=False, index=False)

def analisa_dokumen_dengan_gemini(gambar):
    with st.spinner("AI sedang membaca dokumen..."):
        try:
            instruksi = """
            Analisa gambar ini (nota/transfer). 
            Ekstrak ke JSON:
            1. Nama pengirim/penerima/toko -> 'Nama_Barang'
            2. Harga Satuan -> 'Harga_Satuan'
            3. Jumlah -> 'Qty' (default 1 jika bukti transfer)
            
            Berikan format JSON Array saja:
            [{"Nama_Barang": "X", "Harga_Satuan": 1000, "Qty": 1}]
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
            hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(hasil_teks)
            return data
        except Exception as e: 
            st.error(f"Gagal baca AI: {str(e)}")
            return None

# --- DASHBOARD ---
st.title("Monitor Keuangan v4.3 🚀")
total_masuk, total_keluar, saldo = hitung_ringkasan()
c1, c2, c3 = st.columns(3)
c1.metric("Total Uang Masuk", f"Rp {total_masuk:,}")
c2.metric("Total Uang Keluar", f"Rp {total_keluar:,}")
c3.metric("Saldo Akhir", f"Rp {saldo:,}")
st.markdown("---")

# --- BACKUP ---
col_down, col_up = st.columns(2)
with col_down:
    if os.path.exists(NAMA_FILE):
        csv = pd.read_csv(NAMA_FILE).to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Backup", data=csv, file_name=f"backup_{date.today()}.csv", use_container_width=True)
with col_up:
    file_up = st.file_uploader("Upload Backup", type=['csv'], label_visibility="collapsed")
    if file_up:
        pd.read_csv(file_up).to_csv(NAMA_FILE, index=False)
        st.rerun()

st.markdown("---")

# --- INPUT ---
metode = st.radio("Metode Pencatatan:", ["✍️ Manual", "📸 Scan AI"], horizontal=True)

if metode == "✍️ Manual":
    col1, col2 = st.columns(2)
    with col1:
        tgl = st.date_input("Tanggal", date.today())
        tipe = st.radio("Tipe", ["Uang Keluar", "Uang Masuk"], horizontal=True)
        opsi_kat = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe == "Uang Masuk" else ["Makan", "Belanja", "Transport", "Tagihan", "Transfer Keluar", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
    with col2:
        nama = st.text_input("Subjek/Barang")
        harga = st.number_input("Harga/Nominal", min_value=0, step=1000)
        qty = 1 if tipe == "Uang Masuk" else st.number_input("Qty", min_value=1, step=1)
    
    # OPSI CATATAN MANUAL
    catatan_man = st.text_area("Catatan Detail (Opsional)", placeholder="Contoh: Bayar utang makan siang di warteg depan kantor.")
    
    if st.button("💾 Simpan Transaksi"):
        if nama and harga > 0:
            df = pd.DataFrame({"Tanggal": [tgl], "Tipe": [tipe], "Kategori": [kat], "Nama_Barang": [nama], "Harga_Satuan": [harga], "Qty": [qty], "Total_Harga": [harga * qty], "Catatan": [catatan_man]})
            simpan_data_batch(df)
            st.rerun()

else:
    upload = st.file_uploader("Upload Foto", type=['jpg', 'png', 'jpeg'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("🔍 Jalankan AI"):
            st.session_state['scan_v43'] = analisa_dokumen_dengan_gemini(img)
        
        if 'scan_v43' in st.session_state:
            c_tipe, c_kat = st.columns(2)
            with c_tipe: tipe_s = st.radio("Tipe:", ["Uang Keluar", "Uang Masuk"], horizontal=True)
            with c_kat: 
                opsi_s = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe_s == "Uang Masuk" else ["Belanja", "Makan", "Transfer Keluar", "Lain-lain"]
                kat_s = st.selectbox("Kategori:", opsi_s)
            
            df_s = pd.DataFrame(st.session_state['scan_v43'])
            # Tampilkan editor tabel
            edited = st.data_editor(df_s, num_rows="dynamic", hide_index=True, use_container_width=True)
            
            # OPSI CATATAN UNTUK HASIL SCAN
            catatan_scan = st.text_area("Tambahkan Catatan untuk Transaksi Ini:", placeholder="Misal: Uang patungan atau belanja bulanan rumah.")
            
            if st.button("💾 Simpan Hasil Scan"):
                edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                edited['Kategori'] = kat_s
                edited['Tipe'] = tipe_s
                edited['Tanggal'] = date.today()
                edited['Catatan'] = catatan_scan # Memasukkan catatan dari text area ke semua baris scan
                
                simpan_data_batch(edited)
                st.session_state.pop('scan_v43', None)
                st.rerun()

# --- RIWAYAT TABS ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    df_all = pd.read_csv(NAMA_FILE)
    df_all['Tanggal'] = pd.to_datetime(df_all['Tanggal'])
    df_all['Bulan'] = df_all['Tanggal'].dt.strftime('%B %Y')
    bulans = df_all['Bulan'].unique()
    
    if len(bulans) > 0:
        st.subheader("Riwayat Transaksi Bulanan 📅")
        tabs = st.tabs(list(bulans))
        for i, tab in enumerate(tabs):
            with tab:
                df_f = df_all[df_all['Bulan'] == bulans[i]].drop(columns=['Bulan'])
                df_f['Tanggal'] = df_f['Tanggal'].dt.strftime('%Y-%m-%d')
                st.dataframe(df_f, use_container_width=True)
