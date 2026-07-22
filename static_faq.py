"""
Static FAQ / Rule-based Layer for My Hiking Chatbot
=====================================================
Menyaring pesan user sebelum dikirim ke Gemini API.
Jika pesan cocok dengan pola FAQ, jawab langsung dari database MySQL.
Jika tidak cocok, return None agar fallback ke Gemini API.

Tujuan:
1. Mengurangi penggunaan token Gemini
2. Kecepatan respons (latency)
3. Konsistensi jawaban (tanpa halusinasi AI)
"""

import re
from database import (
    fetch_mountains_data,
    fetch_trails_data,
    fetch_routes_by_mountain_name,
    fetch_route_detail,
    fetch_rules_by_mountain,
    fetch_rules_data,
)

# Fallback image jika tidak ada gambar di database
FALLBACK_IMAGE = "assets/images/img_error.png"


def normalize_text(text):
    """Membersihkan teks dari spasi berlebih dan mengubah ke huruf kecil"""
    if not text:
        return ""
    text = text.lower().strip()
    # Menghapus tanda baca umum untuk memudahkan pencocokan keyword
    text = re.sub(r'[.,\/#!$%\^&\*;:{}=\-_`~()?]', '', text)
    return text


def extract_mountain_name(normalized_text, all_mountains):
    """Mengekstraksi nama gunung yang ada di dalam database dari input user.
    Menggunakan regex boundary (\b) untuk mencegah pencocokan substring parsial.
    """
    for m in all_mountains:
        name_lower = m['nama'].lower()
        clean_name = name_lower.replace("gunung ", "").strip()

        if name_lower in normalized_text or re.search(rf'\b{re.escape(clean_name)}\b', normalized_text):
            return m['nama']
    return None


def extract_route_name(normalized_text, routes):
    """Mengekstraksi nama jalur pendakian dari input user"""
    clean_text = normalized_text.replace("via", "").replace("jalur", "").strip()

    for r in routes:
        trail_name_lower = r['nama_jalur'].lower().replace("via", "").replace("jalur", "").strip()
        if re.search(rf'\b{re.escape(trail_name_lower)}\b', clean_text):
            return r['nama_jalur']
    return None


def format_trail_name(name):
    if not name:
        return ""
    name_str = str(name).strip()
    if name_str.lower().startswith("jalur "):
        return name_str
    return f"Jalur {name_str}"


def _build_route_detail_response(detail, query_text=""):
    """Helper merakit response kartu detail rute dengan teks yang spesifik"""
    basecamp_parts = []
    if detail.get('desa'):
        basecamp_parts.append(detail['desa'])
    if detail.get('kecamatan'):
        basecamp_parts.append(detail['kecamatan'])
    if detail.get('kabupaten'):
        basecamp_parts.append(detail['kabupaten'])
    basecamp_str = ", ".join(basecamp_parts) if basecamp_parts else "Tidak tersedia"
    estimasi = f"{detail['estimasi_waktu']} jam" if detail.get('estimasi_waktu') else "Belum tersedia"
    biaya_formatted = f"Rp {int(detail['biaya']):,}" if detail.get('biaya') else "Rp 0"
    trail_title = format_trail_name(detail['nama_jalur'])

    norm = query_text.lower()
    if any(k in norm for k in ["biaya", "harga", "tarif", "bayar"]):
        message_text = f"Biaya e-tiket pendakian {detail['nama_gunung']} {trail_title} adalah {biaya_formatted} per orang. Berikut detail kartu jalurnya:"
    elif any(k in norm for k in ["jarak", "estimasi", "lama", "durasi", "waktu"]):
        message_text = f"Jarak tempuh {detail['nama_gunung']} {trail_title} adalah {detail.get('jarak', 0)} km dengan estimasi waktu pendakian sekitar {estimasi}. Berikut detail kartu jalurnya:"
    else:
        message_text = f"Ini dia info lengkap jalur {detail['nama_gunung']} {trail_title}! Langsung pesan tiket kalau kamu tertarik ya."

    return {
        "success": True,
        "source": "static_faq",
        "intent": "route_detail",
        "type": "route_cards",
        "message": message_text,
        "data": {
            "mountain_name": detail["nama_gunung"],
            "routes": [{
                "id": detail["id"],
                "id_gunung": detail["id_gunung"],
                "nama_jalur": detail["nama_jalur"],
                "jarak": float(detail["jarak"]) if detail.get("jarak") else 0,
                "biaya": int(detail["biaya"]) if detail.get("biaya") else 0,
                "estimasi_waktu": estimasi,
                "tingkat_kesulitan": detail.get("tingkat_kesulitan") or "Belum dikategorikan",
                "deskripsi": detail.get("deskripsi") or "",
                "basecamp": f"Basecamp {basecamp_str}",
                "provinsi": detail.get("provinsi") or "Jawa Tengah",
                "gambar_jalur": detail.get("gambar_jalur") or FALLBACK_IMAGE,
                "buttons": [
                    {"label": "Pesan Tiket", "payload": f"Pesan tiket {detail['nama_gunung']} {detail['nama_jalur']}"}
                ]
            }]
        }
    }


