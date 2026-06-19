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
    fetch_routes_by_mountain_name,
    fetch_route_detail,
    fetch_rules_by_mountain,
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
    """Mengekstraksi nama gunung yang ada di dalam database dari input user"""
    for m in all_mountains:
        name_lower = m['nama'].lower()
        clean_name = name_lower.replace("gunung ", "").strip()

        # Cek jika nama lengkap atau nama pendek gunung ada di teks
        if name_lower in normalized_text or clean_name in normalized_text:
            return m['nama']
    return None


def extract_route_name(normalized_text, routes):
    """Mengekstraksi nama jalur pendakian dari input user"""
    # Bersihkan input dari kata-kata umum
    clean_text = normalized_text.replace("via", "").replace("jalur", "").strip()

    for r in routes:
        trail_name_lower = r['nama_jalur'].lower().replace("via", "").replace("jalur", "").strip()
        if trail_name_lower in clean_text:
            return r['nama_jalur']
    return None


def get_static_response(user_message):
    """
    Fungsi utama untuk mengevaluasi apakah input user masuk kategori FAQ.

    Return:
        dict: Response JSON jika cocok dengan FAQ
        None: Jika tidak cocok, agar fallback ke Gemini API
    """
    normalized = normalize_text(user_message)

    # Bypass static FAQ untuk permintaan pemesanan tiket / booking agar diproses oleh Gemini API.
    # Namun, jika mengandung kata pembatalan/cancel/refund, jangan di-bypass agar tetap ditangani oleh intent refund_policy.
    is_refund_query = any(k in normalized for k in ["cancel", "batal", "refund", "pembatalan", "batalin", "uang kembali"])
    if not is_refund_query:
        if any(k in normalized for k in [
            "pesan tiket", "pesan tiker", "booking", "book tiket",
            "beli tiket", "order tiket", "pesan tempat", "pesan kuota"
        ]):
            return None

    all_mountains = fetch_mountains_data()

    # Ekstraksi nama gunung dari pesan (digunakan di beberapa intent)
    extracted_mountain = extract_mountain_name(normalized, all_mountains)

    # ===================================================================
    # 1. INTENT: list_mountains
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
    # 2. INTENT: list_routes_by_mountain / route_detail
    # ===================================================================
    is_route_query = any(k in normalized for k in [
        "jalur", "rute", "via", "estimasi", "lama pendakian",
        "biaya mendaki", "list jalur", "daftar jalur",
        "jalur apa saja", "ada berapa jalur", "jalur yang tersedia",
        "jalur tersedia", "rute pendakian", "ada rute apa"
    ])

    if is_route_query or extracted_mountain:
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

            # Cek jika menanyakan detail jalur spesifik
            extracted_route = extract_route_name(normalized, routes)
            if extracted_route:
                detail = fetch_route_detail(extracted_mountain, extracted_route)
                if detail:
                    basecamp_parts = []
                    if detail.get('desa'):
                        basecamp_parts.append(detail['desa'])
                    if detail.get('kecamatan'):
                        basecamp_parts.append(detail['kecamatan'])
                    if detail.get('kabupaten'):
                        basecamp_parts.append(detail['kabupaten'])
                    basecamp_str = ", ".join(basecamp_parts) if basecamp_parts else "Tidak tersedia"

                    estimasi = f"{detail['estimasi_waktu']} jam" if detail.get('estimasi_waktu') else "Belum tersedia"

                    return {
                        "success": True,
                        "source": "static_faq",
                        "intent": "route_detail",
                        "type": "route_cards",
                        "message": f"Ini dia info lengkap jalur {detail['nama_gunung']} {detail['nama_jalur']}! Langsung pesan tiket kalau kamu tertarik ya.",
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
            # User bertanya tentang jalur tapi tidak menyebutkan nama gunung
            # Tampilkan daftar gunung agar user memilih gunung terlebih dahulu
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
    # 3. INTENT: hiking_rules
    # ===================================================================
    if any(k in normalized for k in [
        "aturan", "tata tertib", "peraturan", "bolehkah mendaki",
        "dilarang", "syarat mendaki", "ketentuan mendaki"
    ]):
        # Jika user menyebutkan nama gunung, ambil aturan khusus gunung tersebut
        if extracted_mountain:
            rules_data = fetch_rules_by_mountain(extracted_mountain)
            if rules_data:
                rule_text = f"TATA TERTIB PENDAKIAN {extracted_mountain.upper()}:\n"
                for idx, r in enumerate(rules_data, 1):
                    rule_text += f"{idx}. [Jalur {r['nama_jalur']}]: {r['tata_tertib']}\n"
                rule_text += "\nOh iya, aturan detail lainnya bisa saja berbeda di tiap basecamp. Biar lebih pasti, jangan lupa cek tata tertib lengkap masing-masing gunung di halaman info gunung (Trail Screen) ya!"
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
            "message": "ATURAN UMUM PENDAKIAN MYHIKING:\n1. Pendaki wajib membawa kartu identitas asli (KTP/SIM/Paspor) saat check-in.\n2. Wajib registrasi online dan melakukan pembayaran e-tiket sebelum waktu pendakian.\n3. Dilarang membuang sampah sembarangan dan wajib membawa sampah kembali ke basecamp.\n4. Tidak diperkenankan merusak flora, fauna, dan situs cagar alam di sepanjang jalur pendakian.\n\nSetiap gunung juga punya aturan khusus masing-masing, lho. Biar pendakianmu berjalan lancar, yuk cek detail tata tertib lengkap tiap gunung di halaman info gunung (Trail Screen) ya!"
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

    if any(k in normalized for k in [
        "bayar", "metode pembayaran", "pembayaran", "midtrans",
        "cara bayar", "bayarnya lewat apa", "bisa pakai ewallet"
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
    is_emergency = any(k in normalized for k in [
        "tersesat", "tim sar", "pos sar", "panic button", "darurat",
        "butuh bantuan", "kecelakaan", "sakit di gunung",
        "cara pakai panic", "tombol darurat", "evakuasi"
    ]) or " sar " in f" {normalized} "

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
