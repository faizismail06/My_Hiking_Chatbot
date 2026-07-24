"""
Database module for My Hiking Chatbot
=====================================
Database connection and all data-fetching functions.
"""

import pymysql
from config import DB_CONFIG


def get_db_connection():
    """Membuat koneksi ke database MySQL"""
    return pymysql.connect(**DB_CONFIG)


def init_chat_history_table():
    """Membuat tabel chat_histories jika belum ada"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_histories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'pendaki',
                    title VARCHAR(255) DEFAULT NULL,
                    messages LONGTEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_role (user_id, role)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
        conn.commit()
        conn.close()
        print("[OK] Tabel chat_histories siap")
    except Exception as e:
        print(f"[Warning] Gagal membuat tabel chat_histories: {e}")


# ============================================
# DATABASE FETCH FUNCTIONS
# ============================================

def fetch_mountains_data():
    """Mengambil data gunung dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT m.id, m.nama, m.deskripsi, m.ketinggian, m.latitude, m.longitude, m.gambar_gunung,
                       m.province_id, p.name as provinsi
                FROM mountains m
                LEFT JOIN reg_provinces p ON m.province_id = p.id
            """
            cursor.execute(query)
            mountains = cursor.fetchall()
        conn.close()
        return mountains
    except Exception as e:
        print(f"Error fetching mountains: {e}")
        return []


def fetch_trails_data():
    """Mengambil data jalur pendakian dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT r.id, r.nama as nama_jalur, r.jarak, r.deskripsi, r.biaya, r.latitude, r.longitude,
                       r.province_id, r.regency_id, r.district_id, r.village_id,
                       r.tingkat_kesulitan, r.elevasi, r.durasi,
                       m.nama as nama_gunung, m.id as id_gunung, m.ketinggian,
                       p.name as provinsi, rg.name as kabupaten, d.name as kecamatan, v.name as desa
                FROM routes r
                LEFT JOIN mountains m ON r.id_gunung = m.id
                LEFT JOIN reg_provinces p ON r.province_id = p.id
                LEFT JOIN reg_regencies rg ON r.regency_id = rg.id
                LEFT JOIN reg_districts d ON r.district_id = d.id
                LEFT JOIN reg_villages v ON r.village_id = v.id
            """
            cursor.execute(query)
            trails = cursor.fetchall()
        conn.close()
        return trails
    except Exception as e:
        print(f"Error fetching trails: {e}")
        return []


def fetch_rules_data():
    """Mengambil data tata tertib dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT ru.id, ru.description as tata_tertib, 
                       r.nama as nama_jalur, m.nama as nama_gunung
                FROM rules ru
                LEFT JOIN routes r ON ru.jalur_id = r.id
                LEFT JOIN mountains m ON r.id_gunung = m.id
            """
            cursor.execute(query)
            rules = cursor.fetchall()
        conn.close()
        return rules
    except Exception as e:
        print(f"Error fetching rules: {e}")
        return []


def fetch_orders_data():
    """Mengambil data pesanan dari database"""
    try:
        auto_expire_stale_orders()
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT o.id, o.id_gunung, o.id_jalur, o.id_user, 
                       o.tanggal_naik, o.tanggal_turun, o.total_harga_tiket, o.status,
                       o.created_at, o.updated_at,
                       m.nama as nama_gunung, r.nama as nama_jalur,
                       u.name as nama_user, u.email as email_user
                FROM orders o
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                LEFT JOIN users u ON o.id_user = u.id
                ORDER BY o.created_at DESC
            """
            cursor.execute(query)
            orders = cursor.fetchall()
        conn.close()
        return orders
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return []


def fetch_transactions_data():
    """Mengambil data transaksi dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT t.id, t.id_pesanan, t.total_bayar, t.status_pesanan,
                       t.waktu_pembayaran, t.bukti, t.payment_type,
                       t.created_at, t.updated_at,
                       o.id_gunung, o.id_jalur, o.id_user, o.tanggal_naik,
                       m.nama as nama_gunung, r.nama as nama_jalur,
                       u.name as nama_user
                FROM transactions t
                LEFT JOIN orders o ON t.id_pesanan = o.id
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                LEFT JOIN users u ON o.id_user = u.id
                ORDER BY t.created_at DESC
            """
            cursor.execute(query)
            transactions = cursor.fetchall()
        conn.close()
        return transactions
    except Exception as e:
        print(f"Error fetching transactions: {e}")
        return []


def fetch_panic_data():
    """Mengambil data panic/SAR dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT p.id, p.user_id, p.order_id, p.latitude, p.longitude,
                       p.emergency_type, p.description, p.status,
                       p.created_at, p.updated_at,
                       u.name as nama_user, u.phone as telepon_user, u.emergency_phone,
                       o.id_gunung, o.id_jalur, o.tanggal_naik,
                       m.nama as nama_gunung, r.nama as nama_jalur
                FROM panic_requests p
                LEFT JOIN users u ON p.user_id = u.id
                LEFT JOIN orders o ON p.order_id = o.id
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                ORDER BY p.created_at DESC
            """
            cursor.execute(query)
            panics = cursor.fetchall()
        conn.close()
        return panics
    except Exception as e:
        print(f"Error fetching panics: {e}")
        return []


