# Panduan Instalasi dan Menjalankan Backend

## Prasyarat
- Python 3.8 atau versi lebih baru
- pip
- virtualenv (opsional, tapi direkomendasikan)

## Langkah Instalasi

### 1. Clone Repository
```bash
git clone [URL_REPOSITORY]
cd [FOLDER_NAME]
```

### 2. Buat Virtual Environment
```bash
# Untuk Windows
python -m venv venv

# Untuk macOS/Linux
python3 -m venv venv
```

### 3. Aktifkan Virtual Environment
```bash
# Untuk Windows
venv\Scripts\activate

# Untuk macOS/Linux
source venv/bin/activate
```

### 4. Install Requirement
```bash
pip install -r requirements.txt
```

### 5. Konfigurasi Environment (Opsional)
Salin file `.env.example` menjadi `.env` dan sesuaikan konfigurasi:
```bash
cp .env.example .env
```

### 6. Jalankan Aplikasi
```bash
# Untuk menjalankan server development
python app.py

# Atau menggunakan flask
flask run
```

## Penghentian Virtual Environment
Untuk keluar dari virtual environment:
```bash
deactivate
```

## Troubleshooting
- Pastikan Anda menggunakan versi Python yang kompatibel
- Periksa file `requirements.txt` untuk dependensi spesifik
- Pastikan semua environment variable sudah terkonfigurasi

## Catatan Tambahan
- Selalu gunakan virtual environment untuk mengisolasi dependensi project
- Update `requirements.txt` jika menambahkan library baru
