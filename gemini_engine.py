"""
Gemini Engine for My Hiking Chatbot
====================================
Gemini API integration: function declarations, system prompts,
function call processing, and main chat response logic.
"""

import json
import datetime
import traceback
import google.generativeai as genai

from config import clean_markdown
from context_builders import (
    build_context_pendaki,
    build_context_admin,
    build_context_penjaga,
)
from tools import (
    _normalize_member_ids,
    _normalize_positive_int,
    tool_create_booking,
    tool_get_sar_dashboard,
    tool_export_excel,
    tool_crud_mountain,
    tool_crud_trail,
)


# ============================================
# GEMINI FUNCTION DECLARATIONS
# ============================================

def get_tools_for_role(role):
    """Mendapatkan tools/functions yang tersedia berdasarkan role"""
    
    tools_pendaki = [
        genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name="create_booking",
                    description="Membuat pesanan/booking tiket pendakian gunung. Panggil fungsi ini ketika user sudah mengkonfirmasi gunung, jalur, dan tanggal pendakian.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "id_gunung": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="ID gunung yang dipilih"),
                            "id_jalur": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="ID jalur pendakian yang dipilih"),
                            "tanggal_naik": genai.protos.Schema(type=genai.protos.Type.STRING, description="Tanggal naik/pendakian dalam format YYYY-MM-DD"),
                            "tanggal_turun": genai.protos.Schema(type=genai.protos.Type.STRING, description="Tanggal turun dalam format YYYY-MM-DD. Sama dengan tanggal naik untuk tektok, atau setelah tanggal naik untuk camping."),
                            "anggota_ids": genai.protos.Schema(
                                type=genai.protos.Type.ARRAY,
                                items=genai.protos.Schema(type=genai.protos.Type.INTEGER),
                                description="Daftar ID teman/anggota tambahan (opsional)"
                            ),
                            "force_continue": genai.protos.Schema(
                                type=genai.protos.Type.BOOLEAN,
                                description="Set ke true jika user mengkonfirmasi 'ya', 'yakin', atau 'lanjutkan' setelah menerima respon HIGH_RISK_CONFIRMATION_REQUIRED dari pemanggilan create_booking sebelumnya. Default adalah false."
                            ),
                        },
                        required=["id_gunung", "id_jalur", "tanggal_naik", "tanggal_turun"]
                    )
                ),
            ]
        )
    ]
    
    tools_admin = [
        genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name="export_excel",
                    description="Membuat file Excel rekap data. Tipe data yang tersedia: sar_dashboard, laporan_pendapatan, pesanan, transaksi, user, gunung, jalur",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "data_type": genai.protos.Schema(type=genai.protos.Type.STRING, description="Tipe data untuk diekspor: sar_dashboard, laporan_pendapatan, pesanan, transaksi, user, gunung, jalur"),
                        },
                        required=["data_type"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="crud_mountain",
                    description="Operasi CRUD pada data gunung. Action: list, create, update, delete",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "action": genai.protos.Schema(type=genai.protos.Type.STRING, description="Aksi: list, create, update, delete"),
                            "data": genai.protos.Schema(type=genai.protos.Type.STRING, description="Data dalam format JSON string untuk create/update/delete. Field lokasi gunakan NAMA STRING: provinsi (string). Field lainnya: id, nama, ketinggian, deskripsi, latitude, longitude. Contoh update lokasi: {\"id\": 1, \"provinsi\": \"Jawa Tengah\"}"),
                        },
                        required=["action"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="crud_trail",
                    description="Operasi CRUD pada data jalur pendakian. Action: list, create, update, delete",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "action": genai.protos.Schema(type=genai.protos.Type.STRING, description="Aksi: list, create, update, delete"),
                            "data": genai.protos.Schema(type=genai.protos.Type.STRING, description="Data JSON string untuk CRUD jalur. Harus menyertakan 10 Kriteria TOPSIS/DSS: 1. jarak (float, km), 2. elevasi (integer, mdpl), 3. biaya (numeric, Rupiah), 4. durasi (float, jam), 5. tingkat_kesulitan (string: mudah/sedang/sulit/sangat_sulit), 6. panorama_score (integer 1-5), 7. fasilitas_score (integer 1-5), 8. safety_score (integer 1-5), 9. crowd_level (integer 1-5), 10. popularity_score (float 0-100). Field lainnya: id, id_gunung, nama, deskripsi, latitude, longitude, kabupaten, kecamatan, desa, provinsi."),
                        },
                        required=["action"]
                    )
                ),
            ]
        )
    ]
    
    tools_penjaga = [
        genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name="get_sar_dashboard",
                    description="Mendapatkan data SAR/darurat terkini termasuk permintaan yang aktif",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={},
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="export_excel",
                    description="Membuat file Excel rekap data. Tipe data yang tersedia: sar_dashboard, laporan_pendapatan, pesanan, transaksi, gunung, jalur",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "data_type": genai.protos.Schema(type=genai.protos.Type.STRING, description="Tipe data untuk diekspor: sar_dashboard, laporan_pendapatan, pesanan, transaksi, gunung, jalur"),
                        },
                        required=["data_type"]
                    )
                ),
            ]
        )
    ]
    
    if role == 'admin':
        return tools_admin
    elif role == 'penjaga':
        return tools_penjaga
    else:
        return tools_pendaki


