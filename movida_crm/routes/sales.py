from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
from extensions import db
from models import Customer, CustomerCountry, FollowUp, Interview, NoAnswerNumber, Notification, SocialAssignment, SocialNumber
from models.user import User
from utils import log_action
from utils.notifications import create_interview_notification, create_followup_notification
from utils.dynamic_notifications import get_dynamic_notifications

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

def sales_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ['sales', 'admin']:
            flash('ليس لديك صلاحية', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)

@sales_bp.route('/')
@sales_required
def home():
    emp_id = current_user.id if current_user.role == 'sales' else None

    # Received numbers from social (not yet converted)
    assigned_numbers_query = SocialAssignment.query.filter_by(sales_employee_id=current_user.id if current_user.role == 'sales' else None)
    if current_user.role == 'admin':
        received_numbers = []
    else:
        received_ids = [a.social_number_id for a in assigned_numbers_query]
        received_numbers = SocialNumber.query.filter(
            SocialNumber.id.in_(received_ids),
            SocialNumber.converted_to_customer == False
        ).all()

    # Customers
    q = Customer.query
    if emp_id:
        q = q.filter_by(sales_employee_id=emp_id)

    now = datetime.now()
    recent_customers = q.order_by(Customer.created_at.desc()).limit(5).all()
    upcoming_interviews = q.filter(
        Customer.interview_date >= now,
        Customer.interview_status == 'active'
    ).order_by(Customer.interview_date).limit(5).all()
    sales_interviews_query = q.filter(Customer.interview_date.isnot(None)).order_by(Customer.interview_date.asc()).all()
    active_future_interviews = [c for c in sales_interviews_query if c.interview_status == 'active' and c.interview_date and c.interview_date >= now]
    other_interviews = [c for c in sales_interviews_query if not (c.interview_status == 'active' and c.interview_date and c.interview_date >= now)]
    sales_interviews = (active_future_interviews + other_interviews)[:5]
    sales_interviews_count = len(active_future_interviews + other_interviews)
    recent_followups = q.filter(Customer.followup_date != None).order_by(Customer.followup_date.desc()).limit(5).all()

    # No-answer numbers
    na_q = NoAnswerNumber.query
    if emp_id:
        na_q = na_q.filter_by(sales_employee_id=emp_id)
    no_answer = na_q.order_by(NoAnswerNumber.added_at.desc()).limit(5).all()

    # Dynamic notifications
    notifs = get_dynamic_notifications(current_user.id, current_user.role)[:10]

    return render_template('sales/home.html',
        received_numbers=received_numbers,
        recent_customers=recent_customers,
        upcoming_interviews=upcoming_interviews,
        sales_interviews=sales_interviews,
        sales_interviews_count=sales_interviews_count,
        recent_followups=recent_followups,
        no_answer=no_answer,
        notifications=notifs,
        now=now
    )

