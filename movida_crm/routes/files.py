import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_from_directory, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from functools import wraps
from extensions import db
from models.contract import Contract, Payment, Document, Note, ContractAttempt, VisaApplication
from models.interview import Interview
from models.user import User
from models.customer import Customer, CustomerCountry
from models.notification import Notification
from models.log import ActivityLog
from utils import log_action, save_upload
from utils.notifications import create_interview_notification, create_fingerprint_notification
from utils.dynamic_notifications import get_dynamic_notifications

files_bp = Blueprint('files', __name__, url_prefix='/files')

def files_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ['files', 'admin']:
            flash('ليس لديك صلاحية', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)

@files_bp.route('/')
@files_required
def home():
    now = datetime.now()
    upcoming_fingerprints = Contract.query.filter(
        Contract.fingerprint_date >= now,
        Contract.status == 'active'
    ).order_by(Contract.fingerprint_date).limit(5).all()

    recent_contracts = Contract.query.filter_by(status='active').order_by(Contract.created_at.desc()).limit(5).all()
    
    # آخر المقابلات التي أضيفت بواسطة موظفي الملفات أو الأدمن
    recent_interviews_query = Interview.query.filter(
        Interview.interview_date.isnot(None),
        Interview.employee.has(db.or_(User.role == 'files', User.role == 'admin'))
    )
    recent_interviews = recent_interviews_query.order_by(Interview.created_at.desc()).limit(5).all()

    # أقرب 5 مواعيد مستقبلية فقط من السيلز
    upcoming_interviews = Customer.query.filter(
        Customer.interview_date >= now
    ).order_by(Customer.interview_date.asc()).limit(5).all()
    
    # Dynamic notifications (احسب الإشعارات بناءً على التواريخ)
    notifs = get_dynamic_notifications(current_user.id, current_user.role)[:10]

    return render_template('files/home.html',
        upcoming_fingerprints=upcoming_fingerprints,
        recent_contracts=recent_contracts,
        recent_interviews=recent_interviews,
        upcoming_interviews=upcoming_interviews,
        notifications=notifs
    )

@files_bp.route('/add-interview', methods=['GET', 'POST'])
@files_required
def add_interview():
    sales_users = User.query.filter_by(role='sales', is_active=True).order_by(User.full_name).all()
    customer_id = request.args.get('customer_id', '').strip()
    customer = None
    prefill = {}
    if customer_id:
        try:
            customer = Customer.query.get(int(customer_id))
        except Exception:
            customer = None
        if customer:
            countries = customer.get_countries_list()
            prefill = {
                'client_name': customer.full_name or '',
                'phone': customer.phone or '',
                'country': countries[0] if countries else '',
                'customer_id': str(customer.id),
                'interview_date': customer.interview_date.strftime('%Y-%m-%dT%H:%M') if customer.interview_date else ''
            }
            if customer.sales_employee_id:
                prefill['sales_employee_id'] = str(customer.sales_employee_id)

    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '').strip() or customer_id
        phone = request.form.get('phone', '').strip()
        name = request.form.get('client_name', '').strip()
        country = request.form.get('country', '').strip()
        sales_id = request.form.get('sales_employee_id', '').strip()
        sales_name = ''
        sales_user = None
        try:
            if sales_id:
                sales_user = User.query.get(int(sales_id))
                sales_name = sales_user.full_name if sales_user else ''
        except Exception:
            sales_user = None
            sales_name = ''
        notes = request.form.get('notes', '')
        date_str = request.form.get('interview_date', '')

        try:
            idate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            idate = datetime.now()

        iv = Interview(
            employee_id=current_user.id,
            interview_date=idate,
            notes=notes,
            client_phone=phone,
            client_name=name,
            country=country,
            sales_employee_name=sales_name
        )
        # find or create customer and associate
        customer = None
        if customer_id:
            try:
                customer = Customer.query.get(int(customer_id))
            except Exception:
                customer = None
        if not customer and phone:
            customer = Customer.query.filter_by(phone=phone).first()
        if customer:
            customer.full_name = name or customer.full_name
            if sales_user:
                customer.sales_employee_id = sales_user.id
            customer.interview_date = idate
            customer.interview_status = 'attended'
            customer.interview_result = 'interview'
            db.session.add(customer)
            db.session.flush()
            iv.customer_id = customer.id
        else:
            # create minimal customer record so sales can see it
            if phone and name:
                customer = Customer(
                    phone=phone,
                    full_name=name,
                    sales_employee_id=sales_user.id if sales_user else None,
                    source='files',
                    interview_date=idate,
                    interview_status='attended',
                    interview_result='interview'
                )
                db.session.add(customer)
                db.session.flush()
                iv.customer_id = customer.id
                if country:
                    db.session.add(CustomerCountry(customer_id=customer.id, country=country))

        db.session.add(iv)
        db.session.commit()
        
        # Create notifications for sales employee if assigned
        if sales_user and sales_user.id:
            create_interview_notification(
                sales_user.id,
                name,
                phone,
                idate,
                is_sales=False  # من قسم الملفات
            )
            db.session.commit()
        
        log_action('add_interview', f'تسجيل حضور مقابلة: {name} - {phone}', iv.id, 'interview')
        flash('تم تسجيل حضور المقابلة بنجاح', 'success')
        return redirect(url_for('files.home'))
    return render_template('files/add_interview.html', sales_users=sales_users, prefill=prefill)

