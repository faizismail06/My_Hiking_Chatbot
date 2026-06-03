"""
Configuration module for My Hiking Chatbot
==========================================
Environment variables, database config, API settings, and shared utilities.
"""

import os
import re
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY and GEMINI_API_KEY != 'your_gemini_api_key_here':
    genai.configure(api_key=GEMINI_API_KEY)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME') or os.getenv('DB_DATABASE', 'myhiking'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'charset': 'utf8mb4',
    'cursorclass': __import__('pymysql').cursors.DictCursor
}

# Laravel API base URL
LARAVEL_API_URL = os.getenv('LARAVEL_API_URL', 'http://127.0.0.1:8000/api')

# Kunci rahasia untuk endpoint CRUD chatbot admin di Laravel.
# Harus sama dengan nilai CHATBOT_SECRET di .env Laravel.
CHATBOT_SECRET = os.getenv('CHATBOT_SECRET', '')

# Directory untuk menyimpan file Excel yang di-generate
EXPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
os.makedirs(EXPORT_DIR, exist_ok=True)


def clean_markdown(text):
    """Membersihkan format markdown dari teks respons Gemini"""
    # Hapus bold (**text** atau __text__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # Hapus italic (*text* atau _text_) - hati-hati dengan bullet points
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    # Hapus heading markers (# ## ### etc)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Hapus backtick code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Bersihkan multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