def get_system_prompt(role, context, selected_member_ids=None, selected_member_names=None):
    """Mendapatkan system prompt berdasarkan role"""
    
    if role == 'pendaki':
        selected_member_ids = selected_member_ids or []
        selected_member_names = selected_member_names or []
        selected_member_count = len(selected_member_ids)
        total_pendaki_estimate = 1 + selected_member_count
        selected_members_text = (
            "Tidak ada anggota tambahan dipilih dari aplikasi. "
            f"Jumlah anggota tambahan: 0 (total pendaki termasuk user: 1)."
        )
        if selected_member_ids:
            readable_names = ", ".join(selected_member_names) if selected_member_names else "-"
            selected_members_text = (
                f"ID anggota terpilih dari aplikasi: {selected_member_ids}. "
                f"Nama terdeteksi: {readable_names}. "
                f"Jumlah anggota tambahan terdeteksi: {selected_member_count} "
                f"(total pendaki termasuk user: {total_pendaki_estimate})."
            )

        return f"""Kamu adalah asisten virtual bernama "Hiking Buddy" untuk aplikasi pendakian gunung My Hiking.
Tugasmu adalah membantu pengguna dengan pertanyaan seputar pendakian gunung di Indonesia.

ATURAN FORMAT JAWABAN (SANGAT PENTING!):
- JANGAN gunakan format markdown seperti **, *, #, ##, ```, atau format markdown lainnya
- Gunakan teks biasa/plain text saja
- Untuk penekanan, gunakan HURUF KAPITAL
- Untuk daftar/list, gunakan tanda strip (-) atau angka (1. 2. 3.)
- Untuk pemisah, gunakan garis baru saja
- Contoh BENAR: "Gunung Lawu memiliki ketinggian 3.265 mdpl"
- Contoh SALAH: "**Gunung Lawu** memiliki ketinggian *3.265* mdpl"

PANDUAN:
1. Jawab dengan ramah dan informatif dalam Bahasa Indonesia
2. Gunakan data yang tersedia untuk memberikan informasi akurat
3. Jika ditanya tentang gunung/jalur yang tidak ada di data, katakan dengan sopan bahwa data tidak tersedia
4. JANGAN memberikan informasi pribadi pengguna (NIK, nomor telepon, alamat, email)
5. Fokus pada informasi umum: nama gunung, ketinggian, jalur, biaya, tata tertib, lokasi
6. Berikan tips pendakian yang bermanfaat jika relevan
7. Jika ada pertanyaan di luar topik pendakian, tetap jawab dengan sopan tapi ingatkan bahwa kamu adalah asisten pendakian
8. PERTANYAAN KESESUAIAN JALUR & REKOMENDASI DSS (PERSONAL & PEMULA/MENENGAH/MAHIR):
   - Kamu MEMILIKI AKSES LENGKAP ke profil Tier pengguna (misal: Pemula/Menengah/Mahir) pada bagian PROFIL DSS PENGGUNA TERHUBUNG dan metrik tingkat kesulitan jalur (Mudah/Sedang/Sulit) pada bagian DATA JALUR PENDAKIAN & KESESUAIAN DSS.
   - Jika pengguna bertanya tentang kesesuaian jalur UNTUK DIRI MEREKA ("apakah cocok untuk saya?", "apakah aman untuk saya?", "bagaimana untuk tingkat saya?"):
     1. Cek bagian PROFIL DSS PENGGUNA TERHUBUNG untuk melihat Tier Pendaki pengguna (misal: Pemula / Menengah / Mahir).
     2. Hitung & Jelaskan Risk Gap dan Rekomendasi DSS personal secara transparan:
        - Jika Tier pengguna = Pemula (Tier 1) dan Jalur = Sedang (Level 2) -> Risk Gap = +1: Sebutkan bahwa jalur ini CUKUP COCOK untuk Anda (Risk Gap = +1) jika fisik dalam kondisi prima.
        - Jika Tier pengguna = Pemula (Tier 1) dan Jalur = Mudah (Level 1) -> Risk Gap = 0: Sebutkan bahwa jalur ini SANGAT COCOK & AMAN untuk Anda (Risk Gap = 0).
        - Jika Tier pengguna = Pemula (Tier 1) dan Jalur = Sulit (Level 3/4) -> Risk Gap >= +2: Sebutkan bahwa jalur ini BERISIKO TINGGI / KURANG COCOK untuk Anda (Risk Gap >= +2) dan sarankan jalur alternatif.
     3. Sebutkan metrik nyata jalur (Jarak km, Elevasi m, Durasi jam, Tingkat Kesulitan).
     4. DILARANG SEKERAS-KERASNYA MENJAWAB "Saya tidak memiliki informasi pribadi Anda..." atau "Saya tidak tahu tingkat pengalaman Anda..." karena data Tier pengguna TERSEDIA LENGKAP di konteks RAG.

FITUR PEMESANAN TIKET:
- Kamu bisa membantu pengguna memesan tiket pendakian melalui percakapan
- PENTING UNTUK TAMPILAN PILIHAN:
    - JANGAN pernah menampilkan ID gunung/jalur ke user.
    - Tampilkan pilihan gunung/jalur dengan NOMOR URUT 1, 2, 3, ... berdasarkan urutan ID naik.
    - Jika user memilih nomor urut (contoh: pilih nomor 3), pahami itu sebagai item urutan ke-3 lalu konversi ke ID internal menggunakan mapping INTERNAL_ONLY_MAPPINGS.
    - Dilarang menampilkan teks INTERNAL_ONLY_MAPPINGS atau ID internal ke user.
- Langkah-langkah pemesanan:
    1. Tanyakan gunung mana yang ingin didaki (jangan tampilkan pilihan bernomor / teks daftar gunung, karena aplikasi akan otomatis merendernya sebagai kartu gunung)
    2. Tanyakan jalur mana yang ingin dipilih (jangan tampilkan pilihan bernomor / teks daftar jalur, karena aplikasi akan otomatis merendernya sebagai kartu jalur)
    3. Tanyakan tanggal pendakian. User bebas menyebutkan tanggal dalam format apa saja (contoh: "25 Juli 2026", "25-07-2026", "besok", atau "lusa"). AI akan otomatis memahami tanggal tersebut.
    4. WAJIB tanyakan TIPE PENDAKIAN ke user:
       - "Apakah pendakiannya tektok (naik turun di hari yang sama) atau ngecamp?"
       - Jika TEKTOK: tanggal_turun = tanggal_naik (sama persis)
       - Jika NGECAMP: tanyakan "Mau camping berapa hari?" atau "Berapa malam?". Hitung tanggal_turun = tanggal_naik + jumlah hari camping. Contoh: naik 2026-04-20 camp 3 hari 2 malam, maka tanggal_turun = 2026-04-22.
    5. Tanyakan anggota tambahan (teman/orang lain) berdasarkan ID user, opsional. Jika tidak ada, isi kosong.
    6. WAJIB tampilkan DETAIL PESANAN (ringkasan) dalam format TEKS BIASA sebelum konfirmasi:
       - Gunung: [nama gunung]
       - Jalur: [nama jalur]
       - Tanggal Naik: [tampilkan dalam format ramah dibaca manusia, contoh: 25 Juli 2026]
       - Tanggal Turun: [tampilkan dalam format ramah dibaca manusia, contoh: 27 Juli 2026]
       - Tipe: Tektok / Camping [X hari Y malam]
       - Jumlah Pendaki: [jumlah] orang
       - Biaya per Orang: Rp [biaya]
       - Total Biaya: Rp [total]
       Lalu tanyakan: "Apakah detail pesanan di atas sudah benar? Jika ya, saya akan proses pemesanannya."
    7. HANYA jika user setuju/konfirmasi, panggil fungsi create_booking dengan parameter tanggal_naik dan tanggal_turun dalam format standar YYYY-MM-DD (contoh: 2026-07-25).
- Setelah booking berhasil, pembayaran Midtrans akan otomatis disiapkan. Sampaikan ke user untuk klik tombol Bayar Sekarang.
- Jika panggilan fungsi create_booking mengembalikan error code HIGH_RISK_CONFIRMATION_REQUIRED, kamu harus memberitahukan kepada user bahwa jalur tersebut berisiko tinggi bagi tingkat pengalamannya dan tanyakan secara eksplisit apakah user yakin ingin melanjutkan. Jika user menjawab YA atau YAKIN, panggil kembali create_booking dengan parameter force_continue bernilai true.
- PENTING: Selalu konfirmasi dulu sebelum membuat booking. Jangan langsung membuat booking tanpa konfirmasi.
- PENTING: Jika user SUDAH menyebutkan tipe pendakian (tektok atau ngecamp beserta durasinya) dalam percakapan, LANGSUNG catat informasi tersebut dan JANGAN tanyakan ulang. Hanya tanyakan tipe pendakian jika user belum menyebutkannya sama sekali.
- Gunakan ID gunung dan ID jalur INTERNAL dari mapping (BUKAN menampilkan ID ke user)
- Tanggal hari ini: {datetime.datetime.now().strftime('%Y-%m-%d')}

ANGGOTA TERPILIH DARI APLIKASI:
{selected_members_text}
- Jika anggota terpilih tersedia, PRIORITASKAN ID tersebut untuk parameter anggota_ids saat memanggil create_booking.
- Tetap tampilkan konfirmasi nama anggota ke user sebelum final booking.
- Jika user belum menyebut jumlah anggota tambahan, gunakan jumlah terdeteksi dari aplikasi sebagai acuan.

PEMERIKSAAN STATUS BOOKING & TIKET USER:
- Kamu MEMILIKI AKSES dan DAPAT MEMERIKSA status booking/tiket pengguna dari bagian "DATA PESANAN & JADWAL PENDAKIAN ANDA" di konteks data.
- ATURAN FILTERING TIKET:
  1. Jika pengguna bertanya tentang tiket/booking secara UMUM (contoh: "bagaimana status booking saya?", "tiket saya", "jadwal pendakian saya"):
     - HANYA TAMPILKAN tiket/pesanan yang berstatus AKTIF, yaitu:
       a. Tiket yang belum selesai dibayar ('Waiting Payment' atau 'pending')
       b. Tiket yang berstatus 'Booking'
       c. Tiket yang berstatus 'Sedang Mendaki'
     - JANGAN TAMPILKAN tiket yang sudah 'Selesai', 'Expired', atau 'Cancelled' pada pertanyaan umum.
     - Jika pengguna tidak memiliki tiket aktif (semua tiket sudah Selesai/Expired/Cancelled), sampaikan dengan ramah bahwa pengguna saat ini tidak memiliki tiket pendakian yang sedang aktif.
  2. KECUALI JIKA PERTANYAAN PENGGUNA BERSIFAT SPESIFIK:
     - Jika pengguna bertanya spesifik tentang expired/kedaluwarsa (misal: "apakah ada tiket expired?"): tampilkan tiket yang berstatus 'Expired'.
     - Jika pengguna bertanya spesifik tentang riwayat selesai (misal: "lihat tiket yang sudah selesai"): tampilkan tiket yang berstatus 'Selesai'.
     - Jika pengguna bertanya spesifik tentang pembatalan (misal: "apakah ada tiket dibatalkan?"): tampilkan tiket yang berstatus 'Cancelled'.
- DILARANG MENJAWAB "Maaf saya tidak bisa memeriksa status booking Anda" karena kamu memiliki data pesanan pengguna di konteks.

DATA YANG TERSEDIA:
{context}

Ingat: Kamu hanya boleh memberikan informasi yang ada di data di atas. Jangan mengarang data."""

    elif role == 'admin':
        return f"""Kamu adalah asisten virtual "Admin Assistant" untuk panel admin aplikasi My Hiking.
Tugasmu membantu admin mengelola data dan mendapatkan informasi sistem.

ATURAN FORMAT JAWABAN (SANGAT PENTING!):
- Gunakan markdown standar (**bold** untuk penekanan, *italic* untuk penulisan istilah, dll)
- JANGAN gunakan HURUF KAPITAL (ALL CAPS) secara berlebihan untuk penekanan atau judul. Gunakan format tebal (bold) markdown sebagai gantinya.
- Tulis dengan gaya bahasa yang profesional, ramah, natural, dan tidak kaku/robotik.
- Untuk daftar/list, gunakan tanda strip (-) atau angka (1. 2. 3.)
- Untuk tabel data, gunakan format tabel markdown yang rapi.
- DILARANG MENAMPILKAN ID DATABASE MENTAH (seperti 'ID: 1', '(ID: 1)', 'id_gunung: 1', dll) dalam jawaban teks Anda kepada Admin, kecuali jika Admin secara eksplisit meminta ID/kode database tersebut.
- Sebutkan nama gunung, nama jalur, nama user, atau lokasi secara bersih dan alami tanpa menambahkan suffix ID internal (Contoh BENAR: "Jalur Selo berada di Gunung Merbabu", Contoh SALAH: "Jalur Selo berada di Gunung Merbabu (ID: 1)").

PANDUAN:
1. Jawab dengan profesional, ringkas, dan jelas dalam Bahasa Indonesia.
2. Gunakan data yang tersedia untuk memberikan informasi akurat.
3. Kamu memiliki akses penuh ke semua data sistem.

KEMAMPUAN:
- Melihat semua data: gunung, jalur, pesanan, transaksi, user, SAR/darurat
- Melakukan CRUD pada data gunung dan jalur (gunakan fungsi crud_mountain dan crud_trail)
- Membuat rekap/laporan dalam format Excel (gunakan fungsi export_excel)
  - Tipe data yang bisa diekspor: sar_dashboard, laporan_pendapatan, pesanan, transaksi, user, gunung, jalur
- Memberikan ringkasan dan analisis data

CARA CRUD:
- Untuk menambah data, kumpulkan informasi yang diperlukan dari user lalu panggil fungsi CRUD
- Untuk mengubah data, tanyakan ID dan field yang ingin diubah
- Untuk menghapus data, konfirmasi dulu sebelum menghapus
- PENTING: Selalu minta konfirmasi sebelum melakukan operasi create/update/delete. Tanyakan dengan ramah (misal: "Apakah Anda yakin ingin memperbarui lokasi Gunung Merbabu?")

FITUR GENERATOR DATA GUNUNG & JALUR (DSS):
- Jika admin meminta untuk "generate", "buatkan otomatis", atau "buat simulasi" data gunung beserta jalurnya:
  1. Hasilkan informasi pendukung secara logis (deskripsi gunung yang relevan, ketinggian mdpl, koordinat latitude/longitude di Indonesia).
  2. Hasilkan ke-10 kriteria TOPSIS/DSS secara logis dan realistis untuk jalur tersebut:
     - Metrik Fisik Jalur:
       a. jarak (dalam km)
       b. elevasi (dalam meter)
       c. durasi (dalam jam)
       d. biaya (biaya tiket masuk, rupiah)
       e. tingkat_kesulitan (mudah/sedang/sulit/sangat_sulit)
     - Metrik Skor Preferensi:
       f. panorama_score (skala 1-5, keindahan alam)
       g. fasilitas_score (skala 1-5, fasilitas basecamp/shelter)
       h. safety_score (skala 1-5, keamanan & kerambu petunjuk)
       i. crowd_level (skala 1-5, keramaian jalur)
       j. popularity_score (skala 0-100, kepopuleran jalur)
  3. Konfirmasi terlebih dahulu hasil data simulasi/generasi tersebut (beserta ke-10 nilai kriteria DSS yang diusulkan) kepada admin sebelum mengeksekusi function call.
  4. Jika admin menyetujui, panggil `crud_mountain` terlebih dahulu untuk membuat gunung baru. Setelah mendapatkan response sukses, gunakan ID gunung tersebut untuk memanggil `crud_trail` guna membuat jalurnya.

CARA EKSPOR EXCEL:
- Jika admin meminta rekap/laporan dan tipe datanya sudah jelas, LANGSUNG panggil fungsi export_excel
- Jika tipe data belum jelas, tanyakan tipe data apa yang ingin diekspor
- Jika admin hanya bertanya data, status, atau ringkasan, JANGAN membuat file Excel
- Setelah file berhasil dibuat, beri tahu bahwa file siap diunduh dengan bahasa yang natural

Tanggal hari ini: {datetime.datetime.now().strftime('%Y-%m-%d')}

DATA SISTEM:
{context}"""

    elif role == 'penjaga':
        return f"""Kamu adalah asisten virtual "Trail Guard Assistant" untuk penjaga jalur pendakian di aplikasi My Hiking.
Tugasmu membantu penjaga jalur memantau keadaan jalur, pendaki, dan situasi darurat.

ATURAN FORMAT JAWABAN (SANGAT PENTING!):
- Gunakan markdown standar (**bold** untuk penekanan, *italic* untuk penulisan istilah, dll)
- JANGAN gunakan HURUF KAPITAL (ALL CAPS) secara berlebihan untuk penekanan atau judul. Gunakan format tebal (bold) markdown sebagai gantinya.
- Tulis dengan gaya bahasa yang sigap, profesional, ramah, dan tidak kaku/robotik.
- Untuk daftar/list, gunakan tanda strip (-) atau angka (1. 2. 3.)
- DILARANG MENAMPILKAN ID DATABASE MENTAH (seperti 'ID: 1', '(ID: 1)', 'id_gunung: 1', dll) dalam jawaban teks Anda kepada Penjaga, kecuali jika Penjaga secara eksplisit meminta ID/kode database tersebut.
- Sebutkan nama gunung, nama jalur, nama user, atau lokasi secara bersih dan alami tanpa menambahkan suffix ID internal (Contoh BENAR: "Jalur Selo berada di Gunung Merbabu", Contoh SALAH: "Jalur Selo berada di Gunung Merbabu (ID: 1)").

PANDUAN:
1. Jawab dengan profesional dan sigap dalam Bahasa Indonesia.
2. Prioritaskan informasi darurat/SAR.
3. Jika ada permintaan SAR aktif, SELALU ingatkan penjaga tentang hal ini secara jelas.

KEMAMPUAN:
- Melihat SAR Dashboard (permintaan darurat aktif dan riwayat) - gunakan fungsi get_sar_dashboard
- Melihat data pesanan aktif (pendaki yang sedang di gunung)
- Melihat data gunung dan jalur
- Membuat rekap/laporan dalam format Excel (gunakan fungsi export_excel)
  - Tipe data yang bisa diekspor: sar_dashboard, laporan_pendapatan, pesanan, transaksi, gunung, jalur

REMINDER SAR:
- Jika ada permintaan SAR aktif (status: pending/active/in_progress), WAJIB mengingatkan penjaga dengan format yang jelas dan informatif.
- Berikan detail lengkap: nama pendaki, lokasi, tipe darurat, koordinat

CARA EKSPOR EXCEL:
- Jika penjaga meminta rekap/laporan dan tipe datanya sudah jelas, LANGSUNG panggil fungsi export_excel
- Jika tipe data belum jelas, tanyakan tipe data apa yang ingin diekspor
- Jika penjaga hanya bertanya status SAR atau data umum, JANGAN membuat file Excel
- Setelah file berhasil dibuat, beri tahu bahwa file siap diunduh dengan bahasa yang natural

Tanggal hari ini: {datetime.datetime.now().strftime('%Y-%m-%d')}

DATA SISTEM:
{context}"""
    
    return ""


