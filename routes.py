"""
Flask Routes for My Hiking Chatbot
====================================
All API endpoints registered as a Flask Blueprint.
"""

import os
import json
import traceback
from flask import Blueprint, request, jsonify, send_file

from config import EXPORT_DIR
from database import (
    get_db_connection,
    init_chat_history_table,
    fetch_mountains_data,
    fetch_trails_data,
)
from gemini_engine import get_gemini_response
from static_faq import get_static_response


# Create Blueprint
api_bp = Blueprint('api', __name__)


# ============================================
# CHAT ENDPOINT
# ============================================

@api_bp.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint untuk chatbot (mendukung semua role)"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({
                'success': False,
                'message': 'Pesan tidak boleh kosong'
            }), 400
        
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        role = data.get('role', 'pendaki')  # Default: pendaki
        user_id = data.get('user_id', None)
        selected_member_ids = data.get('selected_member_ids', [])
        selected_member_names = data.get('selected_member_names', [])
        auth_token = data.get('auth_token')
        auth_header = request.headers.get('Authorization', '').strip()

        if not auth_token and auth_header.lower().startswith('bearer '):
            auth_token = auth_header[7:].strip()
        
        if not user_message:
            return jsonify({
                'success': False,
                'message': 'Pesan tidak boleh kosong'
            }), 400
        
        # Validate role
        if role not in ('pendaki', 'admin', 'penjaga'):
            role = 'pendaki'
        
  
        if role == 'pendaki':
            static_response = get_static_response(user_message)
            if static_response:
                print(f"[LOG] [Static FAQ] Intent: '{static_response['intent']}' | Pesan: '{user_message}'")
                return jsonify(static_response)

        
        print(f"[LOG] [Gemini API] Fallback dipicu | Role: '{role}' | Pesan: '{user_message}'")

        # Get response from Gemini
        response = get_gemini_response(
            user_message,
            role,
            user_id,
            conversation_history,
            selected_member_ids=selected_member_ids,
            selected_member_names=selected_member_names,
            auth_token=auth_token,
        )
        
        # Tambahkan metadata pada response Gemini agar struktur konsisten
        response.setdefault('source', 'gemini_api')
        response.setdefault('intent', 'fallback_to_gemini')
        response.setdefault('type', 'text')

        return jsonify(response)
        
    except Exception as e:
        print(f"Chat endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Terjadi kesalahan internal server'
        }), 500


# ============================================
# EXPORT ENDPOINT
# ============================================

