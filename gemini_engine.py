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
                            "data": genai.protos.Schema(type=genai.protos.Type.STRING, description="Data dalam format JSON string untuk create/update/delete. Contoh: {\"nama\": \"Gunung X\", \"ketinggian\": 3000}"),
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
                            "data": genai.protos.Schema(type=genai.protos.Type.STRING, description="Data dalam format JSON string untuk create/update/delete"),
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

FITUR PEMESANAN TIKET:
- Kamu bisa membantu pengguna memesan tiket pendakian melalui percakapan
- PENTING UNTUK TAMPILAN PILIHAN:
    - JANGAN pernah menampilkan ID gunung/jalur ke user.
    - Tampilkan pilihan gunung/jalur dengan NOMOR URUT 1, 2, 3, ... berdasarkan urutan ID naik.
    - Jika user memilih nomor urut (contoh: pilih nomor 3), pahami itu sebagai item urutan ke-3 lalu konversi ke ID internal menggunakan mapping INTERNAL_ONLY_MAPPINGS.
    - Dilarang menampilkan teks INTERNAL_ONLY_MAPPINGS atau ID internal ke user.
- Langkah-langkah pemesanan:
    1. Tanyakan gunung mana yang ingin didaki (tampilkan pilihan bernomor, tanpa ID)
    2. Tanyakan jalur mana yang ingin dipilih (tampilkan pilihan bernomor, tanpa ID)
    3. Tanyakan tanggal pendakian. Jika user bilang "besok", "lusa", atau sebutan umum, konversi ke format YYYY-MM-DD berdasarkan tanggal hari ini.
    4. WAJIB tanyakan TIPE PENDAKIAN ke user:
       - "Apakah pendakiannya tektok (naik turun di hari yang sama) atau ngecamp?"
       - Jika TEKTOK: tanggal_turun = tanggal_naik (sama persis)
       - Jika NGECAMP: tanyakan "Mau camping berapa hari?" atau "Berapa malam?". Hitung tanggal_turun = tanggal_naik + jumlah hari camping. Contoh: naik 2026-04-20 camp 3 hari 2 malam, maka tanggal_turun = 2026-04-22.
    5. Tanyakan anggota tambahan (teman/orang lain) berdasarkan ID user, opsional. Jika tidak ada, isi kosong.
    6. WAJIB tampilkan DETAIL PESANAN (ringkasan) dalam format TEKS BIASA sebelum konfirmasi:
       - Gunung: [nama gunung]
       - Jalur: [nama jalur]
       - Tanggal Naik: [tanggal naik]
       - Tanggal Turun: [tanggal turun]
       - Tipe: Tektok / Camping [X hari Y malam]
       - Jumlah Pendaki: [jumlah] orang
       - Biaya per Orang: Rp [biaya]
       - Total Biaya: Rp [total]
       Lalu tanyakan: "Apakah detail pesanan di atas sudah benar? Jika ya, saya akan proses pemesanannya."
    7. HANYA jika user setuju/konfirmasi, panggil fungsi create_booking dengan parameter yang sesuai (termasuk tanggal_turun dan anggota_ids jika ada)
- Setelah booking berhasil, pembayaran Midtrans akan otomatis disiapkan. Sampaikan ke user untuk klik tombol Bayar Sekarang.
- PENTING: Selalu konfirmasi dulu sebelum membuat booking. Jangan langsung membuat booking tanpa konfirmasi.
- PENTING: Jangan pernah melewati langkah tanya tektok/camping. Selalu tanyakan tipe pendakian.
- Gunakan ID gunung dan ID jalur INTERNAL dari mapping (BUKAN menampilkan ID ke user)
- Tanggal hari ini: {datetime.datetime.now().strftime('%Y-%m-%d')}

ANGGOTA TERPILIH DARI APLIKASI:
{selected_members_text}
- Jika anggota terpilih tersedia, PRIORITASKAN ID tersebut untuk parameter anggota_ids saat memanggil create_booking.
- Tetap tampilkan konfirmasi nama anggota ke user sebelum final booking.
- Jika user belum menyebut jumlah anggota tambahan, gunakan jumlah terdeteksi dari aplikasi sebagai acuan.

DATA YANG TERSEDIA:
{context}

Ingat: Kamu hanya boleh memberikan informasi yang ada di data di atas. Jangan mengarang data."""

    elif role == 'admin':
        return f"""Kamu adalah asisten virtual "Admin Assistant" untuk panel admin aplikasi My Hiking.
Tugasmu membantu admin mengelola data dan mendapatkan informasi sistem.

