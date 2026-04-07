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
    kolom_standar = ['Tanggal', 'Tipe', 'Kategori', 'Nama_Barang', 'Harga_Satuan', 'Qty', 'Total_Harga', 'Catatan']
    df_baru = df_baru[kolom_standar]
    if not os.path.exists(NAMA_FILE):
        df_baru.to_csv(NAMA_FILE, index=False)
    else:
        df_baru.to_csv(NAMA_FILE, mode='a', header=False, index=False)

# --- FUNGSI AI HYBRID (PINTAR & ADAPTIF) ---
def analisa_dokumen_dengan_gemini(gambar):
    with st.spinner("AI sedang mengenali dokumen..."):
        try:
            instruksi = """
            Tolong analisa gambar ini. Ini bisa berupa NOTA BELANJA atau BUKTI TRANSFER/QRIS.
            
            ATURAN EKSTRAKSI:
            1. Jika ini NOTA BELANJA (ada daftar barang): Ekstrak setiap barang yang dibeli (Nama Barang, Harga Satuan, dan Qty).
            2. Jika ini BUKTI TRANSFER / QRIS: Ekstrak Nama Penerima/Toko (sebagai Nama_Barang) dan TOTAL NOMINAL (sebagai Harga_Satuan) dengan Qty 1.
            
            Keluarkan hasil HANYA dalam format JSON Array mentah:
            [{"Nama_Barang": "Contoh", "Harga_Satuan": 1000, "Qty": 1}]
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
            hasil_teks = response.text.replace('```json', '').replace('```', '').strip()
            
            data = json.loads(hasil_teks)
            # Pastikan setiap item punya kolom Catatan kosong agar tidak error saat edit tabel
            for item in data:
                if "Catatan" not in item:
                    item["Catatan"] = ""
            return data
        except Exception as e: 
            st.error(f"Terjadi kendala: {str(e)}")
            return None

# --- TAMPILAN UTAMA ---
st.title("Monitor Keuangan v4.2 🚀")

total_masuk, total_keluar, saldo = hitung_ringkasan()
c1, c2, c3 = st.columns(3)
c1.metric("Total Uang Masuk", f"Rp {total_masuk:,}")
c2.metric("Total Uang Keluar", f"Rp {total_keluar:,}")
c3.metric("Saldo Akhir", f"Rp {saldo:,}")
st.markdown("---")

# --- AREA BACKUP ---
col_down, col_up = st.columns(2)
with col_down:
    if os.path.exists(NAMA_FILE):
        df_dl = pd.read_csv(NAMA_FILE)
        csv = df_dl.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Backup", data=csv, file_name=f"backup_{date.today()}.csv", use_container_width=True)
    else:
        st.download_button("📥 Download Backup (Kosong)", data="", disabled=True, use_container_width=True)
with col_up:
    file_up = st.file_uploader("Upload Backup", type=['csv'], label_visibility="collapsed")
    if file_up:
        pd.read_csv(file_up).to_csv(NAMA_FILE, index=False)
        st.rerun()

st.markdown("---")

# --- INPUT TRANSAKSI ---
metode = st.radio("Metode Pencatatan:", ["✍️ Manual", "📸 Scan AI"], horizontal=True)

if metode == "✍️ Manual":
    col1, col2 = st.columns(2)
    with col1:
        tgl = st.date_input("Tanggal", date.today())
        tipe = st.radio("Tipe", ["Uang Keluar", "Uang Masuk"], horizontal=True)
        opsi_kat = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe == "Uang Masuk" else ["Makan", "Transport", "Belanja", "Tagihan", "Transfer Keluar", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
    with col2:
        nama = st.text_input("Nama/Subjek")
        harga = st.number_input("Harga/Nominal", min_value=0, step=1000)
        qty = 1 if tipe == "Uang Masuk" else st.number_input("Qty", min_value=1, step=1)
    
    catatan_man = st.text_input("Catatan Tambahan (Opsional)")
    
    if st.button("💾 Simpan Manual"):
        if nama and harga > 0:
            df = pd.DataFrame({"Tanggal": [tgl], "Tipe": [tipe], "Kategori": [kat], "Nama_Barang": [nama], "Harga_Satuan": [harga], "Qty": [qty], "Total_Harga": [harga * qty], "Catatan": [catatan_man]})
            simpan_data_batch(df)
            st.rerun()

else:
    upload = st.file_uploader("Upload Nota / Bukti Transfer", type=['jpg', 'jpeg', 'png'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("🔍 Jalankan AI"):
            hasil = analisa_dokumen_dengan_gemini(img)
            if hasil: st.session_state['scan_v4'] = hasil
        
        if 'scan_v4' in st.session_state:
            col_t, col_k = st.columns(2)
            with col_t:
                tipe_s = st.radio("Tipe:", ["Uang Keluar", "Uang Masuk"], horizontal=True)
            with col_k:
                opsi_s = ["Gaji", "Transfer Masuk", "Lain-lain"] if tipe_s == "Uang Masuk" else ["Belanja", "Makan", "Transfer Keluar", "Tagihan", "Lain-lain"]
                kat_s = st.selectbox("Kategori:", opsi_s)
            
            df_s = pd.DataFrame(st.session_state['scan_v4'])
            # Pastikan kolom Total_Harga dihitung di tabel editor
            if 'Harga_Satuan' in df_s.columns and 'Qty' in df_s.columns:
                df_s['Total_Harga'] = df_s['Harga_Satuan'] * df_s['Qty']
            
            edited = st.data_editor(df_s, num_rows="dynamic", hide_index=True, use_container_width=True)
            
            if st.button("💾 Simpan Hasil Scan"):
                edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                edited.insert(0, 'Kategori', kat_s)
                edited.insert(0, 'Tipe', tipe_s)
                edited.insert(0, 'Tanggal', date.today())
                simpan_data_batch(edited)
                st.session_state.pop('scan_v4', None)
                st.rerun()

# --- TAMPILAN TAB BULAN ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    df_all = pd.read_csv(NAMA_FILE)
    df_all['Tanggal'] = pd.to_datetime(df_all['Tanggal'])
    df_all['Bulan'] = df_all['Tanggal'].dt.strftime('%B %Y')
    bulans = df_all['Bulan'].unique()
    
    if len(bulans) > 0:
        st.subheader("Buku Kas Bulanan")
        tabs = st.tabs(list(bulans))
        for i, tab in enumerate(tabs):
            with tab:
                df_f = df_all[df_all['Bulan'] == bulans[i]].drop(columns=['Bulan'])
                df_f['Tanggal'] = df_f['Tanggal'].dt.strftime('%Y-%m-%d')
                st.dataframe(df_f, use_container_width=True)
