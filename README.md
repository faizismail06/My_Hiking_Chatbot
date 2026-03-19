# My Hiking Chatbot Backend

Backend chatbot menggunakan **Gemini API** dengan **RAG (Retrieval Augmented Generation)** untuk menjawab pertanyaan seputar pendakian gunung.

## Fitur

- 🤖 Chatbot berbasis Gemini AI
- 📊 RAG (Retrieval Augmented Generation) dari database MySQL
- 🏔️ Informasi gunung, jalur, dan tata tertib
- 🔒 Filter keamanan untuk data privasi

## Prasyarat

- Python 3.10 atau lebih baru
- MySQL Server (XAMPP/Laragon)
- Gemini API Key

## Instalasi

### 1. Buat Virtual Environment

```bash
# Windows
cd My_Hiking_Python
python -m venv venv
venv\Scripts\activate

# Linux/Mac
cd My_Hiking_Python
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment

Salin file `.env.example` ke `.env` dan isi dengan konfigurasi Anda:

```bash
copy .env.example .env
```

Edit file `.env`:

```env
# Gemini API Key (dapatkan di https://makersuite.google.com/app/apikey)
GEMINI_API_KEY=your_actual_gemini_api_key

# Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=myhiking
DB_USER=root
DB_PASSWORD=

# Server Configuration
FLASK_PORT=5000
FLASK_HOST=0.0.0.0
FLASK_DEBUG=True
```

### 4. Dapatkan Gemini API Key

1. Buka https://makersuite.google.com/app/apikey
2. Login dengan akun Google
3. Klik "Create API Key"
4. Copy API key dan paste ke file `.env`

## Menjalankan Server

```bash
# Pastikan virtual environment aktif
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Jalankan server
python app.py
```

Server akan berjalan di `http://localhost:5000`

## API Endpoints

### POST /api/chat

Mengirim pesan ke chatbot.

**Request Body:**
```json
{
    "message": "Apa saja gunung yang tersedia?",
    "history": []
}
```

**Response:**
```json
{
    "success": true,
    "message": "Berikut adalah gunung yang tersedia..."
}
```

### GET /api/chat/info

Mendapatkan informasi chatbot dan data yang tersedia.

### GET /api/health

Cek kesehatan server dan koneksi database.

## Struktur Folder

```
My_Hiking_Python/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── .env.example       # Example environment file
├── .gitignore         # Git ignore file
└── README.md          # Documentation
```

## Troubleshooting

### Error: ModuleNotFoundError
Pastikan virtual environment aktif dan dependencies terinstall:
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### Error: Gemini API Key not configured
Pastikan GEMINI_API_KEY sudah diisi di file `.env`

### Error: Database connection failed
1. Pastikan MySQL server berjalan (XAMPP/Laragon)
2. Pastikan database `myhiking` sudah ada
3. Cek konfigurasi DB_USER dan DB_PASSWORD di `.env`

## Keamanan

Chatbot dirancang untuk **tidak** memberikan informasi sensitif seperti:
- NIK pengguna
- Nomor telepon pribadi
- Alamat email
- Password
- Data transaksi individual

## Lisensi

© 2024 My Hiking Team
