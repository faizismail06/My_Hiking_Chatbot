"""
Context Builders for My Hiking Chatbot
=======================================
Build RAG context strings for each role (pendaki, admin, penjaga).
Each context builder now accepts user_id to ensure data isolation:
  - Penjaga: only sees data for their own trail(s)
  - Pendaki: only sees public data (mountains, trails, rules)
  - Admin: sees all data (unchanged)
"""

from database import (
    fetch_mountains_data,
    fetch_trails_data,
    fetch_rules_data,
    fetch_orders_data,
    fetch_transactions_data,
    fetch_panic_data,
    fetch_users_data,
    fetch_trails_by_guard,
    fetch_orders_by_trail_ids,
    fetch_panics_by_trail_ids,
    fetch_orders_by_user,
    fetch_user_profile,
)


def build_context_pendaki(user_id=None):
    """Membangun konteks untuk chatbot pendaki.
    
    Konteks berisi data publik (gunung, jalur, rules, DSS difficulty metrics) serta
    data pesanan/tiket dan profil tier milik user tersebut jika user sedang login.
    """
    context_parts = []
    
    mountains = fetch_mountains_data()
    trails = fetch_trails_data()
    rules = fetch_rules_data()
    mountains_sorted = []
    trails_sorted = []
    
    # Build user profile and orders context if user_id is provided
    if user_id:
        user_profile = fetch_user_profile(user_id)
        if user_profile:
            raw_tier = user_profile.get('tier')
            tier_name = str(raw_tier).title() if raw_tier else "Pemula"
            context_parts.append("=== PROFIL DSS PENGGUNA TERHUBUNG (AKUN ANDA) ===")
            context_parts.append(f"Nama Pengguna: {user_profile.get('name', 'Pendaki')}")
            context_parts.append(f"Tingkat Pengalaman (Tier Pendaki Anda): {tier_name}")
            context_parts.append("Instruksi AI: Gunakan Tier Pendaki Anda di atas untuk menghitung Risk Gap dan memberikan rekomendasi personal saat user bertanya 'apakah cocok untuk SAYA'.\n")

        user_orders = fetch_orders_by_user(user_id)
        if user_orders:
            context_parts.append("=== DATA PESANAN & JADWAL PENDAKIAN ANDA ===")
            for idx, o in enumerate(user_orders, start=1):
                order_info = f"""
Tiket #{idx} (Kode Booking: #{o['id']}):
- Gunung: {o.get('nama_gunung', '-')}
- Jalur: {o.get('nama_jalur', '-')}
- Tanggal Naik: {o['tanggal_naik']}
- Tanggal Turun: {o.get('tanggal_turun', '-')}
- Total Biaya: Rp {o['total_harga_tiket']:,}
- Status Tiket/Booking: {o['status']}
---"""
                context_parts.append(order_info)
        else:
            context_parts.append("=== DATA PESANAN & JADWAL PENDAKIAN ANDA ===")
            context_parts.append("Anda belum memiliki riwayat pemesanan/tiket pendakian di aplikasi MyHiking.")

    # Build mountain context (user-facing: nomor urut, tanpa ID mentah)
    if mountains:
        context_parts.append("\n=== DATA GUNUNG ===")
        mountains_sorted = sorted(mountains, key=lambda x: x.get('id', 0))
        for idx, m in enumerate(mountains_sorted, start=1):
            mountain_info = f"""
No Gunung: {idx}
Nama Gunung: {m['nama']}
Ketinggian: {m['ketinggian']} mdpl
Provinsi: {m.get('provinsi', '')}
Deskripsi: {m['deskripsi']}
Koordinat: {m.get('latitude', '-')}, {m.get('longitude', '-')}
---"""
            context_parts.append(mountain_info)
    
    # Build trails context (user-facing: nomor urut, tanpa ID mentah + DSS Difficulty & Suitability)
    if trails:
        context_parts.append("\n=== DATA JALUR PENDAKIAN & KESESUAIAN DSS ===")
        trails_sorted = sorted(trails, key=lambda x: x.get('id', 0))
        for idx, t in enumerate(trails_sorted, start=1):
            diff_raw = str(t.get('tingkat_kesulitan') or '').lower()
            if not diff_raw or diff_raw == 'none':
                dist = float(t.get('jarak') or 0)
                elev = float(t.get('elevasi') or 0)
                dur = float(t.get('durasi') or 0)
                norm_dist = min(1.0, dist / 20.0)
                norm_elev = min(1.0, elev / 3500.0)
                norm_dur = min(1.0, dur / 14.0)
                demand = (norm_elev * 0.40) + (norm_dist * 0.35) + (norm_dur * 0.25)
                score = 1.0 + (demand * 3.0)
                if score < 1.75:
                    diff_label = "Mudah"
                elif score < 2.50:
                    diff_label = "Sedang"
                elif score < 3.25:
                    diff_label = "Sulit"
                else:
                    diff_label = "Sangat Sulit"
            else:
                diff_label = diff_raw.replace('_', ' ').title()

            # Formulasi Kesesuaian DSS (Risk Gap & Acuan Pemula)
            diff_lower = diff_label.lower()
            if diff_lower == "mudah":
                kesesuaian_dss = "Sangat cocok & aman untuk pendaki Pemula, Menengah, dan Mahir (Risk Gap = 0)."
            elif diff_lower == "sedang":
                kesesuaian_dss = "Cukup cocok untuk pendaki Pemula yang memiliki fisik sehat/prima (Risk Gap = +1), serta sangat cocok untuk pendaki Menengah & Mahir."
            elif diff_lower in ["sulit", "sangat sulit"]:
                kesesuaian_dss = "Kurang cocok / Berisiko Tinggi untuk Pemula (Risk Gap >= +2). Disarankan untuk pendaki Menengah/Mahir atau didampingi pendaki berpengalaman."
            else:
                kesesuaian_dss = "Dapat dicoba oleh pendaki dengan fisik dan persiapan yang memadai."

            trail_info = f"""
No Jalur: {idx}
Nama Jalur: {t['nama_jalur']}
Gunung: {t['nama_gunung']} ({t.get('ketinggian', '-')} mdpl)
Jarak: {t['jarak']} km
Elevasi: {t.get('elevasi', '-')} m
Durasi Estimasi: ~{t.get('durasi', '-')} Jam
Tingkat Kesulitan DSS: {diff_label}
Kesesuaian Pendaki Pemula & Rekomendasi DSS: {kesesuaian_dss}
Biaya: Rp {t['biaya']:,}
Lokasi Basecamp: {t.get('desa', '')}, {t.get('kecamatan', '')}, {t.get('kabupaten', '')}, {t.get('provinsi', '')}
Deskripsi: {t.get('deskripsi', '-')}
---"""
            context_parts.append(trail_info)

        # Mapping internal untuk function calling (jangan ditampilkan ke user)
        context_parts.append("\n=== INTERNAL_ONLY_MAPPINGS (JANGAN DITAMPILKAN KE USER) ===")
        for idx, m in enumerate(mountains_sorted, start=1):
            context_parts.append(f"MAP_GUNUNG: nomor {idx} -> id_gunung {m['id']} ({m['nama']})")
        for idx, t in enumerate(trails_sorted, start=1):
            context_parts.append(f"MAP_JALUR: nomor {idx} -> id_jalur {t['id']} ({t['nama_jalur']})")
    
    # Build rules context
    if rules:
        context_parts.append("\n=== DATA TATA TERTIB ===")
        for r in rules:
            rule_info = f"""
Jalur: {r['nama_jalur']} - Gunung {r['nama_gunung']}
Tata Tertib: {r['tata_tertib']}
---"""
            context_parts.append(rule_info)
    
    return "\n".join(context_parts)



