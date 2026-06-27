import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_from_directory, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import User
from utils import log_action

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            from datetime import datetime
            from extensions import db
            user.last_login = datetime.now()
            db.session.commit()
            log_action('login', f'تسجيل دخول: {user.full_name}')
            return redirect(url_for('auth.dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'sales':
        return redirect(url_for('sales.home'))
    elif current_user.role == 'social':
        return redirect(url_for('social.home'))
    elif current_user.role == 'files':
        return redirect(url_for('files.home'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    log_action('logout', f'تسجيل خروج: {current_user.full_name}')
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logo')
def serve_logo():
    logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', 'WhatsApp Image 2026-06-24 at 2.02.14 AM.jpeg')
    if os.path.exists(logo_path):
        return send_from_directory(os.path.dirname(logo_path), os.path.basename(logo_path))
    return '', 404