@api_bp.route('/api/chat/export/<filename>', methods=['GET'])
def download_export(filename):
    """Endpoint untuk download file Excel yang di-generate"""
    try:
        filepath = os.path.join(EXPORT_DIR, filename)
        if os.path.exists(filepath):
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return jsonify({
                'success': False,
                'message': 'File tidak ditemukan'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================
# INFO & HEALTH ENDPOINTS
# ============================================

@api_bp.route('/api/chat/info', methods=['GET'])
def chat_info():
    """Endpoint untuk mendapatkan info chatbot dan data yang tersedia"""
    try:
        mountains = fetch_mountains_data()
        trails = fetch_trails_data()
        
        return jsonify({
            'success': True,
            'data': {
                'name': 'Hiking Buddy',
                'description': 'Asisten virtual untuk pendakian gunung',
                'available_mountains': [m['nama'] for m in mountains],
                'available_trails': [f"{t['nama_jalur']} ({t['nama_gunung']})" for t in trails],
                'capabilities': [
                    'Informasi gunung (ketinggian, lokasi, deskripsi)',
                    'Informasi jalur pendakian (jarak, biaya, basecamp)',
                    'Tata tertib dan peraturan pendakian',
                    'Tips dan saran pendakian',
                    'Saran jalur berdasarkan preferensi',
                    'Pemesanan tiket pendakian via chat',
                ],
                'supported_roles': ['pendaki', 'admin', 'penjaga'],
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_bp.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint untuk cek kesehatan server"""
    from config import GEMINI_API_KEY

    db_status = 'connected'
    try:
        conn = get_db_connection()
        conn.close()
    except:
        db_status = 'disconnected'
    
    gemini_status = 'configured' if GEMINI_API_KEY and GEMINI_API_KEY != 'your_gemini_api_key_here' else 'not_configured'
    
    return jsonify({
        'status': 'ok',
        'database': db_status,
        'gemini_api': gemini_status
    })


@api_bp.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'name': 'My Hiking Chatbot API',
        'version': '2.1.0',
        'endpoints': {
            'POST /api/chat': 'Kirim pesan ke chatbot (role: pendaki, admin, penjaga)',
            'GET /api/chat/info': 'Info chatbot dan data tersedia',
            'GET /api/chat/export/<filename>': 'Download file Excel hasil ekspor',
            'GET /api/chat/history?user_id=&role=': 'Daftar riwayat chat',
            'GET /api/chat/history/<id>': 'Detail riwayat chat',
            'POST /api/chat/history': 'Simpan riwayat chat',
            'DELETE /api/chat/history/<id>': 'Hapus riwayat chat',
            'GET /api/health': 'Cek kesehatan server',
        }
    })


# ============================================
# CHAT HISTORY ENDPOINTS
# ============================================

@api_bp.route('/api/chat/history', methods=['GET'])
def get_chat_histories():
    """Mendapatkan daftar riwayat chat user"""
    try:
        init_chat_history_table()
        user_id = request.args.get('user_id')
        role = request.args.get('role', 'pendaki')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'user_id diperlukan'}), 400
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, role, title, created_at, updated_at
                FROM chat_histories
                WHERE user_id = %s AND role = %s
                ORDER BY updated_at DESC
                LIMIT 50
            """, (user_id, role))
            histories = cursor.fetchall()
        conn.close()
        
        # Convert to serializable format
        for h in histories:
            h['created_at'] = str(h['created_at'])
            h['updated_at'] = str(h['updated_at'])
        
        return jsonify({'success': True, 'data': histories})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/api/chat/history/<int:history_id>', methods=['GET'])
def get_chat_history(history_id):
    """Mendapatkan detail riwayat chat berdasarkan ID"""
    try:
        init_chat_history_table()
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, role, title, messages, created_at, updated_at
                FROM chat_histories WHERE id = %s
            """, (history_id,))
            history = cursor.fetchone()
        conn.close()
        
        if not history:
            return jsonify({'success': False, 'message': 'Riwayat tidak ditemukan'}), 404
        
        history['messages'] = json.loads(history['messages'])
        history['created_at'] = str(history['created_at'])
        history['updated_at'] = str(history['updated_at'])
        
        return jsonify({'success': True, 'data': history})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/api/chat/history', methods=['POST'])
def save_chat_history():
    """Simpan atau update riwayat chat"""
    try:
        init_chat_history_table()
        data = request.get_json()
        
        user_id = data.get('user_id')
        role = data.get('role', 'pendaki')
        messages = data.get('messages', [])
        history_id = data.get('history_id')
        title = data.get('title')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'user_id diperlukan'}), 400
        
        if not messages:
            return jsonify({'success': False, 'message': 'messages tidak boleh kosong'}), 400
        
        # Auto-generate title dari pesan pertama user
        if not title:
            for msg in messages:
                if msg.get('isUser', False):
                    title = msg.get('message', '')[:100]
                    break
            if not title:
                title = 'Chat Baru'
        
        messages_json = json.dumps(messages, ensure_ascii=False, default=str)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if history_id:
                # Update existing
                cursor.execute("""
                    UPDATE chat_histories 
                    SET messages = %s, title = %s, updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                """, (messages_json, title, history_id, user_id))
                result_id = history_id
            else:
                # Create new
                cursor.execute("""
                    INSERT INTO chat_histories (user_id, role, title, messages, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (user_id, role, title, messages_json))
                result_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Riwayat chat berhasil disimpan',
            'history_id': result_id,
        }), 201 if not history_id else 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/api/chat/history/<int:history_id>', methods=['DELETE'])
def delete_chat_history(history_id):
    """Hapus riwayat chat"""
    try:
        init_chat_history_table()
        user_id = request.args.get('user_id')
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if user_id:
                cursor.execute("DELETE FROM chat_histories WHERE id = %s AND user_id = %s", (history_id, user_id))
            else:
                cursor.execute("DELETE FROM chat_histories WHERE id = %s", (history_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Riwayat chat berhasil dihapus'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