ATURAN FORMAT JAWABAN (SANGAT PENTING!):
- JANGAN gunakan format markdown seperti **, *, #, ##, ```, atau format markdown lainnya
- Gunakan teks biasa/plain text saja
- Untuk penekanan, gunakan HURUF KAPITAL
- Untuk daftar/list, gunakan tanda strip (-) atau angka (1. 2. 3.)
- Untuk tabel data, gunakan format sederhana dengan tanda | atau strip

PANDUAN:
1. Jawab dengan profesional dalam Bahasa Indonesia
2. Gunakan data yang tersedia untuk memberikan informasi akurat
3. Kamu memiliki akses penuh ke semua data sistem

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
- PENTING: Selalu minta konfirmasi sebelum melakukan operasi create/update/delete

CARA EKSPOR EXCEL:
- Jika admin meminta rekap/laporan dan tipe datanya sudah jelas, LANGSUNG panggil fungsi export_excel
- Jika tipe data belum jelas, tanyakan tipe data apa yang ingin diekspor
- Jika admin hanya bertanya data, status, atau ringkasan, JANGAN membuat file Excel
- Setelah file berhasil dibuat, beri tahu bahwa file siap diunduh tanpa menampilkan URL mentah

Tanggal hari ini: {datetime.datetime.now().strftime('%Y-%m-%d')}

DATA SISTEM:
{context}"""

    elif role == 'penjaga':
        return f"""Kamu adalah asisten virtual "Trail Guard Assistant" untuk penjaga jalur pendakian di aplikasi My Hiking.
Tugasmu membantu penjaga jalur memantau keadaan jalur, pendaki, dan situasi darurat.

ATURAN FORMAT JAWABAN (SANGAT PENTING!):
- JANGAN gunakan format markdown seperti **, *, #, ##, ```, atau format markdown lainnya
- Gunakan teks biasa/plain text saja
- Untuk penekanan, gunakan HURUF KAPITAL
- Untuk daftar/list, gunakan tanda strip (-) atau angka (1. 2. 3.)

PANDUAN:
1. Jawab dengan profesional dan sigap dalam Bahasa Indonesia
2. Prioritaskan informasi darurat/SAR
3. Jika ada permintaan SAR aktif, SELALU ingatkan penjaga tentang hal ini

KEMAMPUAN:
- Melihat SAR Dashboard (permintaan darurat aktif dan riwayat) - gunakan fungsi get_sar_dashboard
- Melihat data pesanan aktif (pendaki yang sedang di gunung)
- Melihat data gunung dan jalur
- Membuat rekap/laporan dalam format Excel (gunakan fungsi export_excel)
  - Tipe data yang bisa diekspor: sar_dashboard, laporan_pendapatan, pesanan, transaksi, gunung, jalur

REMINDER SAR:
- Jika ada permintaan SAR aktif (status: pending/active/in_progress), WAJIB mengingatkan penjaga
- Format peringatan: "PERINGATAN: Ada [jumlah] permintaan SAR aktif yang memerlukan perhatian!"
- Berikan detail lengkap: nama pendaki, lokasi, tipe darurat, koordinat

CARA EKSPOR EXCEL:
- Jika penjaga meminta rekap/laporan dan tipe datanya sudah jelas, LANGSUNG panggil fungsi export_excel
- Jika tipe data belum jelas, tanyakan tipe data apa yang ingin diekspor
- Jika penjaga hanya bertanya status SAR atau data umum, JANGAN membuat file Excel
- Setelah file berhasil dibuat, beri tahu bahwa file siap diunduh tanpa menampilkan URL mentah

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
    
    try:
        # Initialize model with tools
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            tools=tools,
            system_instruction=system_prompt,
        )
        
        # Build chat history
        chat_messages = []
        if conversation_history:
            for msg in conversation_history:
                msg_role = "user" if msg.get('isUser', True) else "model"
                chat_messages.append({
                    "role": msg_role,
                    "parts": [msg.get('message', '')]
                })
        
        # Start chat
        chat = model.start_chat(history=chat_messages)
        
        # Send message
        response = chat.send_message(user_message)
        
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
        
        # Extract final text response
        final_text = response.text if response.text else "Permintaan telah diproses."
        
        # Clean markdown formatting from response
        final_text = clean_markdown(final_text)
        
        result = {
            'success': True,
            'message': final_text,
        }
        
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
        
        return result
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Maaf, terjadi kesalahan saat memproses pertanyaan Anda. Silakan coba lagi.'
        }