@sales_bp.route('/add-customer', methods=['GET', 'POST'])
@sales_required
def add_customer():
    phone = request.args.get('phone', '')
    social_id = request.args.get('social_id', None)
    from_social = bool(social_id)

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        full_name = request.form.get('full_name', '').strip()
        age_str = request.form.get('age', '').strip()
        countries = request.form.getlist('countries')
        has_bank = request.form.get('has_bank_statement') == 'yes'
        interest = request.form.get('interest_level', '')
        interest_pct = request.form.get('interest_percentage', None)
        not_int_reason = request.form.get('not_interested_reason', '')
        source = request.form.get('source', 'social')
        source_detail = request.form.get('source_detail', '')
        social_number_id = request.form.get('social_number_id', None)

        interview_date_str = request.form.get('interview_date', '')
        followup_date_str = request.form.get('followup_date', '')
        notes = request.form.get('notes', '')

        if not phone or not full_name:
            flash('يرجى ملء الاسم ورقم الهاتف', 'danger')
            return render_template('sales/add_customer.html', phone=phone, from_social=from_social)

        interview_date = None
        followup_date = None
        try:
            if interview_date_str:
                interview_date = datetime.strptime(interview_date_str, '%Y-%m-%dT%H:%M')
            if followup_date_str:
                followup_date = datetime.strptime(followup_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

        customer = Customer(
            phone=phone,
            full_name=full_name,
            age=int(age_str) if age_str.isdigit() else None,
            has_bank_statement=has_bank,
            interest_level=interest if interest else None,
            interest_percentage=int(interest_pct) if interest_pct and interest == 'interested' else None,
            not_interested_reason=not_int_reason if interest == 'not_interested' else None,
            source=source,
            source_detail=source_detail if source != 'social' else None,
            social_number_id=int(social_number_id) if social_number_id else None,
            sales_employee_id=current_user.id,
            interview_date=interview_date,
            interview_status='active' if interview_date else None,
            followup_date=followup_date,
            notes=notes
        )
        db.session.add(customer)

        # Add countries
        for c in countries:
            if c.strip():
                db.session.add(CustomerCountry(customer=customer, country=c.strip()))

        # Mark social number as converted
        if social_number_id:
            sn = SocialNumber.query.get(int(social_number_id))
            if sn:
                sn.converted_to_customer = True

        # Remove from no-answer if exists
        na = NoAnswerNumber.query.filter_by(phone=phone).first()
        if na:
            db.session.delete(na)

        # Create interview record for the scheduled appointment
        if interview_date:
            iv = Interview(customer_id=customer.id, employee_id=current_user.id, interview_date=interview_date, notes=notes, status='active')
            db.session.add(iv)

        db.session.commit()

        # Create notifications
        if customer.interview_date:
            create_interview_notification(
                customer.sales_employee_id, 
                customer.full_name, 
                customer.phone, 
                customer.interview_date,
                is_sales=True
            )
        
        if customer.followup_date:
            create_followup_notification(
                customer.sales_employee_id, 
                customer.full_name, 
                customer.phone, 
                customer.followup_date
            )
        
        db.session.commit()

        log_action('add_customer', f'إضافة عميل: {full_name} - {phone}', customer.id, 'customer')
        flash(f'تم إضافة العميل {full_name} بنجاح', 'success')
        return redirect(url_for('sales.customer_profile', customer_id=customer.id))

    return render_template('sales/add_customer.html', phone=phone, social_id=social_id, from_social=from_social)


@sales_bp.route('/no-answer', methods=['POST'])
@sales_required
def no_answer():
    phone = request.form.get('phone', '').strip()
    social_id = request.form.get('social_number_id', None)
    if not phone:
        flash('يرجى إدخال رقم الهاتف', 'danger')
        return redirect(url_for('sales.home'))
    existing = NoAnswerNumber.query.filter_by(phone=phone, sales_employee_id=current_user.id).first()
    if not existing:
        na = NoAnswerNumber(phone=phone, sales_employee_id=current_user.id, social_number_id=int(social_id) if social_id else None)
        db.session.add(na)
        
        # Remove from social assignments if came from social
        if social_id:
            try:
                assignment = SocialAssignment.query.filter_by(
                    social_number_id=int(social_id),
                    sales_employee_id=current_user.id
                ).first()
                if assignment:
                    db.session.delete(assignment)
            except Exception:
                pass
        
        db.session.commit()
        log_action('no_answer', f'لم يتم الرد: {phone}')
        flash('تم تسجيل عدم الرد', 'success')
    else:
        flash('الرقم موجود مسبقاً في قائمة عدم الرد', 'warning')
    return redirect(url_for('sales.home'))

@sales_bp.route('/customer/<int:customer_id>')
@sales_required
def customer_profile(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    followups = FollowUp.query.filter_by(customer_id=customer_id).order_by(FollowUp.followup_date.desc()).all()
    interviews = Interview.query.filter_by(customer_id=customer_id).order_by(Interview.interview_date.desc()).all()
    return render_template('sales/customer_profile.html', customer=customer, followups=followups, interviews=interviews)

@sales_bp.route('/customer/<int:customer_id>/edit', methods=['GET', 'POST'])
@sales_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        customer.full_name = request.form.get('full_name', customer.full_name).strip()
        customer.phone = request.form.get('phone', customer.phone).strip()
        age_str = request.form.get('age', '').strip()
        customer.age = int(age_str) if age_str.isdigit() else None
        customer.has_bank_statement = request.form.get('has_bank_statement') == 'yes'
        customer.interest_level = request.form.get('interest_level', '')
        customer.interest_percentage = int(request.form.get('interest_percentage', 0) or 0) if customer.interest_level == 'interested' else None
        customer.not_interested_reason = request.form.get('not_interested_reason', '') if customer.interest_level == 'not_interested' else None
        customer.notes = request.form.get('notes', '')

        interview_date_str = request.form.get('interview_date', '')
        followup_date_str = request.form.get('followup_date', '')
        try:
            customer.interview_date = datetime.strptime(interview_date_str, '%Y-%m-%dT%H:%M') if interview_date_str else None
            customer.interview_status = 'active' if interview_date_str else customer.interview_status
            if not interview_date_str:
                customer.interview_result = None
            customer.followup_date = datetime.strptime(followup_date_str, '%Y-%m-%dT%H:%M') if followup_date_str else None
        except ValueError:
            pass

        # Update countries
        CustomerCountry.query.filter_by(customer_id=customer_id).delete()
        for c in request.form.getlist('countries'):
            if c.strip():
                db.session.add(CustomerCountry(customer_id=customer_id, country=c.strip()))

        customer.updated_at = datetime.now()
        db.session.commit()
        log_action('edit_customer', f'تعديل عميل: {customer.full_name}', customer_id, 'customer')
        flash('تم تحديث بيانات العميل', 'success')
        return redirect(url_for('sales.customer_profile', customer_id=customer_id))
    return render_template('sales/edit_customer.html', customer=customer)

@sales_bp.route('/customer/<int:customer_id>/add-followup', methods=['POST'])
@sales_required
def add_followup(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    date_str = request.form.get('followup_date', '')
    next_str = request.form.get('next_followup_date', '')
    notes = request.form.get('notes', '')

    try:
        fdate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        next_date = datetime.strptime(next_str, '%Y-%m-%dT%H:%M') if next_str else None
    except ValueError:
        flash('تاريخ غير صحيح', 'danger')
        return redirect(url_for('sales.customer_profile', customer_id=customer_id))

    fu = FollowUp(customer_id=customer_id, employee_id=current_user.id, followup_date=fdate, next_followup_date=next_date, notes=notes)
    db.session.add(fu)
    customer.followup_date = next_date if next_date else fdate
    db.session.commit()
    log_action('add_followup', f'متابعة مع: {customer.full_name}', customer_id, 'customer')
    flash('تم إضافة المتابعة', 'success')
    return redirect(url_for('sales.customer_profile', customer_id=customer_id))

@sales_bp.route('/customer/<int:customer_id>/add-interview', methods=['POST'])
@sales_required
def add_interview(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    date_str = request.form.get('interview_date', '')
    notes = request.form.get('notes', '')
    try:
        idate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('تاريخ غير صحيح', 'danger')
        return redirect(url_for('sales.customer_profile', customer_id=customer_id))

    # ملغي جميع المقابلات القديمة النشطة للعميل
    old_interviews = Interview.query.filter_by(customer_id=customer_id, status='active').all()
    for old_iv in old_interviews:
        old_iv.status = 'cancelled'
        db.session.add(old_iv)

    iv = Interview(customer_id=customer_id, employee_id=current_user.id, interview_date=idate, notes=notes, status='active')
    db.session.add(iv)
    customer.interview_date = idate
    customer.interview_status = 'attended'
    customer.interview_result = None
    customer.interview_action_at = datetime.now()
    db.session.add(customer)
    db.session.commit()
    log_action('add_interview', f'تسجيل حضور مقابلة مع: {customer.full_name}', customer_id, 'customer')
    flash('تم تسجيل حضور المقابلة', 'success')
    return redirect(url_for('sales.customer_profile', customer_id=customer_id))

@sales_bp.route('/customer/<int:interview_id>/edit-interview', methods=['GET', 'POST'])
@sales_required
def edit_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    customer = interview.customer
    if request.method == 'POST':
        date_str = request.form.get('interview_date', '')
        notes = request.form.get('notes', '')
        try:
            idate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('تاريخ غير صحيح', 'danger')
            return redirect(url_for('sales.edit_interview', interview_id=interview_id))

        interview.interview_date = idate
        interview.notes = notes
        db.session.add(interview)

        if customer and interview.status == 'active':
            customer.interview_date = idate
            customer.interview_status = 'active'
            db.session.add(customer)

        db.session.commit()
        log_action('edit_interview', f'تعديل موعد مقابلة: {customer.full_name}', customer.id, 'customer')
        flash('تم تحديث موعد المقابلة', 'success')
        return redirect(url_for('sales.customer_profile', customer_id=customer.id))

    return render_template('sales/edit_interview.html', interview=interview)

@sales_bp.route('/customer/<int:interview_id>/cancel-interview', methods=['POST'])
@sales_required
def cancel_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    customer = interview.customer
    interview.status = 'cancelled'
    db.session.add(interview)

    if customer:
        active_iv = Interview.query.filter_by(customer_id=customer.id, status='active').order_by(Interview.interview_date.asc()).first()
        if active_iv:
            customer.interview_date = active_iv.interview_date
            customer.interview_status = 'active'
        else:
            customer.interview_date = None
            customer.interview_status = None
            customer.interview_result = None
        db.session.add(customer)

    db.session.commit()
    flash('تم إلغاء موعد المقابلة', 'success')
    return redirect(url_for('sales.customer_profile', customer_id=customer.id if customer else None))

@sales_bp.route('/customer/<int:customer_id>/interview-action', methods=['GET', 'POST'])
@sales_required
def interview_action(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'missed':
            customer.interview_status = 'missed'
            customer.interview_result = None
            customer.interview_action_at = datetime.now()
            db.session.add(customer)
            db.session.commit()
            log_action('interview_missed', f'العميل لم يحضر المقابلة: {customer.full_name}', customer_id, 'customer')
            flash('تم تسجيل أن العميل لم يحضر المقابلة', 'success')
            return redirect(url_for('sales.customer_profile', customer_id=customer_id))
        if action == 'contract':
            customer.interview_status = 'attended'
            customer.interview_result = 'contract'
            customer.interview_action_at = datetime.now()
            db.session.add(customer)
            db.session.commit()
            return redirect(url_for('files.add_contract', customer_id=customer_id))
        if action == 'interview':
            return redirect(url_for('files.add_interview', customer_id=customer_id))
        flash('لم يتم اختيار إجراء صحيح', 'danger')
    return render_template('sales/interview_action.html', customer=customer)

@sales_bp.route('/customers')
@sales_required
def customers_list():
    submitted = request.args.get('submitted', '').strip()
    q = request.args.get('q', '').strip()
    sales_id = request.args.get('sales_id', '').strip()
    interview_date = request.args.get('interview_date', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    interest = request.args.get('interest', '').strip()

    query = Customer.query
    sales_employees = []
    if current_user.role == 'sales':
        query = query.filter_by(sales_employee_id=current_user.id)
    else:
        sales_employees = User.query.filter_by(role='sales', is_active=True).order_by(User.full_name).all()

    if q:
        query = query.filter(
            (Customer.full_name.contains(q)) | (Customer.phone.contains(q))
        )

    if sales_id:
        try:
            query = query.filter_by(sales_employee_id=int(sales_id))
        except ValueError:
            pass

    if interest in ['interested', 'not_interested']:
        query = query.filter_by(interest_level=interest)

    from datetime import datetime, timedelta
    if date_from:
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Customer.created_at >= start_date)
        except ValueError:
            pass
    if date_to:
        try:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Customer.created_at < end_date)
        except ValueError:
            pass

    if interview_date:
        try:
            target_date = datetime.strptime(interview_date, '%Y-%m-%d')
            next_date = target_date + timedelta(days=1)
            # Filter customers with interviews on this specific date
            query = query.filter(
                Customer.interview_date >= target_date,
                Customer.interview_date < next_date
            )
        except ValueError:
            pass

    customers = query.order_by(Customer.created_at.desc()).all()
    return render_template(
        'sales/customers_list.html',
        customers=customers,
        q=q,
        sales_employees=sales_employees,
        selected_sales_id=sales_id,
        interview_date=interview_date,
        date_from=date_from,
        date_to=date_to,
        selected_interest=interest,
        submitted=submitted
    )

@sales_bp.route('/customer/<int:customer_id>/note', methods=['POST'])
@sales_required
def customer_note(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if current_user.role == 'sales' and customer.sales_employee_id != current_user.id:
        flash('لا تملك صلاحية تعديل الملاحظة لهذا العميل', 'danger')
        return redirect(request.referrer or url_for('sales.customers_list'))

    notes = request.form.get('notes', '').strip()
    customer.notes = notes if notes else None
    db.session.add(customer)
    db.session.commit()
    flash('تم حفظ الملاحظة بنجاح', 'success')
    return redirect(request.referrer or url_for('sales.customers_list'))

@sales_bp.route('/interviews')
@sales_required
def interviews_list():
    now = datetime.now()
    query = Customer.query.filter(Customer.interview_date.isnot(None))
    if current_user.role == 'sales':
        query = query.filter(Customer.sales_employee_id == current_user.id)

    all_interviews = query.order_by(Customer.interview_date.asc()).all()
    active_future_interviews = [c for c in all_interviews if c.interview_status == 'active' and c.interview_date and c.interview_date >= now]
    other_interviews = [c for c in all_interviews if not (c.interview_status == 'active' and c.interview_date and c.interview_date >= now)]
    sales_interviews = active_future_interviews + other_interviews

    return render_template('sales/interviews_list.html',
        sales_interviews=sales_interviews,
        now=now
    )

@sales_bp.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
@sales_required
def mark_notification_read(notif_id):
    if current_user.role == 'admin':
        n = Notification.query.filter_by(id=notif_id).first()
    else:
        n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if n:
        n.is_read = True
        db.session.commit()
    return jsonify({'success': True})
