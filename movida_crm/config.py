import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'crm-visa-secret-key-2024'

    database_url = os.environ.get('DATABASE_URL') or 'postgresql://postgres.vguwqimunbrghfbukska:xUwMVMfi0K8PGNrz@aws-1-eu-central-1.pooler.supabase.com:5432/postgres'
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if database_url.startswith('postgresql://') and 'sslmode=' not in database_url:
        separator = '&' if '?' in database_url else '?'
        database_url += f'{separator}sslmode=require'
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '10'))
        }
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'}
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_ENABLED = False