def get_static_response(user_message):
    """
    Fungsi utama untuk mengevaluasi apakah input user masuk kategori FAQ.

    Return:
        dict: Response JSON jika cocok dengan FAQ
        None: Jika tidak cocok, agar fallback ke Gemini API
    """
    normalized = normalize_text(user_message)

    # ===================================================================
    # BYPASS KE GEMINI (Return None):
    # Untuk pertanyaan yang butuh penalaran/perbandingan/rekomendasi spesifik/data personal user
    # ===================================================================
    all_mountains = fetch_mountains_data()
    extracted_mountain = extract_mountain_name(normalized, all_mountains)

    all_trails = fetch_trails_data()
    has_specific_trail = any(re.search(rf'\b{re.escape(t["nama_jalur"].lower().replace("via","").replace("jalur","").strip())}\b', normalized) for t in all_trails if len(t["nama_jalur"].strip()) > 2)

    # Bypass jika perbandingan ("paling murah", "paling singkat") ATAU rekomendasi spesifik gunung/jalur ("apakah selo cocok untuk pemula")
    is_comparison = any(k in normalized for k in ["murah", "mahal", "singkat", "cepat", "paling", "dibandingkan", "pilihan terbaik"])
    is_specific_recommendation = (extracted_mountain or has_specific_trail) and any(k in normalized for k in ["pemula", "cocok", "rekomendasi"])

    if is_comparison or is_specific_recommendation:
        return None

    # 2. Pertanyaan status booking / jadwal personal user (dibaca dari RAG user orders)
    if any(k in normalized for k in [
        "jadwal", "booking saya", "pesanan saya", "status booking", "status pesanan"
    ]):
        return None

    # 3. Bypass static FAQ untuk permintaan pemesanan tiket / booking agar diproses oleh Gemini API.
    is_refund_query = any(k in normalized for k in ["cancel", "batal", "refund", "pembatalan", "batalin", "uang kembali"])
    if not is_refund_query:
        if any(k in normalized for k in [
            "pesan tiket", "pesan tiker", "pesen tiket", "pesen tiker",
            "oesan tiket", "oesan tiker", "booking", "book tiket",
            "beli tiket", "order tiket", "pesan tempat", "pesan kuota",
            "pesan", "pesen", "oesan"
        ]):
            return None

    # ===================================================================
    # 1. INTENT: mountain_detail (Ketinggian / Lokasi spesifik Gunung)
    # ===================================================================
    if extracted_mountain and any(k in normalized for k in ["ketinggian", "tinggi", "lokasi", "di mana", "dimana", "provinsi"]):
        mountain_data = next((m for m in all_mountains if m['nama'].lower() == extracted_mountain.lower()), None)
        if mountain_data:
            if any(k in normalized for k in ["ketinggian", "tinggi"]):
                return {
                    "success": True,
                    "source": "static_faq",
                    "intent": "mountain_detail",
                    "type": "text",
                    "message": f"Ketinggian {mountain_data['nama']} adalah {mountain_data['ketinggian']} mdpl."
                }
            elif any(k in normalized for k in ["lokasi", "di mana", "dimana", "provinsi"]):
                return {
                    "success": True,
                    "source": "static_faq",
                    "intent": "mountain_detail",
                    "type": "text",
                    "message": f"{mountain_data['nama']} berlokasi di Provinsi {mountain_data.get('provinsi', 'Jawa Tengah')}."
                }

    # ===================================================================
    # 2. INTENT: hiking_rules (DICEK SEBELUM ROUTE DETAIL AGAR "tata tertib jalur X" TIDAK TERTANGKAP CARD JALUR)
    # ===================================================================
    if any(k in normalized for k in [
        "aturan", "tata tertib", "peraturan", "bolehkah mendaki",
        "dilarang", "syarat mendaki", "ketentuan mendaki"
    ]):
        # Jika user menyebutkan nama gunung
        if extracted_mountain:
            rules_data = fetch_rules_by_mountain(extracted_mountain)
            if rules_data:
                rule_text = f"TATA TERTIB PENDAKIAN {extracted_mountain.upper()}:\n"
                for idx, r in enumerate(rules_data, 1):
                    t_title = format_trail_name(r['nama_jalur'])
                    rule_text += f"{idx}. [{t_title}]: {r['tata_tertib']}\n"
                rule_text += "\nOh iya, aturan detail lainnya bisa saja berbeda di tiap basecamp. Biar lebih pasti, jangan lupa cek tata tertib lengkap di halaman info gunung ya!"
                return {
                    "success": True,
                    "source": "static_faq",
                    "intent": "hiking_rules",
                    "type": "text",
                    "message": rule_text.strip()
                }

        # Jika user menyebutkan nama jalur spesifik (misal: "tata tertib jalur kaliwadas")
        all_rules = fetch_rules_data()
        matched_rules = []
        for r in all_rules:
            trail_clean = r['nama_jalur'].lower().replace("via", "").replace("jalur", "").strip()
            if re.search(rf'\b{re.escape(trail_clean)}\b', normalized):
                matched_rules.append(r)

        if matched_rules:
            trail_name = format_trail_name(matched_rules[0]['nama_jalur']).upper()
            mountain_name = matched_rules[0]['nama_gunung'].upper()
            rule_text = f"TATA TERTIB PENDAKIAN {mountain_name} ({trail_name}):\n"
            for idx, r in enumerate(matched_rules, 1):
                rule_text += f"{idx}. {r['tata_tertib']}\n"
            return {
                "success": True,
                "source": "static_faq",
                "intent": "hiking_rules",
                "type": "text",
                "message": rule_text.strip()
            }

        # Fallback aturan umum
        return {
            "success": True,
            "source": "static_faq",
            "intent": "hiking_rules",
            "type": "text",
            "message": "ATURAN UMUM PENDAKIAN MYHIKING:\n1. Pendaki wajib membawa kartu identitas asli (KTP/SIM/Paspor) saat check-in.\n2. Wajib registrasi online dan melakukan pembayaran e-tiket sebelum waktu pendakian.\n3. Dilarang membuang sampah sembarangan dan wajib membawa sampah kembali ke basecamp.\n4. Tidak diperkenankan merusak flora, fauna, dan situs cagar alam di sepanjang jalur pendakian.\n\nSetiap gunung juga punya aturan khusus masing-masing, lho. Biar pendakianmu berjalan lancar, yuk cek detail tata tertib lengkap tiap gunung di halaman info gunung ya!"
        }

    # ===================================================================
    # 2. INTENT: list_mountains
    # ===================================================================
    if any(k in normalized for k in [
        "ada gunung apa saja", "daftar gunung", "tampilkan gunung",
        "gunung yang tersedia", "pilihan gunung", "gunung apa saja",
        "ada berapa gunung", "list gunung", "gunung tersedia"
    ]):
        mountains_list = []
        for m in all_mountains:
            mountains_list.append({
                "id": m["id"],
                "nama": m["nama"],
                "ketinggian": m["ketinggian"],
                "provinsi": m.get("provinsi", "Jawa Tengah"),
                "deskripsi": m["deskripsi"],
                "gambar_gunung": m.get("gambar_gunung") or FALLBACK_IMAGE
            })

        return {
            "success": True,
            "source": "static_faq",
            "intent": "list_mountains",
            "type": "mountain_cards",
            "message": f"Di MyHiking, ada {len(mountains_list)} gunung yang bisa kamu daki! Yuk pilih salah satu untuk lihat jalur pendakiannya.",
            "data": {
                "mountains": mountains_list
            }
        }

    # ===================================================================
    # 3. INTENT: list_routes_by_mountain / route_detail
    # ===================================================================
    is_route_query = any(k in normalized for k in [
        "jalur", "rute", "via", "estimasi", "lama pendakian",
        "biaya mendaki", "list jalur", "daftar jalur",
        "jalur apa saja", "ada berapa jalur", "jalur yang tersedia",
        "jalur tersedia", "rute pendakian", "ada rute apa"
    ])

    if is_route_query:
        if extracted_mountain:
            routes = fetch_routes_by_mountain_name(extracted_mountain)
            if not routes:
                return {
                    "success": True,
                    "source": "static_faq",
                    "intent": "list_routes_by_mountain",
                    "type": "text",
                    "message": f"Waduh, saat ini belum ada jalur pendakian aktif yang terdaftar untuk {extracted_mountain} di database kami. Coba cek gunung lainnya ya!"
                }

            # Cek jika menanyakan detail jalur spesifik (misal: Jalur Selo)
            extracted_route = extract_route_name(normalized, routes)
            if extracted_route:
                detail = fetch_route_detail(extracted_mountain, extracted_route)
                if detail:
                    return _build_route_detail_response(detail, user_message)

            # Jika tidak ada rute spesifik yang dicocokkan, tampilkan semua jalur gunung tersebut
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
                        {"label": "Detail Jalur", "payload": f"Detail jalur {r['nama_gunung']} {r['nama_jalur']}"},
                        {"label": "Pesan Tiket", "payload": f"Pesan tiket {r['nama_gunung']} {r['nama_jalur']}"}
                    ]
                })

            return {
                "success": True,
                "source": "static_faq",
                "intent": "list_routes_by_mountain",
                "type": "route_cards",
                "message": f"Ada {len(routes_list)} jalur pendakian resmi di {extracted_mountain}! Silakan pilih jalur yang ingin kamu gunakan:",
                "data": {
                    "mountain_name": extracted_mountain,
                    "routes": routes_list
                }
            }
        else:
            # Jika gunung tidak terdeteksi di teks, cek apakah user menyebut nama jalur spesifik (misal: "Berapa biaya jalur Selo?")
            all_trails = fetch_trails_data()
            matched_trail = None
            for t in all_trails:
                trail_clean = t['nama_jalur'].lower().replace("via", "").replace("jalur", "").strip()
                if re.search(rf'\b{re.escape(trail_clean)}\b', normalized):
                    matched_trail = t
                    break

            if matched_trail:
                detail = fetch_route_detail(matched_trail['nama_gunung'], matched_trail['nama_jalur'])
                if detail:
                    return _build_route_detail_response(detail, user_message)

            # Jika tidak ada nama gunung maupun nama jalur spesifik, tampilkan kartu gunung untuk dipilih
            mountains_list = []
            for m in all_mountains:
                mountains_list.append({
                    "id": m["id"],
                    "nama": m["nama"],
                    "ketinggian": m["ketinggian"],
                    "provinsi": m.get("provinsi", "Jawa Tengah"),
                    "deskripsi": m["deskripsi"],
                    "gambar_gunung": m.get("gambar_gunung") or FALLBACK_IMAGE
                })
            return {
                "success": True,
                "source": "static_faq",
                "intent": "fallback_no_mountain",
                "type": "mountain_cards",
                "message": "Kamu mau lihat jalur pendakian di gunung mana? Pilih dulu gunungnya di bawah ini ya!",
                "data": {
                    "mountains": mountains_list
                }
            }

    # ===================================================================
    # 4. INTENT: refund_policy
    # ===================================================================
    if any(k in normalized for k in [
        "refund", "batal", "cancel", "uang kembali",
        "pembatalan tiket", "bisa batalin", "kebijakan refund"
    ]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "refund_policy",
            "type": "text",
            "message": "KEBIJAKAN REFUND & PEMBATALAN TIKET:\n1. Pembatalan tiket dapat dilakukan secara mandiri melalui menu 'Waiting Payment' atau Detail Tiket sebelum statusnya berubah menjadi Check-In.\n2. Refund dana akan dipotong biaya penalti sesuai dengan H-X tanggal pendakian (silakan cek ketentuan detail pada halaman refund).\n3. Pengembalian dana akan dikirimkan ke rekening bank / e-wallet yang kamu daftarkan dalam waktu maksimal 3x24 jam setelah pengajuan disetujui.\n\n*Catatan penting: Pengembalian dana (refund berupa uang) hanya berlaku untuk gunung yang kebijakannya mengizinkan refund uang ya. Jadi, pastikan kamu memeriksa kembali aturan refund dari gunung yang kamu pesan!"
        }

    # ===================================================================
    # 5. INTENT: payment_info / payment_detail
    # ===================================================================
    # Deteksi detail metode pembayaran spesifik terlebih dahulu untuk menghindari perulangan (loop)
    if any(k in normalized for k in ["virtual account", "bank va", "transfer va", "nomor va", "akun virtual"]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "payment_detail_va",
            "type": "text",
            "message": "CARA BAYAR PAKAI VIRTUAL ACCOUNT (VA):\n\n1. Pilih opsi pembayaran 'Virtual Account' saat melakukan checkout pemesanan tiket.\n2. Kamu akan mendapatkan nomor Virtual Account unik dan nominal tagihan.\n3. Lakukan pembayaran melalui mobile banking, internet banking, atau ATM sesuai dengan bank yang kamu pilih (seperti BCA, Mandiri, BRI, BNI, dll).\n4. Setelah transfer selesai, sistem MyHiking akan memverifikasi pembayaranmu secara otomatis dalam waktu kurang dari 1 menit!"
        }

    if any(k in normalized for k in ["e-wallet", "ewallet", "gopay", "qris", "shopeepay", "shopee pay", "dana", "ovo", "linkaja"]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "payment_detail_ewallet",
            "type": "text",
            "message": "CARA BAYAR PAKAI E-WALLET / QRIS:\n\n1. Pilih opsi pembayaran 'GoPay/QRIS' saat checkout tiket.\n2. Jika kamu memesan lewat handphone, kamu bisa langsung memilih opsi buka aplikasi e-wallet (seperti GoPay atau ShopeePay) untuk menyelesaikan pembayaran.\n3. Jika memesan lewat laptop/PC, sebuah kode QRIS akan tampil di layar. Buka aplikasi e-wallet favoritmu (GoPay, OVO, Dana, LinkAja, atau m-banking yang mendukung QRIS), lalu scan kode QR tersebut.\n4. Konfirmasi pembayaran dan transaksi akan langsung terverifikasi lunas secara real-time!"
        }

    if any(k in normalized for k in ["minimarket", "alfamart", "indomaret", "indomart", "alfamidi"]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "payment_detail_minimarket",
            "type": "text",
            "message": "CARA BAYAR LEWAT MINIMARKET (ALFAMART / INDOMARET):\n\n1. Pilih opsi pembayaran 'Alfamart' atau 'Indomaret' saat checkout tiket.\n2. Catat atau screenshot 'Kode Pembayaran' yang ditampilkan di layar.\n3. Datang ke gerai Alfamart atau Indomaret terdekat, sampaikan ke kasir bahwa kamu ingin melakukan pembayaran merchant Midtrans atau MyHiking.\n4. Tunjukkan kode pembayaran tersebut kepada kasir, dan selesaikan transaksi menggunakan uang tunai atau metode pembayaran yang diterima di kasir.\n5. Kasir akan memberikan struk fisik sebagai bukti pembayaran sah. Simpan struk tersebut ya!"
        }

    # Memicu informasi opsi metode pembayaran (Gunakan frasa spesifik alih-alih kata "bayar" tunggal agar tidak bentrok dengan pertanyaan biaya)
    if any(k in normalized for k in [
        "metode pembayaran", "pembayaran", "midtrans",
        "cara bayar", "bayarnya lewat apa", "bisa pakai ewallet",
        "metode bayar", "opsi bayar", "sistem bayar"
    ]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "payment_info",
            "type": "buttons",
            "message": "Transaksi e-tiket pendakian didukung sepenuhnya secara aman oleh Midtrans. Kamu bisa pilih salah satu metode pembayaran berikut:",
            "data": {
                "buttons": [
                    {"label": "Virtual Account", "payload": "Cara bayar dengan Bank Virtual Account"},
                    {"label": "E-Wallet (GoPay/QRIS)", "payload": "Cara bayar dengan E-Wallet atau ShopeePay"},
                    {"label": "Minimarket", "payload": "Cara bayar lewat Alfamart / Indomaret"}
                ]
            }
        }

    # ===================================================================
    # 6. INTENT: emergency_guide
    # ===================================================================
    # Jangan pemicu emergency protocol jika query tentang laporan/rekap SAR (misal oleh Admin/Penjaga)
    is_report_query = any(k in normalized for k in ["laporan", "dashboard", "rekap", "export", "excel", "unduh", "download"])
    is_emergency = not is_report_query and (any(k in normalized for k in [
        "tersesat", "tim sar", "pos sar", "panic button", "darurat",
        "butuh bantuan", "kecelakaan", "sakit di gunung",
        "cara pakai panic", "tombol darurat", "evakuasi"
    ]) or " sar " in f" {normalized} ")

    if is_emergency:
        return {
            "success": True,
            "source": "static_faq",
            "intent": "emergency_guide",
            "type": "text",
            "message": "PANDUAN DARURAT (EMERGENCY PROTOCOL):\n1. Jangan panik. Tetap diam bersama rombongan Anda di jalur resmi pendakian.\n2. Aktifkan GPS pada ponsel Anda dan buka aplikasi MyHiking.\n3. Tekan tombol merah 'PANIC BUTTON' di pojok kanan bawah chat / layar utama untuk memicu alarm darurat di Pos SAR terdekat.\n4. Tim Ranger & SAR akan segera melacak koordinat GPS terakhir Anda untuk melakukan penyelamatan."
        }

    # ===================================================================
    # 7. INTENT: beginner_tips
    # ===================================================================
    if any(k in normalized for k in [
        "pemula", "tips", "bawa apa saja", "perlengkapan",
        "logistik", "persiapan", "tips mendaki",
        "barang bawaan", "pendaki pemula"
    ]):
        return {
            "success": True,
            "source": "static_faq",
            "intent": "beginner_tips",
            "type": "text",
            "message": "TIPS PENDAKI PEMULA & PERSIAPAN BARANG:\n1. Persiapan Fisik: Olahraga ringan (cardio/jogging) 3-4 kali seminggu sebelum mendaki.\n2. Perlengkapan Wajib: Tas carrier, jaket windproof/waterproof, jas hujan, sleeping bag, matras tidur, sendok-nesting kompor portabel, headlamp, dan obat-obatan pribadi.\n3. Aturan Kelompok: Pastikan mendaki minimal 3 orang dan menyewa jasa Porter/Guide jika belum pernah mendaki jalur tersebut."
        }

    # ===================================================================
    # Jika pesan user tidak cocok dengan filter FAQ, return None (-> Gemini)
    # ===================================================================
    return None
