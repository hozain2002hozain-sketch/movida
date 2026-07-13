import os
import uuid
from datetime import datetime
from flask import request, current_app
from flask_login import current_user
from extensions import db
from models.log import ActivityLog

def log_action(action, description=None, reference_id=None, reference_type=None):
    try:
        log = ActivityLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            ip_address=get_client_ip(),
            user_agent=request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def allowed_file(filename):
    ALLOWED = {'pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

def save_upload(file, subfolder='documents'):
    if not file or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)
    file.save(filepath)
    # Store a normalized web-friendly path using forward slashes
    return os.path.join(subfolder, filename).replace('\\', '/')
