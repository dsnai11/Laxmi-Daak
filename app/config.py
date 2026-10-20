import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'CourierTrackPro-SecretKey-2024!')
    
    # SQLite Database - auto-creates file in instance folder
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///courier_tracker.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.office365.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'CourierTrack Pro')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    SESSION_COOKIE_SAMESITE = 'Lax'
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'CourierTrackPro-SecretKey-2024!')
    
    # SQLite Database - auto-creates file in instance folder
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///courier_tracker.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.office365.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')
    
    COMPANY_NAME = os.environ.get('COMPANY_NAME', 'CourierTrack Pro')
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    UPLOAD_FOLDER = 'app/static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    QR_FOLDER = 'app/static/qr'
    
    # Cookie security settings (OWASP A02:2021)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('BASE_URL', '').startswith('https')
    
    # Remember Me cookie security
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = os.environ.get('BASE_URL', '').startswith('https')
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    # Pushpak Courier API Settings
    PUSHPAK_API_BASE_URL = os.environ.get('PUSHPAK_API_BASE_URL', 'https://www.pushpakcourier.net/v3')
    PUSHPAK_SCBF_ID = os.environ.get('PUSHPAK_SCBF_ID', '')
    PUSHPAK_API_USER = os.environ.get('PUSHPAK_API_USER', '')
    PUSHPAK_API_PASS = os.environ.get('PUSHPAK_API_PASS', '')