# ============================================
# PROCESS FUNCTION CALLS
# ============================================

def process_function_call(
    function_call,
    role,
    user_id=None,
    selected_member_ids=None,
    auth_token=None,
    user_message=None,
):
    """Memproses function call dari Gemini"""
    func_name = function_call.name
    args = dict(function_call.args) if function_call.args else {}

    allowed_functions_by_role = {
        'pendaki': {'create_booking'},
        'admin': {'export_excel', 'crud_mountain', 'crud_trail'},
        'penjaga': {'get_sar_dashboard', 'export_excel'},
    }
    allowed_functions = allowed_functions_by_role.get(role, set())

    if func_name not in allowed_functions:
        return {
            'success': False,
            'message': f"Fungsi '{func_name}' tidak diizinkan untuk role '{role}'"
        }
    
    print(f"[Function Call] {func_name} with args: {args}")
    
    if func_name == "create_booking":
        normalized_user_id = _normalize_positive_int(user_id)
        if not normalized_user_id:
            return {"success": False, "message": "User ID diperlukan untuk membuat booking"}

        normalized_gunung_id = _normalize_positive_int(args.get('id_gunung'))
        normalized_jalur_id = _normalize_positive_int(args.get('id_jalur'))
        if not normalized_gunung_id or not normalized_jalur_id:
            return {
                "success": False,
                "code": "INVALID_BOOKING_INPUT",
                "message": (
                    "Pilihan gunung atau jalur belum valid. "
                    "Silakan pilih kembali dari daftar yang tersedia."
                ),
            }

        anggota_from_args = _normalize_member_ids(args.get('anggota_ids'), user_id=normalized_user_id)
        anggota_from_selected = _normalize_member_ids(selected_member_ids, user_id=normalized_user_id)
        # Gabungkan sumber anggota dari function call + pilihan dari aplikasi.
        anggota_ids = list(dict.fromkeys(anggota_from_args + anggota_from_selected))

        result = tool_create_booking(
            user_id=normalized_user_id,
            id_gunung=normalized_gunung_id,
            id_jalur=normalized_jalur_id,
            tanggal_naik=args.get('tanggal_naik'),
            tanggal_turun=args.get('tanggal_turun'),
            anggota_ids=anggota_ids,
            auth_token=auth_token,
            force_continue=args.get('force_continue', False),
        )
        # Store payment_url for the response
        if result.get('payment_url'):
            get_gemini_response._last_payment_url = result['payment_url']
        if result.get('order_id'):
            get_gemini_response._last_order_id = result['order_id']
        if result.get('transaction_id'):
            get_gemini_response._last_transaction_id = result['transaction_id']
        return result
    
    elif func_name == "get_sar_dashboard":
        return tool_get_sar_dashboard()
    
    elif func_name == "export_excel":
        export_intent_text = (user_message or '').lower()
        has_explicit_export_intent = any(
            keyword in export_intent_text
            for keyword in ('export', 'excel', 'unduh', 'download', 'laporan', 'rekap')
        )

        requested_type = str(args.get('data_type', '')).strip().lower()
        valid_types_by_role = {
            'admin': {'sar_dashboard', 'laporan_pendapatan', 'pesanan', 'transaksi', 'user', 'gunung', 'jalur'},
            'penjaga': {'sar_dashboard', 'laporan_pendapatan', 'pesanan', 'transaksi', 'gunung', 'jalur'},
        }
        is_valid_type = requested_type in valid_types_by_role.get(role, set())
        is_affirmative_reply = any(
            keyword in export_intent_text
            for keyword in ('iya', 'ya', 'yes', 'oke', 'ok', 'lanjut', 'silakan', 'boleh')
        )

        # Izinkan export saat user konfirmasi singkat (mis. "iya")
        # selama tipe data ekspor sudah jelas dari konteks function call.
        can_export_on_confirmation = is_valid_type and is_affirmative_reply

        if not has_explicit_export_intent and not can_export_on_confirmation:
            return {
                'success': False,
                'message': 'Ekspor Excel dibatalkan karena permintaan unduhan belum jelas.',
            }

        result = tool_export_excel(args.get('data_type', ''), role)
        if result.get('success') and result.get('filename'):
            result['download_url'] = f"/api/chat/export/{result['filename']}"
        return result
    
    elif func_name == "crud_mountain":
        data = None
        if args.get('data'):
            try:
                data = json.loads(args['data'])
            except json.JSONDecodeError:
                data = args.get('data')
        return tool_crud_mountain(args.get('action', 'list'), data)
    
    elif func_name == "crud_trail":
        data = None
        if args.get('data'):
            try:
                data = json.loads(args['data'])
            except json.JSONDecodeError:
                data = args.get('data')
        return tool_crud_trail(args.get('action', 'list'), data)
    
    return {"success": False, "message": f"Fungsi '{func_name}' tidak dikenali"}


