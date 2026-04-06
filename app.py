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
    if not os.path.exists(NAMA_FILE):
        df_baru.to_csv(NAMA_FILE, index=False)
    else:
        df_baru.to_csv(NAMA_FILE, mode='a', header=False, index=False)

def analisa_dokumen_dengan_gemini(gambar):
    try:
        # INSTRUKSI AI YANG LEBIH LUAS (Bisa baca Nota & Bukti Transfer)
        instruksi = """
        Tolong analisa gambar ini (bisa berupa nota belanja atau bukti transfer bank).
        Ekstrak informasi pentingnya ke dalam format JSON Array.
        1. Jika NOTA: Ambil daftar barang, harga satuan, dan qty.
        2. Jika BUKTI TRANSFER: Ambil nominal total, nama pengirim/penerima sebagai 'Nama_Barang', dan tambahkan catatan di 'Keterangan'.
        
        Format yang diminta harus persis seperti ini:
        [
          {"Nama_Barang": "Nama Item / Nama Pengirim", "Harga_Satuan": 1000, "Qty": 1, "Total_Harga": 1000, "Keterangan": "Catatan tambahan jika ada"}
        ]
        Hanya berikan JSON mentah saja.
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=[instruksi, gambar])
        return json.loads(response.text.replace('```json', '').replace('```', '').strip())
    except: return []

# --- TAMPILAN UTAMA ---
st.title("Monitor Keuangan v2.5 📊")

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
        opsi_kat = ["Gaji", "Pendapatan Ojol", "Lain-lain"] if tipe == "Uang Masuk" else ["Makan", "Transport", "Belanja", "Tagihan", "Lain-lain"]
        kat = st.selectbox("Kategori", opsi_kat)
    with col2:
        nama = st.text_input("Nama/Keterangan")
        if tipe == "Uang Masuk":
            harga, qty = st.number_input("Nominal", min_value=0, step=1000), 1
        else:
            harga = st.number_input("Harga Satuan", min_value=0, step=1000)
            qty = st.number_input("Qty", min_value=1, step=1)
    if st.button("💾 Simpan Manual"):
        if nama and harga > 0:
            df = pd.DataFrame({"Tanggal": [tgl], "Tipe": [tipe], "Kategori": [kat], "Nama_Barang": [nama], "Harga_Satuan": [harga], "Qty": [qty], "Total_Harga": [harga * qty]})
            simpan_data_batch(df)
            st.rerun()

else:
    # --- SCAN AI YANG DIPERBARUI ---
    upload = st.file_uploader("Upload Nota / Bukti Transfer", type=['jpg', 'jpeg', 'png'])
    if upload:
        img = Image.open(upload)
        st.image(img, width=250)
        if st.button("🔍 Analisa Dokumen"):
            st.session_state['scan_pro'] = analisa_dokumen_dengan_gemini(img)
        
        if 'scan_pro' in st.session_state:
            st.markdown("### Hasil Analisa AI")
            col_t, col_k = st.columns(2)
            with col_t:
                tipe_scan = st.radio("Tentukan Tipe Transaksi:", ["Uang Keluar", "Uang Masuk"], horizontal=True)
            with col_k:
                kat_scan = st.selectbox("Kategori Hasil Scan:", ["Belanja", "Gaji", "Transfer Masuk", "Makan", "Lain-lain"])
            
            # Tabel yang bisa diedit termasuk kolom Keterangan
            df_scan = pd.DataFrame(st.session_state['scan_pro'])
            edited = st.data_editor(df_scan, num_rows="dynamic", hide_index=True, use_container_width=True)
            
            if st.button("💾 Simpan Hasil Scan"):
                edited['Total_Harga'] = edited['Harga_Satuan'] * edited['Qty']
                edited.insert(0, 'Kategori', kat_scan)
                edited.insert(0, 'Tipe', tipe_scan)
                edited.insert(0, 'Tanggal', date.today())
                simpan_data_batch(edited)
                st.session_state.pop('scan_pro', None)
                st.success("Berhasil disimpan!")
                st.rerun()

# --- RIWAYAT ---
if os.path.exists(NAMA_FILE):
    st.markdown("---")
    st.subheader("10 Transaksi Terakhir")
    st.dataframe(pd.read_csv(NAMA_FILE).tail(10), use_container_width=True)