def build_context_admin():
    """Membangun konteks untuk chatbot admin"""
    context_parts = []
    
    mountains = fetch_mountains_data()
    trails = fetch_trails_data()
    orders = fetch_orders_data()
    transactions = fetch_transactions_data()
    users = fetch_users_data()
    panics = fetch_panic_data()
    
    # Mountains
    if mountains:
        context_parts.append("=== DATA GUNUNG ===")
        for m in mountains:
            context_parts.append(f"ID: {m['id']} | Nama: {m['nama']} | Ketinggian: {m['ketinggian']} mdpl | Provinsi: {m.get('provinsi', '')}")
    
    # Trails
    if trails:
        context_parts.append("\n=== DATA JALUR PENDAKIAN ===")
        for t in trails:
            context_parts.append(f"ID Jalur: {t['id']} | Jalur: {t['nama_jalur']} | Gunung: {t['nama_gunung']} | ID Gunung: {t['id_gunung']} | Biaya: Rp {t['biaya']:,} | Jarak: {t['jarak']} km | Lokasi: {t.get('kabupaten', '')}, {t.get('kecamatan', '')}, {t.get('desa', '')}, {t.get('provinsi', '')}")

    
    # Orders (recent 50)
    if orders:
        context_parts.append(f"\n=== DATA PESANAN (Total: {len(orders)}, Ditampilkan 50 terbaru) ===")
        for o in orders[:50]:
            context_parts.append(f"ID: {o['id']} | User: {o.get('nama_user', '-')} | Gunung: {o.get('nama_gunung', '-')} | Jalur: {o.get('nama_jalur', '-')} | Tanggal Naik: {o['tanggal_naik']} | Status: {o['status']} | Total: Rp {o['total_harga_tiket']:,}")
    
    # Transactions (recent 50)
    if transactions:
        context_parts.append(f"\n=== DATA TRANSAKSI (Total: {len(transactions)}, Ditampilkan 50 terbaru) ===")
        for t in transactions[:50]:
            context_parts.append(f"ID: {t['id']} | Pesanan: {t['id_pesanan']} | User: {t.get('nama_user', '-')} | Total: Rp {t['total_bayar']:,} | Status: {t['status_pesanan']} | Pembayaran: {t.get('waktu_pembayaran', '-')}")
    
    # Users
    if users:
        context_parts.append(f"\n=== DATA USER (Total: {len(users)}) ===")
        for u in users[:50]:
            context_parts.append(f"ID: {u['id']} | Nama: {u['name']} | Email: {u['email']} | Phone: {u.get('phone', '-')} | Level: {u.get('level', '-')}")
    
    # Panics/SAR
    if panics:
        context_parts.append(f"\n=== DATA SAR/DARURAT (Total: {len(panics)}) ===")
        for p in panics:
            context_parts.append(f"ID: {p['id']} | User: {p.get('nama_user', '-')} | Gunung: {p.get('nama_gunung', '-')} | Jalur: {p.get('nama_jalur', '-')} | Tipe: {p['emergency_type']} | Status: {p['status']} | Waktu: {p['created_at']}")
    
    return "\n".join(context_parts)


