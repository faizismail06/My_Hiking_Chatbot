"""
Context Builders for My Hiking Chatbot
=======================================
Build RAG context strings for each role (pendaki, admin, penjaga).
"""

from database import (
    fetch_mountains_data,
    fetch_trails_data,
    fetch_rules_data,
    fetch_orders_data,
    fetch_transactions_data,
    fetch_panic_data,
    fetch_users_data,
)


def build_context_pendaki():
    """Membangun konteks untuk chatbot pendaki"""
    context_parts = []
    
    mountains = fetch_mountains_data()
    trails = fetch_trails_data()
    rules = fetch_rules_data()
    mountains_sorted = []
    trails_sorted = []
    
    # Build mountain context (user-facing: nomor urut, tanpa ID mentah)
    if mountains:
        context_parts.append("=== DATA GUNUNG ===")
        mountains_sorted = sorted(mountains, key=lambda x: x.get('id', 0))
        for idx, m in enumerate(mountains_sorted, start=1):
            mountain_info = f"""
No Gunung: {idx}
Nama Gunung: {m['nama']}
Ketinggian: {m['ketinggian']} mdpl
Lokasi: {m.get('desa', '')}, {m.get('kecamatan', '')}, {m.get('kabupaten', '')}, {m.get('provinsi', '')}
Deskripsi: {m['deskripsi']}
Koordinat: {m.get('latitude', '-')}, {m.get('longitude', '-')}
---"""
            context_parts.append(mountain_info)
    
    # Build trails context (user-facing: nomor urut, tanpa ID mentah)
    if trails:
        context_parts.append("\n=== DATA JALUR PENDAKIAN ===")
        trails_sorted = sorted(trails, key=lambda x: x.get('id', 0))
        for idx, t in enumerate(trails_sorted, start=1):
            trail_info = f"""
No Jalur: {idx}
Nama Jalur: {t['nama_jalur']}
Gunung: {t['nama_gunung']} ({t.get('ketinggian', '-')} mdpl)
Jarak: {t['jarak']} km
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
            context_parts.append(f"ID: {m['id']} | Nama: {m['nama']} | Ketinggian: {m['ketinggian']} mdpl | Lokasi: {m.get('kabupaten', '')}, {m.get('provinsi', '')}")
    
    # Trails
    if trails:
        context_parts.append("\n=== DATA JALUR PENDAKIAN ===")
        for t in trails:
            context_parts.append(f"ID: {t['id']} | Jalur: {t['nama_jalur']} | Gunung: {t['nama_gunung']} (ID: {t['id_gunung']}) | Biaya: Rp {t['biaya']:,} | Jarak: {t['jarak']} km")
    
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


def build_context_penjaga():
    """Membangun konteks untuk chatbot penjaga jalur"""
    context_parts = []
    
    orders = fetch_orders_data()
    panics = fetch_panic_data()
    trails = fetch_trails_data()
    mountains = fetch_mountains_data()
    
    # Active panics (SAR Dashboard)
    active_panics = [p for p in panics if p.get('status') in ('pending', 'active', 'in_progress')]
    if active_panics:
        context_parts.append("⚠️ === PERMINTAAN SAR AKTIF (PERLU PERHATIAN!) ===")
        for p in active_panics:
            context_parts.append(f"🚨 ID: {p['id']} | User: {p.get('nama_user', '-')} | Telepon: {p.get('telepon_user', '-')} | Darurat: {p.get('emergency_phone', '-')} | Gunung: {p.get('nama_gunung', '-')} | Jalur: {p.get('nama_jalur', '-')} | Tipe: {p['emergency_type']} | Deskripsi: {p.get('description', '-')} | Koordinat: {p.get('latitude', '-')}, {p.get('longitude', '-')} | Status: {p['status']} | Waktu: {p['created_at']}")
    else:
        context_parts.append("✅ Tidak ada permintaan SAR aktif saat ini.")
    
    # All panics history
    if panics:
        context_parts.append(f"\n=== RIWAYAT SAR/DARURAT (Total: {len(panics)}) ===")
        for p in panics[:30]:
            context_parts.append(f"ID: {p['id']} | User: {p.get('nama_user', '-')} | Gunung: {p.get('nama_gunung', '-')} | Tipe: {p['emergency_type']} | Status: {p['status']} | Waktu: {p['created_at']}")
    
    # Active orders (pendaki yang sedang di gunung) 
    if orders:
        active_orders = [o for o in orders if o.get('status') in ('confirmed', 'active', 'checked_in')]
        if active_orders:
            context_parts.append(f"\n=== PESANAN AKTIF / PENDAKI DI GUNUNG (Total: {len(active_orders)}) ===")
            for o in active_orders[:30]:
                context_parts.append(f"ID: {o['id']} | User: {o.get('nama_user', '-')} | Gunung: {o.get('nama_gunung', '-')} | Jalur: {o.get('nama_jalur', '-')} | Tanggal Naik: {o['tanggal_naik']} | Tanggal Turun: {o['tanggal_turun']} | Status: {o['status']}")
        
        context_parts.append(f"\n=== SEMUA PESANAN (Total: {len(orders)}, 50 terbaru) ===")
        for o in orders[:50]:
            context_parts.append(f"ID: {o['id']} | User: {o.get('nama_user', '-')} | Gunung: {o.get('nama_gunung', '-')} | Status: {o['status']} | Tanggal: {o['tanggal_naik']}")
    
    # Mountains & Trails for reference
    if mountains:
        context_parts.append("\n=== DATA GUNUNG ===")
        for m in mountains:
            context_parts.append(f"ID: {m['id']} | {m['nama']} | {m['ketinggian']} mdpl")
    
    if trails:
        context_parts.append("\n=== DATA JALUR ===")
        for t in trails:
            context_parts.append(f"ID: {t['id']} | {t['nama_jalur']} | Gunung: {t['nama_gunung']}")
    
    return "\n".join(context_parts)