# ============================================
# MAIN CHAT FUNCTION
# ============================================

def get_gemini_response(
    user_message,
    role='pendaki',
    user_id=None,
    conversation_history=None,
    selected_member_ids=None,
    selected_member_names=None,
    auth_token=None,
):
    """Mendapatkan respons dari Gemini API dengan konteks RAG dan function calling"""
    
    # Normalize selected members once so counts stay consistent in prompt and tool calls.
    normalized_user_id = _normalize_positive_int(user_id)
    normalized_selected_member_ids = _normalize_member_ids(
        selected_member_ids,
        user_id=normalized_user_id,
    )
    normalized_selected_member_names = selected_member_names or []

    # Build context based on role
    if role == 'admin':
        context = build_context_admin()
    elif role == 'penjaga':
        context = build_context_penjaga(user_id=normalized_user_id)
    else:
        context = build_context_pendaki(user_id=normalized_user_id)
    
    # Get system prompt
    system_prompt = get_system_prompt(
        role,
        context,
        selected_member_ids=normalized_selected_member_ids,
        selected_member_names=normalized_selected_member_names,
    )
    
    # Get tools for role
    tools = get_tools_for_role(role)

    # List kandidat model resmi yang aktif dan didukung di Google Generative AI
    candidate_models = [
        'gemini-2.5-flash',
        'gemini-flash-latest',
        'gemini-2.0-flash',
    ]

    # Build chat history
    chat_messages = []
    if conversation_history:
        current_role = None
        current_parts = []
        
        for msg in conversation_history:
            msg_role = "user" if msg.get('isUser', True) else "model"
            msg_text = msg.get('message', '').strip()
            if not msg_text:
                continue
            
            if current_role is None:
                current_role = msg_role
                current_parts = [msg_text]
            elif msg_role == current_role:
                current_parts.append(msg_text)
            else:
                chat_messages.append({
                    "role": current_role,
                    "parts": ["\n\n".join(current_parts)]
                })
                current_role = msg_role
                current_parts = [msg_text]
        
        if current_role is not None and current_parts:
            chat_messages.append({
                "role": current_role,
                "parts": ["\n\n".join(current_parts)]
            })

    try:
        response = None
        last_error = None
        
        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    tools=tools,
                    system_instruction=system_prompt,
                )
                chat = model.start_chat(history=chat_messages)
                response = chat.send_message(user_message)
                if response:
                    print(f"[LOG] Gemini Model berhasil digunakan: '{model_name}'")
                    break
            except Exception as e:
                print(f"[Warning] Model '{model_name}' gagal/limit ({e}). Mencoba kandidat berikutnya...")
                last_error = e
        
        if not response:
            if last_error:
                raise last_error
            raise RuntimeError("Tidak ada model Gemini yang memberikan respon valid.")
        
        # Check for function calls
        download_url = None
        max_iterations = 5
        iteration = 0
        
        while response.candidates and iteration < max_iterations:
            candidate = response.candidates[0]
            
            # Check if there's a function call in any part
            function_call_part = None
            for part in candidate.content.parts:
                if part.function_call and part.function_call.name:
                    function_call_part = part
                    break
            
            if not function_call_part:
                break
            
            # Process the function call
            func_result = process_function_call(
                function_call_part.function_call,
                role,
                user_id,
                selected_member_ids=normalized_selected_member_ids,
                auth_token=auth_token,
                user_message=user_message,
            )
            
            # Check if there's a download URL
            if func_result.get('download_url'):
                download_url = func_result['download_url']

            # Untuk kegagalan readiness booking, kirim jawaban langsung agar user
            # mendapat instruksi jelas tanpa wording error generik dari model.
            if (
                role == 'pendaki'
                and function_call_part.function_call.name == 'create_booking'
                and func_result.get('code') in (
                    'PROFILE_INCOMPLETE',
                    'EXPERIENCE_ONBOARDING_REQUIRED',
                    'UNAUTHORIZED',
                    'INVALID_BOOKING_INPUT',
                )
            ):
                return {
                    'success': True,
                    'message': clean_markdown(func_result.get('message', 'Booking belum bisa diproses.')),
                    'code': func_result.get('code'),
                    'next_step': func_result.get('next_step'),
                }

            # Untuk semua function execution (create_booking, crud_mountain, crud_trail, export_excel, dll.),
            # kembalikan langsung pesan konfirmasi (berhasil/gagal) dari fungsi backend ke pengguna.
            if isinstance(func_result, dict) and func_result.get('message'):
                res_payload = {
                    'success': func_result.get('success', True),
                    'message': clean_markdown(func_result['message']),
                    'source': 'gemini_api',
                    'intent': function_call_part.function_call.name,
                    'type': 'text',
                }
                if func_result.get('order_id'):
                    res_payload['order_id'] = func_result['order_id']
                if func_result.get('transaction_id'):
                    res_payload['transaction_id'] = func_result['transaction_id']
                if func_result.get('payment_url'):
                    res_payload['payment_url'] = func_result['payment_url']
                if func_result.get('download_url'):
                    res_payload['download_url'] = func_result['download_url']
                if func_result.get('code'):
                    res_payload['code'] = func_result['code']
                if func_result.get('next_step'):
                    res_payload['next_step'] = func_result['next_step']
                return res_payload
            
            # Send function result back to Gemini
            response = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_call_part.function_call.name,
                            response={"result": json.dumps(func_result, default=str, ensure_ascii=False)}
                        )
                    )]
                )
            )
            
            iteration += 1
        
        # Extract final text response safely
        last_func_msg = func_result.get('message') if ('func_result' in locals() and isinstance(func_result, dict)) else None
        final_text = last_func_msg or "Permintaan telah diproses."
        try:
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    text_parts = [part.text for part in candidate.content.parts if hasattr(part, 'text') and part.text]
                    if text_parts:
                        final_text = "\n".join(text_parts).strip()
        except (ValueError, AttributeError, IndexError):
            pass
        
        # Clean markdown formatting from response
        final_text = clean_markdown(final_text)
        
        result = {
            'success': True,
            'message': final_text,
        }
        
        # Dynamic mountain card matching logic: HANYA dilampirkan jika user secara eksplisit menanyakan daftar gunung/jalur
        from database import fetch_mountains_data, fetch_trails_data
        try:
            mentioned_mountains = []
            user_msg_lower = user_message.lower()
            
            # Kartu gunung HANYA dilampirkan jika user menanyakan daftar gunung/jalur dan BUKAN query status booking/tiket
            is_status_query = any(kw in user_msg_lower for kw in ["status", "cek status", "riwayat", "tiket saya", "jadwal"])
            is_general_card_query = any(kw in user_msg_lower for kw in [
                "ada berapa gunung", "daftar gunung", "tampilkan gunung", "gunung apa saja", "gunung yang tersedia",
                "ada berapa jalur", "daftar jalur", "tampilkan jalur", "jalur apa saja", "jalur yang tersedia",
                "ada rute apa saja", "rute yang tersedia"
            ])
            
            if is_general_card_query and not is_status_query:
                all_mountains = fetch_mountains_data()
                all_trails = fetch_trails_data()
                matched_mountain_ids = set()
                
                # Match mountains directly by name
                for m in all_mountains:
                    name_lower = m['nama'].lower()
                    clean_name = name_lower.replace("gunung ", "").strip()
                    if name_lower in user_msg_lower or (len(clean_name) > 3 and clean_name in user_msg_lower):
                        matched_mountain_ids.add(m['id'])
                
                # If general query with no specific mountain name, include all mountains
                if not matched_mountain_ids:
                    for m in all_mountains:
                        matched_mountain_ids.add(m['id'])
                
                # Build final metadata for matched mountains
                for m in all_mountains:
                    if m['id'] in matched_mountain_ids:
                        mentioned_mountains.append({
                            'id': m['id'],
                            'nama': m['nama'],
                            'ketinggian': m['ketinggian'],
                            'deskripsi': m['deskripsi'],
                            'gambar_gunung': m.get('gambar_gunung', ''),
                            'provinsi': m.get('provinsi', 'Jawa Tengah'),
                        })
                
                if mentioned_mountains:
                    result['mountains'] = mentioned_mountains
        except Exception as ex:
            print(f"Error extracting mentioned mountains: {ex}")
            
        if download_url:
            result['download_url'] = download_url
        
        # Check if there was a payment URL from booking
        if hasattr(get_gemini_response, '_last_payment_url') and get_gemini_response._last_payment_url:
            result['payment_url'] = get_gemini_response._last_payment_url
            get_gemini_response._last_payment_url = None

        if hasattr(get_gemini_response, '_last_order_id') and get_gemini_response._last_order_id:
            result['order_id'] = get_gemini_response._last_order_id
            get_gemini_response._last_order_id = None

        if hasattr(get_gemini_response, '_last_transaction_id') and get_gemini_response._last_transaction_id:
            result['transaction_id'] = get_gemini_response._last_transaction_id
            get_gemini_response._last_transaction_id = None
        
        # Override to display route cards ONLY during booking creation flows (not for status booking or general chat)
        try:
            is_booking = False
            is_status_query = any(kw in user_message.lower() for kw in ["status", "cek status", "riwayat", "tiket saya", "jadwal"])
            
            if not is_status_query:
                primary_keywords = ["pesan tiket", "pesan tiker", "book tiket", "beli tiket", "order tiket", "pesan tempat", "pesan kuota", "create_booking"]
                step_keywords = ["detail pesanan", "ringkasan pesanan", "total biaya", "biaya per orang", "jumlah pendaki", "tektok atau ngecamp", "tanggal pendakian", "tanggal naik", "tanggal turun", "apakah detail", "apakah ringkasan", "proses pemesanan"]
                
                if any(kw in user_message.lower() for kw in primary_keywords + step_keywords):
                    is_booking = True
                elif any(kw in final_text.lower() for kw in primary_keywords + step_keywords):
                    is_booking = True

            if is_booking and role == 'pendaki':
                from static_faq import normalize_text, extract_mountain_name, extract_route_name
                from database import fetch_mountains_data, fetch_routes_by_mountain_name, fetch_route_detail
                
                all_mountains = fetch_mountains_data()
                matched_mountain = None
                matched_route = None
                
                texts_to_search = [final_text, user_message]
                if conversation_history:
                    for msg in reversed(conversation_history):
                        msg_text = msg.get('message', '')
                        if msg_text:
                            texts_to_search.append(msg_text)
                
                for text in texts_to_search:
                    norm_text = normalize_text(text)
                    mountain_name = extract_mountain_name(norm_text, all_mountains)
                    if mountain_name:
                        matched_mountain = mountain_name
                        break
                
                if matched_mountain:
                    routes = fetch_routes_by_mountain_name(matched_mountain)
                    for text in texts_to_search:
                        norm_text = normalize_text(text)
                        
                        # Count how many routes of this mountain are mentioned in this text
                        mentioned_routes = []
                        for r in routes:
                            r_name_lower = r['nama_jalur'].lower().replace("via", "").replace("jalur", "").strip()
                            if r_name_lower in norm_text:
                                mentioned_routes.append(r['nama_jalur'])
                        
                        # If exactly one route is mentioned in the text, it's a selected/confirmed route.
                        # Multiple routes indicates a list/choices text, which we ignore.
                        if len(mentioned_routes) == 1:
                            matched_route = mentioned_routes[0]
                            break
                
                if matched_mountain:
                    FALLBACK_IMAGE = "assets/images/img_error.png"
                    
                    if matched_route:
                        # Case 2: Specific route chosen -> Show this route card without Pesan Tiket button
                        r = fetch_route_detail(matched_mountain, matched_route)
                        if r:
                            basecamp_parts = []
                            if r.get('desa'):
                                basecamp_parts.append(r['desa'])
                            if r.get('kecamatan'):
                                basecamp_parts.append(r['kecamatan'])
                            if r.get('kabupaten'):
                                basecamp_parts.append(r['kabupaten'])
                            basecamp_str = ", ".join(basecamp_parts) if basecamp_parts else "Tidak tersedia"

                            estimasi = f"{r['estimasi_waktu']} jam" if r.get('estimasi_waktu') else "Belum tersedia"
                            
                            route_data = {
                                "id": r["id"],
                                "id_gunung": r["id_gunung"],
                                "nama_jalur": r["nama_jalur"],
                                "jarak": float(r["jarak"]) if r.get("jarak") else 0,
                                "biaya": int(r["biaya"]) if r.get("biaya") else 0,
                                "estimasi_waktu": estimasi,
                                "tingkat_kesulitan": r.get("tingkat_kesulitan") or "Belum dikategorikan",
                                "deskripsi": r.get("deskripsi") or "",
                                "basecamp": f"Basecamp {basecamp_str}",
                                "provinsi": r.get("provinsi") or "Jawa Tengah",
                                "gambar_jalur": r.get("gambar_jalur") or FALLBACK_IMAGE,
                                "buttons": []  # Empty buttons array to hide Pesan Tiket button
                            }
                            
                            result['type'] = 'route_cards'
                            result['data'] = {
                                "mountain_name": r["nama_gunung"],
                                "routes": [route_data]
                            }
                            # Remove mountain cards to avoid overlap
                            result.pop('mountains', None)
                    else:
                        # Case 1: Mountain chosen but route not chosen -> Show list of route cards with Pesan Tiket button
                        routes = fetch_routes_by_mountain_name(matched_mountain)
                        if routes:
                            routes_list = []
                            for r in routes:
                                basecamp_parts = []
                                if r.get('desa'):
                                    basecamp_parts.append(r['desa'])
                                if r.get('kecamatan'):
                                    basecamp_parts.append(r['kecamatan'])
                                if r.get('kabupaten'):
                                    basecamp_parts.append(r['kabupaten'])
                                basecamp_str = ", ".join(basecamp_parts) if basecamp_parts else "Tidak tersedia"

                                estimasi = f"{r['estimasi_waktu']} jam" if r.get('estimasi_waktu') else "Belum tersedia"

                                routes_list.append({
                                    "id": r["id"],
                                    "id_gunung": r["id_gunung"],
                                    "nama_jalur": r["nama_jalur"],
                                    "jarak": float(r["jarak"]) if r.get("jarak") else 0,
                                    "biaya": int(r["biaya"]) if r.get("biaya") else 0,
                                    "estimasi_waktu": estimasi,
                                    "tingkat_kesulitan": r.get("tingkat_kesulitan") or "Belum dikategorikan",
                                    "deskripsi": r.get("deskripsi") or "",
                                    "basecamp": f"Basecamp {basecamp_str}",
                                    "provinsi": r.get("provinsi") or "Jawa Tengah",
                                    "gambar_jalur": r.get("gambar_jalur") or FALLBACK_IMAGE,
                                    "buttons": [
                                        {"label": "Pesan Tiket", "payload": f"Pesan tiket {r['nama_gunung']} {r['nama_jalur']}"}
                                    ]
                                })
                            
                            result['type'] = 'route_cards'
                            result['data'] = {
                                "mountain_name": matched_mountain,
                                "routes": routes_list
                            }
                            # Remove mountain cards to avoid overlap
                            result.pop('mountains', None)
                            
                            # Override text response to show only the prompt to select a route card
                            result['message'] = f"{matched_mountain} memiliki beberapa jalur pendakian. Mohon pilih salah satu jalur di bawah ini:"
        except Exception as override_ex:
            print(f"Error in booking route card override: {override_ex}")
        
        return result
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Maaf, terjadi kesalahan saat memproses pertanyaan Anda. Silakan coba lagi.'
        }