def build_context_penjaga(user_id=None):
    """Membangun konteks untuk chatbot penjaga jalur.
    
    PENTING: Hanya menampilkan data yang terkait dengan jalur
    yang dikelola oleh penjaga yang sedang login (berdasarkan user_id).
    Penjaga A tidak boleh melihat data penjaga B.
    """
    context_parts = []
    
    # Ambil jalur yang dikelola penjaga ini
    guard_trails = fetch_trails_by_guard(user_id) if user_id else []
    guard_trail_ids = [t['id'] for t in guard_trails] if guard_trails else []
    
    if not guard_trails:
        context_parts.append("⚠️ Anda belum ditugaskan ke jalur manapun. Data pesanan dan SAR tidak tersedia.")
        # Tetap tampilkan data gunung & jalur umum untuk referensi
        mountains = fetch_mountains_data()
        trails = fetch_trails_data()
        if mountains:
            context_parts.append("\n=== DATA GUNUNG ===")
            for m in mountains:
                context_parts.append(f"ID: {m['id']} | {m['nama']} | {m['ketinggian']} mdpl")
        if trails:
            context_parts.append("\n=== DATA JALUR ===")
            for t in trails:
                context_parts.append(f"ID: {t['id']} | {t['nama_jalur']} | Gunung: {t['nama_gunung']}")
        return "\n".join(context_parts)
    
    # Info jalur yang dikelola
    context_parts.append("=== JALUR YANG ANDA KELOLA ===")
    for t in guard_trails:
        context_parts.append(
            f"ID: {t['id']} | {t['nama_jalur']} | Gunung: {t['nama_gunung']} "
            f"({t.get('ketinggian', '-')} mdpl) | Biaya: Rp {t['biaya']:,}"
        )
    
    # Ambil data yang HANYA terkait jalur penjaga ini
    orders = fetch_orders_by_trail_ids(guard_trail_ids)
    panics = fetch_panics_by_trail_ids(guard_trail_ids)
    
    # Active panics (SAR Dashboard) — hanya untuk jalur penjaga ini
    active_panics = [p for p in panics if p.get('status') in ('pending', 'active', 'in_progress')]
    if active_panics:
        context_parts.append("\n⚠️ === PERMINTAAN SAR AKTIF (PERLU PERHATIAN!) ===")
        for p in active_panics:
            context_parts.append(f"🚨 ID: {p['id']} | User: {p.get('nama_user', '-')} | Telepon: {p.get('telepon_user', '-')} | Darurat: {p.get('emergency_phone', '-')} | Gunung: {p.get('nama_gunung', '-')} | Jalur: {p.get('nama_jalur', '-')} | Tipe: {p['emergency_type']} | Deskripsi: {p.get('description', '-')} | Koordinat: {p.get('latitude', '-')}, {p.get('longitude', '-')} | Status: {p['status']} | Waktu: {p['created_at']}")
    else:
        context_parts.append("\n✅ Tidak ada permintaan SAR aktif saat ini di jalur Anda.")
    
    # All panics history — hanya untuk jalur penjaga ini
    if panics:
        context_parts.append(f"\n=== RIWAYAT SAR/DARURAT DI JALUR ANDA (Total: {len(panics)}) ===")
        for p in panics[:30]:
            context_parts.append(f"ID: {p['id']} | User: {p.get('nama_user', '-')} | Gunung: {p.get('nama_gunung', '-')} | Tipe: {p['emergency_type']} | Status: {p['status']} | Waktu: {p['created_at']}")
    
    # Active orders (pendaki yang sedang di gunung) — hanya untuk jalur penjaga ini
    if orders:
        active_orders = [o for o in orders if o.get('status') in ('confirmed', 'active', 'checked_in', 'Booking', 'Sedang Mendaki')]
        if active_orders:
            context_parts.append(f"\n=== PESANAN AKTIF / PENDAKI DI JALUR ANDA (Total: {len(active_orders)}) ===")
            for o in active_orders[:30]:
                context_parts.append(f"ID: {o['id']} | User: {o.get('nama_user', '-')} | Gunung: {o.get('nama_gunung', '-')} | Jalur: {o.get('nama_jalur', '-')} | Tanggal Naik: {o['tanggal_naik']} | Tanggal Turun: {o['tanggal_turun']} | Status: {o['status']}")
        
        context_parts.append(f"\n=== SEMUA PESANAN DI JALUR ANDA (Total: {len(orders)}, 50 terbaru) ===")
        for o in orders[:50]:
            context_parts.append(f"ID: {o['id']} | User: {o.get('nama_user', '-')} | Gunung: {o.get('nama_gunung', '-')} | Status: {o['status']} | Tanggal: {o['tanggal_naik']}")
    
    # Mountains & Trails for reference (semua data — ini data publik)
    mountains = fetch_mountains_data()
    if mountains:
        context_parts.append("\n=== DATA GUNUNG ===")
        for m in mountains:
            context_parts.append(f"ID: {m['id']} | {m['nama']} | {m['ketinggian']} mdpl")
    
    all_trails = fetch_trails_data()
    if all_trails:
        context_parts.append("\n=== DATA JALUR ===")
        for t in all_trails:
            context_parts.append(f"ID: {t['id']} | {t['nama_jalur']} | Gunung: {t['nama_gunung']}")
    
    return "\n".join(context_parts)