@files_bp.route('/add-contract', methods=['GET', 'POST'])
@files_required
def add_contract():
    sales_users = User.query.filter_by(role='sales', is_active=True).order_by(User.full_name).all()
    interview_id = request.args.get('interview_id', '').strip()
    customer_id = request.args.get('customer_id', '').strip()
    prefill = {}
    if interview_id:
        try:
            interview = Interview.query.get(int(interview_id))
        except Exception:
            interview = None
        if interview:
            prefill = {
                'client_name': interview.client_name or '',
                'phone': interview.client_phone or '',
                'country': interview.country or '',
                'notes': interview.notes or '',
                'interview_id': str(interview.id)
            }
            if interview.sales_employee_name:
                sales_user_match = User.query.filter_by(full_name=interview.sales_employee_name, role='sales').first()
                if sales_user_match:
                    prefill['sales_employee_id'] = str(sales_user_match.id)
    elif customer_id:
        try:
            customer = Customer.query.get(int(customer_id))
        except Exception:
            customer = None
        if customer:
            prefill = {
                'client_name': customer.full_name or '',
                'phone': customer.phone or '',
                'country': customer.get_countries_list()[0] if customer.get_countries_list() else '',
                'notes': customer.notes or '',
                'customer_id': str(customer.id)
            }
            if customer.sales_employee_id:
                prefill['sales_employee_id'] = str(customer.sales_employee_id)
    if request.method == 'POST':
        interview_id = request.form.get('interview_id', '').strip()
        phone = request.form.get('phone', '').strip()
        name = request.form.get('client_name', '').strip()
        country = request.form.get('country', '').strip()
        total_cost = float(request.form.get('total_cost', 0) or 0)
        num_payments = int(request.form.get('num_payments', 1) or 1)
        fingerprint_location = request.form.get('fingerprint_location', '').strip()
        sales_id = request.form.get('sales_employee_id', '').strip()
        if not sales_id:
            flash('اختر موظف السيلز قبل إنشاء الملف', 'danger')
            return render_template('files/add_contract.html', sales_users=sales_users, prefill=prefill)
        sales_name = ''
        sales_user = None
        try:
            if sales_id:
                sales_user = User.query.get(int(sales_id))
                sales_name = sales_user.full_name if sales_user else ''
        except Exception:
            sales_user = None
            sales_name = ''
        customer_id = request.form.get('customer_id', '').strip()
        notes = request.form.get('notes', '')
        fingerprint_date_str = request.form.get('fingerprint_date', '')

        fingerprint_date = None
        try:
            if fingerprint_date_str:
                fingerprint_date = datetime.strptime(fingerprint_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass

        file_number = Contract.generate_file_number()
        contract = Contract(
            file_number=file_number,
            client_phone=phone,
            client_name=name,
            country=country,
            total_cost=total_cost,
            num_payments=num_payments,
            fingerprint_location=fingerprint_location,
            fingerprint_date=fingerprint_date,
            sales_employee_name=sales_name,
            files_employee_id=current_user.id,
            notes=notes
        )
        db.session.add(contract)

        # Handle client image
        if 'client_image' in request.files:
            img = request.files['client_image']
            if img and img.filename:
                path = save_upload(img, 'clients')
                if path:
                    contract.client_image = path

        db.session.commit()

        # link or create customer so sales dashboard shows this contract
        customer = None
        if phone:
            customer = Customer.query.filter_by(phone=phone).first()
        if customer:
            customer.full_name = name or customer.full_name
            if sales_user:
                customer.sales_employee_id = sales_user.id
            customer.interview_status = 'attended'
            customer.interview_result = 'contract'
            db.session.add(customer)
        else:
            if phone and name:
                customer = Customer(
                    phone=phone,
                    full_name=name,
                    sales_employee_id=sales_user.id if sales_user else current_user.id,
                    source='files',
                    interview_status='attended',
                    interview_result='contract'
                )
                db.session.add(customer)
                db.session.flush()
                if country:
                    db.session.add(CustomerCountry(customer_id=customer.id, country=country))
        db.session.commit()

        if interview_id:
            try:
                interview = Interview.query.get(int(interview_id))
                if interview:
                    if interview.customer:
                        interview.customer.interview_status = 'attended'
                        interview.customer.interview_result = 'contract'
                        if interview.interview_date and not interview.customer.interview_date:
                            interview.customer.interview_date = interview.interview_date
                        db.session.add(interview.customer)
                    db.session.delete(interview)
                    db.session.commit()
            except Exception:
                pass
        if customer_id:
            try:
                customer = Customer.query.get(int(customer_id))
                if customer:
                    customer.interview_status = 'attended'
                    customer.interview_result = 'contract'
                    db.session.add(customer)
                    db.session.commit()
            except Exception:
                pass

        # Timeline entry
        _add_timeline(contract.id, 'إنشاء الملف', f'تم إنشاء الملف رقم {file_number}')
        
        # Create fingerprint notification
        if fingerprint_date:
            create_fingerprint_notification(
                current_user.id,
                name,
                fingerprint_date,
                fingerprint_location
            )
            db.session.commit()
        
        log_action('add_contract', f'تعاقد جديد: {name} - {phone} - {file_number}', contract.id, 'contract')
        flash(f'تم إنشاء الملف {file_number} بنجاح', 'success')
        return redirect(url_for('files.contract_profile', contract_id=contract.id))
    return render_template('files/add_contract.html', sales_users=sales_users, prefill=prefill)

@files_bp.route('/sales-interview/<int:customer_id>/action', methods=['GET', 'POST'])
@files_required
def sales_interview_action(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'missed':
            customer.interview_status = 'missed'
            customer.interview_result = None
            db.session.add(customer)
            db.session.commit()
            log_action('sales_interview_missed', f'العميل لم يحضر المقابلة: {customer.full_name}', customer_id, 'customer')
            flash('تم تسجيل أن العميل لم يحضر المقابلة', 'success')
            return redirect(url_for('sales.customer_profile', customer_id=customer_id))
        if action in ['contract', 'interview']:
            customer.interview_status = 'attended'
            customer.interview_result = action
            db.session.add(customer)
            db.session.commit()
            if action == 'contract':
                return redirect(url_for('files.add_contract', customer_id=customer_id))
            return redirect(url_for('files.add_interview', customer_id=customer_id))
        flash('لم يتم اختيار إجراء صحيح', 'danger')
    return render_template('files/sales_interview_action.html', customer=customer)


def _add_timeline(contract_id, action, description):
    log = ActivityLog(
        user_id=current_user.id,
        action=action,
        description=description,
        reference_id=contract_id,
        reference_type='contract'
    )
    db.session.add(log)

@files_bp.route('/contract/<int:contract_id>')
@files_required
def contract_profile(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    payments = Payment.query.filter_by(contract_id=contract_id, deleted=False).order_by(Payment.payment_date.desc()).all()
    documents = Document.query.filter_by(contract_id=contract_id).order_by(Document.uploaded_at.desc()).all()
    notes = Note.query.filter_by(contract_id=contract_id).order_by(Note.created_at.desc()).all()
    latest_note = notes[0] if notes else None
    attempts = ContractAttempt.query.filter_by(contract_id=contract_id).order_by(ContractAttempt.created_at.desc()).all()
    timeline = ActivityLog.query.filter_by(reference_id=contract_id, reference_type='contract').order_by(ActivityLog.created_at.desc()).all()
    return render_template('files/contract_profile.html',
        contract=contract, payments=payments, documents=documents,
        notes=notes, latest_note=latest_note, attempts=attempts, timeline=timeline
    )


@files_bp.route('/contract/<int:contract_id>/upload-client-image', methods=['POST'])
@files_required
def upload_client_image(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    if 'client_image' not in request.files:
        flash('يرجى اختيار صورة', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    f = request.files['client_image']
    if not f or not f.filename:
        flash('ملف غير صالح', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    path = save_upload(f, 'clients')
    if not path:
        flash('نوع الملف غير مدعوم أو خطأ في الرفع', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    contract.client_image = path
    db.session.commit()
    _add_timeline(contract_id, 'تحديث صورة العميل', f'تم تحديث صورة العميل')
    log_action('upload_client_image', f'صورة عميل محدثة للملف {contract.file_number}', contract_id, 'contract')
    flash('تم رفع صورة العميل بنجاح', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/add-payment', methods=['POST'])
@files_required
def add_payment(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    amount = float(request.form.get('amount', 0) or 0)
    payment_notes = request.form.get('notes', '')
    date_str = request.form.get('payment_date', '')

    try:
        pdate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M') if date_str else datetime.now()
    except ValueError:
        pdate = datetime.now()

    payment = Payment(contract_id=contract_id, amount=amount, payment_date=pdate, notes=payment_notes, employee_id=current_user.id)
    db.session.add(payment)
    db.session.commit()
    _add_timeline(contract_id, 'إضافة دفعة', f'تم إضافة دفعة بمبلغ {amount} ج.م')
    log_action('add_payment', f'دفعة {amount} للملف {contract.file_number}', contract_id, 'contract')
    flash(f'تم إضافة دفعة بمبلغ {amount}', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/edit-payment/<int:payment_id>', methods=['POST'])
@files_required
def edit_payment(contract_id, payment_id):
    payment = Payment.query.get_or_404(payment_id)
    old_amount = payment.amount
    payment.amount = float(request.form.get('amount', payment.amount) or payment.amount)
    payment.notes = request.form.get('notes', payment.notes)
    db.session.commit()
    contract = Contract.query.get(contract_id)
    _add_timeline(contract_id, 'تعديل دفعة', f'تعديل دفعة من {old_amount} إلى {payment.amount}')
    log_action('edit_payment', f'تعديل دفعة للملف {contract.file_number}', contract_id, 'contract')
    flash('تم تعديل الدفعة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/delete-payment/<int:payment_id>', methods=['POST'])
@files_required
def delete_payment(contract_id, payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment.deleted = True
    db.session.commit()
    contract = Contract.query.get(contract_id)
    _add_timeline(contract_id, 'حذف دفعة', f'حذف دفعة بمبلغ {payment.amount}')
    log_action('delete_payment', f'حذف دفعة من الملف {contract.file_number}', contract_id, 'contract')
    flash('تم حذف الدفعة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/update-fingerprint', methods=['POST'])
@files_required
def update_fingerprint(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    location = request.form.get('fingerprint_location', '').strip()
    date_str = request.form.get('fingerprint_date', '')
    try:
        fdate = datetime.strptime(date_str, '%Y-%m-%dT%H:%M') if date_str else None
    except ValueError:
        fdate = None
    contract.fingerprint_location = location
    contract.fingerprint_date = fdate
    db.session.commit()
    _add_timeline(contract_id, 'تعديل التبصيم', f'مكان: {location}')
    log_action('update_fingerprint', f'تعديل تبصيم الملف {contract.file_number}', contract_id, 'contract')
    flash('تم تحديث موعد التبصيم', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/update-visa-status', methods=['POST'])
@files_required
def update_visa_status(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    status = request.form.get('visa_status', '')
    if status not in ['under_review', 'accepted', 'rejected']:
        flash('حالة غير صحيحة', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    contract.visa_status = status

    if status == 'accepted' and 'visa_image' in request.files:
        f = request.files['visa_image']
        if f and f.filename:
            path = save_upload(f, 'visas')
            if path:
                contract.visa_image = path

    if status == 'rejected' and 'rejection_file' in request.files:
        f = request.files['rejection_file']
        if f and f.filename:
            path = save_upload(f, 'rejections')
            if path:
                contract.rejection_file = path

    db.session.commit()
    _add_timeline(contract_id, 'تعديل حالة التأشيرة', f'الحالة: {contract.get_visa_status_display()}')
    log_action('update_visa_status', f'حالة تأشيرة الملف {contract.file_number}: {status}', contract_id, 'contract')
    flash('تم تحديث حالة التأشيرة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/close', methods=['POST'])
@files_required
def close_contract(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    refund = request.form.get('refund_amount', None)
    contract.status = 'closed'
    contract.closed_at = datetime.now()
    contract.refund_amount = float(refund) if refund else None
    db.session.commit()
    _add_timeline(contract_id, 'إغلاق الملف', f'تم إغلاق الملف {"مع استرداد " + refund + " ج.م" if refund else ""}')
    log_action('close_contract', f'إغلاق الملف {contract.file_number}', contract_id, 'contract')
    flash('تم إغلاق الملف', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/reapply', methods=['POST'])
@files_required
def reapply(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    new_country = request.form.get('country', '').strip()
    new_cost = float(request.form.get('total_cost', 0) or 0)
    new_location = request.form.get('fingerprint_location', '').strip()

    attempt_count = ContractAttempt.query.filter_by(contract_id=contract_id).count()
    attempt = ContractAttempt(
        contract_id=contract_id,
        country=new_country,
        total_cost=new_cost,
        fingerprint_location=new_location,
        attempt_number=attempt_count + 1,
        employee_id=current_user.id
    )
    db.session.add(attempt)
    contract.country = new_country
    contract.total_cost = new_cost
    contract.fingerprint_location = new_location
    contract.visa_status = 'under_review'
    contract.status = 'active'
    db.session.commit()
    _add_timeline(contract_id, 'إعادة تقديم', f'الدولة الجديدة: {new_country}')
    log_action('reapply', f'إعادة تقديم الملف {contract.file_number}', contract_id, 'contract')
    flash('تم إنشاء محاولة جديدة بنجاح', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/upload-document', methods=['POST'])
@files_required
def upload_document(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    doc_name = request.form.get('doc_name', '').strip()
    if not doc_name:
        flash('يرجى إدخال اسم الملف', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    if 'document' not in request.files:
        flash('يرجى اختيار ملف', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    f = request.files['document']
    if not f or not f.filename:
        flash('ملف غير صحيح', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    path = save_upload(f, 'documents')
    if not path:
        flash('نوع الملف غير مدعوم', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))

    ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else ''
    doc = Document(contract_id=contract_id, name=doc_name, filename=path, file_type=ext, uploaded_by_id=current_user.id)
    db.session.add(doc)
    db.session.commit()
    _add_timeline(contract_id, 'رفع ملف', f'تم رفع: {doc_name}')
    log_action('upload_document', f'رفع ملف: {doc_name} للملف {contract.file_number}', contract_id, 'contract')
    flash('تم رفع الملف بنجاح', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/delete-document/<int:doc_id>', methods=['POST'])
@files_required
def delete_document(contract_id, doc_id):
    doc = Document.query.get_or_404(doc_id)
    doc_name = doc.name
    db.session.delete(doc)
    db.session.commit()
    flash(f'تم حذف {doc_name}', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/add-note', methods=['POST'])
@files_required
def add_note(contract_id):
    content = request.form.get('content', '').strip()
    if content:
        note = Note(contract_id=contract_id, content=content, employee_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        _add_timeline(contract_id, 'إضافة ملاحظات', content[:100])
        log_action('add_note', f'ملاحظة على الملف', contract_id, 'contract')
        flash('تم إضافة الملاحظة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/edit-note/<int:note_id>', methods=['POST'])
@files_required
def edit_note(contract_id, note_id):
    note = Note.query.get_or_404(note_id)
    if note.contract_id != contract_id:
        flash('الملاحظة غير مرتبطة بهذا الملف', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))
    content = request.form.get('content', '').strip()
    if content:
        note.content = content
        db.session.commit()
        _add_timeline(contract_id, 'تعديل ملاحظات', content[:100])
        log_action('edit_note', f'تعديل ملاحظة على الملف', contract_id, 'contract')
        flash('تم تعديل الملاحظة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contract/<int:contract_id>/delete-note/<int:note_id>', methods=['POST'])
@files_required
def delete_note(contract_id, note_id):
    note = Note.query.get_or_404(note_id)
    if note.contract_id != contract_id:
        flash('الملاحظة غير مرتبطة بهذا الملف', 'danger')
        return redirect(url_for('files.contract_profile', contract_id=contract_id))
    db.session.delete(note)
    db.session.commit()
    _add_timeline(contract_id, 'حذف ملاحظات', note.content[:100])
    log_action('delete_note', f'حذف ملاحظة من الملف', contract_id, 'contract')
    flash('تم حذف الملاحظة', 'success')
    return redirect(url_for('files.contract_profile', contract_id=contract_id))

@files_bp.route('/contracts')
@files_required
def contracts_list():
    q = request.args.get('q', '')
    status = request.args.get('status', 'all')
    visa_status = request.args.get('visa_status', 'all')
    query = Contract.query
    if status == 'active':
        query = query.filter_by(status='active')
    elif status == 'closed':
        query = query.filter_by(status='closed')
    if visa_status in ['under_review', 'accepted', 'rejected']:
        query = query.filter_by(visa_status=visa_status)

    if q:
        status_map = {
            'تحت المراجعة': 'under_review',
            'مقبول': 'accepted',
            'تم القبول': 'accepted',
            'مرفوض': 'rejected',
            'تم الرفض': 'rejected'
        }
        normalized_status = status_map.get(q.strip())
        filters = [
            Contract.client_name.contains(q),
            Contract.client_phone.contains(q),
            Contract.file_number.contains(q),
            Contract.country.contains(q)
        ]
        if normalized_status:
            filters.append(Contract.visa_status == normalized_status)
        query = query.filter(db.or_(*filters))

    contracts = query.order_by(Contract.created_at.desc()).all()
    return render_template('files/contracts_list.html', contracts=contracts, q=q, status=status, visa_status=visa_status)

@files_bp.route('/files-interviews')
@files_required
def files_interviews_list():
    q = request.args.get('q', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = Interview.query.filter(
        Interview.interview_date.isnot(None),
        Interview.employee.has(db.or_(User.role == 'files', User.role == 'admin'))
    )

    if q:
        query = query.filter(db.or_(
            Interview.client_phone.contains(q),
            Interview.client_name.contains(q)
        ))

    interviews = query.order_by(Interview.interview_date.desc()).all()

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            interviews = [iv for iv in interviews if iv.interview_date >= date_from_obj]
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            interviews = [iv for iv in interviews if iv.interview_date <= date_to_obj]
        except ValueError:
            pass

    return render_template('files/files_interviews_list.html',
        interviews=interviews,
        q=q,
        date_from=date_from,
        date_to=date_to
    )


@files_bp.route('/interviews')
@files_required
def interviews_list():
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    sales_employee_id = request.args.get('sales_employee_id', '').strip()

    # جلب جميع المواعيد المستقبلية من المبيعات بترتيب من الأقرب للأبعد
    query = Customer.query.filter(
        Customer.interview_date.isnot(None)
    )

    if sales_employee_id:
        try:
            query = query.filter(Customer.sales_employee_id == int(sales_employee_id))
        except ValueError:
            pass

    all_interviews = query.order_by(Customer.interview_date.asc()).all()

    # تطبيق فلتر التاريخ
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            all_interviews = [iv for iv in all_interviews if iv.interview_date >= date_from_obj]
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            all_interviews = [iv for iv in all_interviews if iv.interview_date <= date_to_obj]
        except ValueError:
            pass

    sales_employees = User.query.filter_by(role='sales').order_by(User.full_name).all()

    return render_template('files/interviews_list.html', 
        interviews=all_interviews, 
        date_from=date_from, 
        date_to=date_to,
        sales_employees=sales_employees,
        selected_sales_employee_id=sales_employee_id,
        show_files_interviews=False
    )

@files_bp.route('/uploads/<path:filepath>')
@files_required
def serve_upload(filepath):
    upload_dir = current_app.config['UPLOAD_FOLDER']
    filepath = filepath.replace('\\', '/').lstrip('/')
    directory = os.path.dirname(os.path.join(upload_dir, filepath))
    filename = os.path.basename(filepath)
    return send_from_directory(directory, filename)

@files_bp.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
@files_required
def mark_notification_read(notif_id):
    if current_user.role == 'admin':
        n = Notification.query.filter_by(id=notif_id).first()
    else:
        n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first()
    if n:
        n.is_read = True
        db.session.commit()
    return jsonify({'success': True})
