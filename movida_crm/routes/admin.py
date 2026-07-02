from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
from extensions import db
from models import User, Customer, SocialNumber, SocialAssignment
from models.contract import Contract, Payment
from models.interview import Interview
from models.log import ActivityLog
from utils import log_action, save_upload

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('هذه الصفحة للمديرين فقط', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)

@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'sales_count': User.query.filter_by(role='sales', is_active=True).count(),
        'social_count': User.query.filter_by(role='social', is_active=True).count(),
        'files_count': User.query.filter_by(role='files', is_active=True).count(),
        'total_customers': Customer.query.count(),
        'total_contracts': Contract.query.count(),
        'closed_contracts': Contract.query.filter_by(status='closed').count(),
        'accepted_visas': Contract.query.filter_by(visa_status='accepted').count(),
        'rejected_visas': Contract.query.filter_by(visa_status='rejected').count(),
    }
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_logs=recent_logs)

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        email = request.form.get('email', '').strip() or None
        phone = request.form.get('phone', '').strip() or None

        if not username or not full_name or not password or not role:
            flash('يرجى ملء جميع الحقول المطلوبة', 'danger')
            return render_template('admin/add_user.html')

        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود مسبقاً', 'danger')
            return render_template('admin/add_user.html')

        user = User(username=username, full_name=full_name, role=role, email=email, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        log_action('add_user', f'إضافة مستخدم: {full_name} ({role})', user.id, 'user')
        flash(f'تم إضافة المستخدم {full_name}', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/add_user.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name).strip()
        user.role = request.form.get('role', user.role)
        user.email = request.form.get('email', '').strip() or None
        user.phone = request.form.get('phone', '').strip() or None
        new_pass = request.form.get('password', '')
        if new_pass:
            user.set_password(new_pass)
        db.session.commit()
        log_action('edit_user', f'تعديل مستخدم: {user.full_name}', user_id, 'user')
        flash('تم تحديث بيانات المستخدم', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/edit_user.html', user=user)

@admin_bp.route('/users/toggle/<int:user_id>', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('لا يمكنك إيقاف حسابك', 'danger')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'تفعيل' if user.is_active else 'إيقاف'
    flash(f'تم {status} المستخدم {user.full_name}', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('لا يمكنك حذف حسابك', 'danger')
        return redirect(url_for('admin.users'))

    if user.role == 'sales':
        related_customers = Customer.query.filter_by(sales_employee_id=user.id).count()
        related_assignments = SocialAssignment.query.filter_by(sales_employee_id=user.id).count()
        if related_customers > 0 or related_assignments > 0:
            flash('لا يمكن حذف موظف السيلز لأنه مرتبط بعملاء أو أرقام سوشيال.', 'danger')
            return redirect(url_for('admin.users'))

    if user.role == 'social':
        related_numbers = SocialNumber.query.filter_by(employee_id=user.id).count()
        if related_numbers > 0:
            flash('لا يمكن حذف موظف السوشيال ميديا لأنه مرتبط بأرقام.', 'danger')
            return redirect(url_for('admin.users'))

    if user.role == 'files':
        related_contracts = Contract.query.filter_by(files_employee_id=user.id).count()
        if related_contracts > 0:
            flash('لا يمكن حذف موظف الملفات لأنه مرتبط بملفات.', 'danger')
            return redirect(url_for('admin.users'))

    log_action('delete_user', f'حذف مستخدم: {user.full_name}', user_id, 'user')
    db.session.delete(user)
    db.session.commit()
    flash(f'تم حذف المستخدم {user.full_name}', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/reports')
@admin_required
def reports():
    from_date_str = request.args.get('from_date', '')
    to_date_str = request.args.get('to_date', '')
    report_type = request.args.get('type', 'sales')

    from_date = datetime.strptime(from_date_str, '%Y-%m-%d') if from_date_str else None
    to_date = datetime.strptime(to_date_str, '%Y-%m-%d') if to_date_str else None

    data = {}
    search_performed = bool(request.args)
    data['search_performed'] = search_performed
    sales_users = User.query.filter_by(role='sales', is_active=True).order_by(User.full_name).all()

    if search_performed:
        if report_type == 'sales':
            q = Customer.query
            if from_date:
                q = q.filter(Customer.created_at >= from_date)
            if to_date:
                q = q.filter(Customer.created_at <= to_date)
            data['customers'] = q.all()

        elif report_type == 'social':
            q = SocialNumber.query
            if from_date:
                q = q.filter(SocialNumber.added_at >= from_date)
            if to_date:
                q = q.filter(SocialNumber.added_at <= to_date)
            data['numbers'] = q.all()

        elif report_type == 'files':
            q = Contract.query
            if from_date:
                q = q.filter(Contract.created_at >= from_date)
            if to_date:
                q = q.filter(Contract.created_at <= to_date)
            data['contracts'] = q.all()

        elif report_type == 'payments':
            q = Payment.query.filter_by(deleted=False)
            if from_date:
                q = q.filter(Payment.payment_date >= from_date)
            if to_date:
                q = q.filter(Payment.payment_date <= to_date)
            data['payments'] = q.all()
            data['total'] = sum(p.amount for p in data['payments'])

        elif report_type == 'visas':
            q = Contract.query
            if from_date:
                q = q.filter(Contract.created_at >= from_date)
            if to_date:
                q = q.filter(Contract.created_at <= to_date)
            contracts = q.all()
            data['accepted'] = [c for c in contracts if c.visa_status == 'accepted']
            data['rejected'] = [c for c in contracts if c.visa_status == 'rejected']
            data['under_review'] = [c for c in contracts if c.visa_status == 'under_review']

            # Sales stats: interviews and contracts per sales employee
            sales_stats = []
            for u in sales_users:
                interviews_count = Interview.query.filter(
                    db.or_(
                        Interview.sales_employee_name == u.full_name,
                        Interview.employee_id == u.id
                    )
                ).count()
                contracts_count = Contract.query.filter(Contract.sales_employee_name == u.full_name).count()
                sales_stats.append({'user': u, 'interviews': interviews_count, 'contracts': contracts_count})
            data['sales_stats'] = sales_stats

        elif report_type == 'sales_employees':
            selected_sales = None
            sales_employee_id = request.args.get('sales_employee', 'all')
            if sales_employee_id and sales_employee_id != 'all':
                try:
                    selected_sales = User.query.filter_by(id=int(sales_employee_id), role='sales', is_active=True).first()
                except ValueError:
                    selected_sales = None

            sales_rows = []
            selected_summary = None
            for u in sales_users:
                if selected_sales and u.id != selected_sales.id:
                    continue

                customer_q = Customer.query.filter(Customer.sales_employee_id == u.id)
                sales_interview_q = Interview.query.filter(
                    db.or_(
                        Interview.sales_employee_name == u.full_name,
                        Interview.employee_id == u.id
                    )
                )
                contract_q = Contract.query.filter(
                    db.or_(
                        Contract.sales_employee_name == u.full_name,
                        Contract.client_phone.in_(
                            db.session.query(Customer.phone).filter(Customer.sales_employee_id == u.id)
                        )
                    )
                )

                if from_date:
                    customer_q = customer_q.filter(Customer.created_at >= from_date)
                    sales_interview_q = sales_interview_q.filter(Interview.created_at >= from_date)
                    contract_q = contract_q.filter(Contract.created_at >= from_date)
                if to_date:
                    customer_q = customer_q.filter(Customer.created_at <= to_date)
                    sales_interview_q = sales_interview_q.filter(Interview.created_at <= to_date)
                    contract_q = contract_q.filter(Contract.created_at <= to_date)

                scheduled_appointments = customer_q.filter(Customer.interview_date.isnot(None)).count()
                attended_interviews = customer_q.filter(
                    Customer.interview_status == 'attended',
                    Customer.interview_result == 'interview'
                ).count()
                attended_contracts = contract_q.count()
                missed_appointments = customer_q.filter(Customer.interview_status == 'missed').count()
                attendance_count = attended_interviews + attended_contracts
                attendance_percent = round((attendance_count / scheduled_appointments) * 100, 1) if scheduled_appointments else 0

                row = {
                    'user': u,
                    'total_calls': customer_q.count(),
                    'social_calls': customer_q.filter(Customer.source == 'social').count(),
                    'reception_calls': customer_q.filter(Customer.source == 'reception').count(),
                    'other_calls': customer_q.filter(Customer.source == 'other').count(),
                    'interviews': sales_interview_q.count(),
                    'contracts': contract_q.count(),
                    'scheduled_appointments': scheduled_appointments,
                    'attended_interviews': attended_interviews,
                    'attended_contracts': attended_contracts,
                    'missed_appointments': missed_appointments,
                    'attendance_percent': attendance_percent
                }

                sales_rows.append(row)

                if selected_sales and selected_sales.id == u.id:
                    selected_summary = row

            data['sales_users'] = sales_users
            data['selected_sales'] = selected_sales
            data['sales_rows'] = sales_rows
            data['selected_sales_summary'] = selected_summary

    return render_template('admin/reports.html',
        data=data, report_type=report_type,
        from_date=from_date_str, to_date=to_date_str
    )
    

@admin_bp.route('/logs')
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    logs_q = ActivityLog.query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', logs=logs_q)
