"""
My Hiking Chatbot Backend
=========================
Chatbot menggunakan Gemini API dengan RAG (Retrieval Augmented Generation)
untuk menjawab pertanyaan seputar pendakian gunung.

Mendukung 3 role:
- pendaki: informasi gunung + pemesanan tiket via chatbot
- admin: CRUD data + ekspor Excel
- penjaga: SAR dashboard + ekspor Excel

Author: My Hiking Team
Date: March 2024
"""

import os
from flask import Flask
from flask_cors import CORS

from config import GEMINI_API_KEY, EXPORT_DIR
from database import init_chat_history_table
from routes import api_bp

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter app

# Register routes blueprint
app.register_blueprint(api_bp)

# Inisialisasi tabel chat history saat startup
init_chat_history_table()


if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"""
+----------------------------------------------------------+
|          My Hiking Chatbot Server v2.1                   |
+----------------------------------------------------------+
|  URL: http://{host}:{port}                              
|  Debug Mode: {debug}                                      
|  Gemini API: {'Configured' if GEMINI_API_KEY else 'Not Set'}                              
|  Roles: pendaki, admin, penjaga                          
|  Excel Export: {EXPORT_DIR}                              
+----------------------------------------------------------+
    """)
    
    app.run(host=host, port=port, debug=debug)