def fetch_users_data():
    """Mengambil data user dari database"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT u.id, u.name, u.email, u.phone, u.address, u.nik,
                       u.emergency_phone, u.date_of_birth, u.level,
                       u.created_at, u.updated_at
                FROM users u
                ORDER BY u.created_at DESC
            """
            cursor.execute(query)
            users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        print(f"Error fetching users: {e}")
        return []


# ============================================
# FILTERED FETCH FUNCTIONS (per-user isolation)
# ============================================

def fetch_trails_by_guard(user_id):
    """Mengambil data jalur yang dikelola oleh penjaga tertentu (routes.user_id)"""
    if not user_id:
        return []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT r.id, r.nama as nama_jalur, r.jarak, r.deskripsi, r.biaya, r.latitude, r.longitude,
                       r.user_id,
                       m.nama as nama_gunung, m.id as id_gunung, m.ketinggian,
                       p.name as provinsi, rg.name as kabupaten, d.name as kecamatan, v.name as desa
                FROM routes r
                LEFT JOIN mountains m ON r.id_gunung = m.id
                LEFT JOIN reg_provinces p ON r.province_id = p.id
                LEFT JOIN reg_regencies rg ON r.regency_id = rg.id
                LEFT JOIN reg_districts d ON r.district_id = d.id
                LEFT JOIN reg_villages v ON r.village_id = v.id
                WHERE r.user_id = %s
            """
            cursor.execute(query, (int(user_id),))
            trails = cursor.fetchall()
        conn.close()
        return trails
    except Exception as e:
        print(f"Error fetching trails for guard {user_id}: {e}")
        return []


def fetch_orders_by_trail_ids(trail_ids):
    """Mengambil data pesanan berdasarkan daftar ID jalur"""
    if not trail_ids:
        return []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ', '.join(['%s'] * len(trail_ids))
            query = f"""
                SELECT o.id, o.id_gunung, o.id_jalur, o.id_user,
                       o.tanggal_naik, o.tanggal_turun, o.total_harga_tiket, o.status,
                       o.created_at, o.updated_at,
                       m.nama as nama_gunung, r.nama as nama_jalur,
                       u.name as nama_user, u.email as email_user
                FROM orders o
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                LEFT JOIN users u ON o.id_user = u.id
                WHERE o.id_jalur IN ({placeholders})
                ORDER BY o.created_at DESC
            """
            cursor.execute(query, tuple(int(tid) for tid in trail_ids))
            orders = cursor.fetchall()
        conn.close()
        return orders
    except Exception as e:
        print(f"Error fetching orders by trail_ids {trail_ids}: {e}")
        return []


def fetch_panics_by_trail_ids(trail_ids):
    """Mengambil data panic/SAR berdasarkan daftar ID jalur"""
    if not trail_ids:
        return []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ', '.join(['%s'] * len(trail_ids))
            query = f"""
                SELECT p.id, p.user_id, p.order_id, p.latitude, p.longitude,
                       p.emergency_type, p.description, p.status,
                       p.created_at, p.updated_at,
                       u.name as nama_user, u.phone as telepon_user, u.emergency_phone,
                       o.id_gunung, o.id_jalur, o.tanggal_naik,
                       m.nama as nama_gunung, r.nama as nama_jalur
                FROM panic_requests p
                LEFT JOIN users u ON p.user_id = u.id
                LEFT JOIN orders o ON p.order_id = o.id
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                WHERE o.id_jalur IN ({placeholders})
                ORDER BY p.created_at DESC
            """
            cursor.execute(query, tuple(int(tid) for tid in trail_ids))
            panics = cursor.fetchall()
        conn.close()
        return panics
    except Exception as e:
        print(f"Error fetching panics by trail_ids {trail_ids}: {e}")
        return []


def fetch_transactions_by_trail_ids(trail_ids):
    """Mengambil data transaksi berdasarkan daftar ID jalur yang dikelola"""
    if not trail_ids:
        return []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            placeholders = ', '.join(['%s'] * len(trail_ids))
            query = f"""
                SELECT t.id, t.id_pesanan, t.total_bayar, t.status_pesanan,
                       t.waktu_pembayaran, t.bukti, t.payment_type,
                       t.created_at, t.updated_at,
                       o.id_gunung, o.id_jalur, o.id_user, o.tanggal_naik,
                       m.nama as nama_gunung, r.nama as nama_jalur,
                       u.name as nama_user
                FROM transactions t
                LEFT JOIN orders o ON t.id_pesanan = o.id
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                LEFT JOIN users u ON o.id_user = u.id
                WHERE o.id_jalur IN ({placeholders})
                ORDER BY t.created_at DESC
            """
            cursor.execute(query, tuple(int(tid) for tid in trail_ids))
            transactions = cursor.fetchall()
        conn.close()
        return transactions
    except Exception as e:
        print(f"Error fetching transactions by trail_ids {trail_ids}: {e}")
        return []


def fetch_routes_by_mountain_name(mountain_name):
    """Mengambil semua jalur (routes) berdasarkan nama gunung (untuk Static FAQ)"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT r.id, r.nama as nama_jalur, r.jarak, r.deskripsi, r.biaya,
                       r.durasi as estimasi_waktu, r.tingkat_kesulitan, r.gambar_jalur,
                       m.nama as nama_gunung, m.id as id_gunung,
                       v.name as desa, d.name as kecamatan, rg.name as kabupaten, p.name as provinsi
                FROM routes r
                INNER JOIN mountains m ON r.id_gunung = m.id
                LEFT JOIN reg_provinces p ON r.province_id = p.id
                LEFT JOIN reg_regencies rg ON r.regency_id = rg.id
                LEFT JOIN reg_districts d ON r.district_id = d.id
                LEFT JOIN reg_villages v ON r.village_id = v.id
                WHERE m.nama LIKE %s
            """
            cursor.execute(query, (f"%{mountain_name}%",))
            routes = cursor.fetchall()
        conn.close()
        return routes
    except Exception as e:
        print(f"Error fetching routes for mountain {mountain_name}: {e}")
        return []


def fetch_route_detail(mountain_name, route_name):
    """Mengambil detail satu rute/jalur spesifik (untuk Static FAQ)"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT r.id, r.nama as nama_jalur, r.jarak, r.deskripsi, r.biaya,
                       r.durasi as estimasi_waktu, r.tingkat_kesulitan, r.gambar_jalur,
                       m.nama as nama_gunung, m.id as id_gunung,
                       v.name as desa, d.name as kecamatan, rg.name as kabupaten, p.name as provinsi
                FROM routes r
                INNER JOIN mountains m ON r.id_gunung = m.id
                LEFT JOIN reg_provinces p ON r.province_id = p.id
                LEFT JOIN reg_regencies rg ON r.regency_id = rg.id
                LEFT JOIN reg_districts d ON r.district_id = d.id
                LEFT JOIN reg_villages v ON r.village_id = v.id
                WHERE m.nama LIKE %s AND r.nama LIKE %s
            """
            cursor.execute(query, (f"%{mountain_name}%", f"%{route_name}%"))
            detail = cursor.fetchone()
        conn.close()
        return detail
    except Exception as e:
        print(f"Error fetching route detail for {mountain_name} via {route_name}: {e}")
        return None


def fetch_rules_by_mountain(mountain_name):
    """Mengambil aturan/tata tertib pendakian untuk gunung tertentu (untuk Static FAQ)"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT ru.description as tata_tertib, r.nama as nama_jalur, m.nama as nama_gunung
                FROM rules ru
                INNER JOIN routes r ON ru.jalur_id = r.id
                INNER JOIN mountains m ON r.id_gunung = m.id
                WHERE m.nama LIKE %s
            """
            cursor.execute(query, (f"%{mountain_name}%",))
            rules = cursor.fetchall()
        conn.close()
        return rules
    except Exception as e:
        print(f"Error fetching rules for {mountain_name}: {e}")
        return []


def auto_expire_stale_orders():
    """Mengubah status pesanan yang belum dibayar dan sudah berusia >= 15 menit menjadi Expired"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE orders o
                LEFT JOIN transactions t ON t.id_pesanan = o.id
                SET o.status = 'Expired',
                    t.payment_status = 'expired',
                    t.status_pesanan = 'Expired'
                WHERE o.status IN ('Waiting Payment', 'pending', 'Booking', 'Menunggu Pembayaran')
                  AND (t.status_pesanan IS NULL OR t.status_pesanan != 'Complete')
                  AND TIMESTAMPDIFF(MINUTE, o.created_at, NOW()) >= 15
            """)
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error auto-expiring stale orders: {e}")


def fetch_orders_by_user(user_id):
    """Mengambil data pesanan milik pendaki tertentu"""
    if not user_id:
        return []
    try:
        auto_expire_stale_orders()
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT o.id, o.id_gunung, o.id_jalur, o.id_user,
                       o.tanggal_naik, o.tanggal_turun, o.total_harga_tiket, o.status,
                       o.created_at, o.updated_at,
                       m.nama as nama_gunung, r.nama as nama_jalur,
                       u.name as nama_user, u.email as email_user
                FROM orders o
                LEFT JOIN mountains m ON o.id_gunung = m.id
                LEFT JOIN routes r ON o.id_jalur = r.id
                LEFT JOIN users u ON o.id_user = u.id
                WHERE o.id_user = %s
                ORDER BY o.created_at DESC
            """
            cursor.execute(query, (int(user_id),))
            orders = cursor.fetchall()
        conn.close()
        return orders
    except Exception as e:
        print(f"Error fetching orders for user {user_id}: {e}")
        return []


def fetch_user_profile(user_id):
    """Mengambil data profil dan tier pengguna dari database"""
    if not user_id:
        return None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            query = "SELECT id, name, email, level, tier FROM users WHERE id = %s"
            cursor.execute(query, (int(user_id),))
            user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        print(f"Error fetching profile for user {user_id}: {e}")
        return None

