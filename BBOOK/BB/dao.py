import hashlib
from datetime import date, timedelta, datetime
from sqlalchemy import func, and_

from BBOOK.BB import db
from BBOOK.BB.models import BookCategory, Book, User, Author, Publisher, Member, StatusPenalty, WaitingList, \
    StatusRequest, ApprovalType, BorrowRecord, BorrowRequest, UserRole, BorrowRequestBatch


def load_book_categories():
    categories = BookCategory.query.order_by('id').all()
    if not categories:
        return []  # Đảm bảo trả về danh sách rỗng nếu không có danh mục
    for category in categories:
        category.product_count = Book.query.filter(Book.category_id == category.id).count()
    return categories


def load_books(kw: object = None) -> object:
    products = Book.query
    if kw:
        products = products.filter(Book.title.contains(kw))  # Sửa Book.name thành Book.title
    return products.all()


# Trong file dao.py, sửa function add_user:

def add_user(fullName, username, password, **kwargs):
    """Tạo User và tự động tạo Member"""
    password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())

    try:
        # Tạo User
        user = User(fullName=fullName.strip(),
                    username=username.strip(),
                    password=password,
                    email=kwargs.get('email'),
                    avatar=kwargs.get('avatar'))
        db.session.add(user)
        db.session.flush()  # Để lấy user.id

        # Tự động tạo Member cho User (trừ Admin)
        if user.role == UserRole.MEMBER:
            member = Member(
                user_id=user.id,
                borrowLimit=5,  # Mặc định cho phép mượn 5 cuốn
                currentBorrowCount=0,
                statusPenalty=StatusPenalty.LEVEL1
            )
            db.session.add(member)

        db.session.commit()
        return user

    except Exception as e:
        db.session.rollback()
        raise e


def get_or_create_member(user_id):
    """Lấy Member hoặc tạo mới nếu chưa có"""
    member = Member.query.filter_by(user_id=user_id).first()

    if not member:
        # Tự động tạo Member nếu chưa có
        user = User.query.get(user_id)
        if user and user.role == UserRole.MEMBER:
            member = Member(
                user_id=user_id,
                borrowLimit=5,
                currentBorrowCount=0,
                statusPenalty=StatusPenalty.LEVEL1
            )
            db.session.add(member)
            db.session.commit()

    return member


def search_books(kw):
    if not kw:
        return []
    # Bỏ khoảng trắng thừa, chuyển về chữ thường, tìm kiếm
    return Book.query.filter(
        Book.title.ilike(f"%{kw}%")  # Sửa Book.name thành Book.title
    ).all()


def load_books_by_category(category_id):
    return Book.query.filter(Book.category_id == category_id).all()


def check_login(username, password, role=None):
    if username and password:
        password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())
        query = User.query.filter(User.username.__eq__(username.strip()),
                                  User.password.__eq__(password))

        if role:
            if isinstance(role, list):
                # Nếu user_role là list thì kiểm tra user có thuộc một trong các role đó không
                query = query.filter(User.role.in_(role))
            else:
                # Nếu user_role là giá trị đơn lẻ
                query = query.filter(User.role.__eq__(role))

        return query.first()


def get_user_by_id(user_id):
    return User.query.get(user_id)


def cart_stats(cart):
    total_quantity = 0

    if cart:
        for c in cart.values():
            total_quantity += c['quantity']

    return {
        'total_quantity': total_quantity
    }


def get_book_by_id(book_id):
    """Lấy thông tin sách theo ID"""
    return Book.query.get(book_id)


def get_books_by_category(category_id, limit=8, exclude_id=None):
    """Lấy sách cùng thể loại (để hiển thị trong phần gợi ý)"""
    query = Book.query.filter(Book.category_id == category_id)
    if exclude_id:
        query = query.filter(Book.id != exclude_id)
    return query.limit(limit).all()


def get_book_rating(book_id):
    """Tính điểm đánh giá trung bình của sách"""
    from sqlalchemy import func
    from BBOOK.BB.models import Rating

    result = db.session.query(
        func.avg(Rating.score).label('avg_rating'),
        func.count(Rating.id).label('total_ratings')
    ).filter(Rating.book_id == book_id).first()

    return {
        'average': float(result.avg_rating) if result.avg_rating else 0,
        'total': result.total_ratings if result.total_ratings else 0
    }


def load_authors():
    """Lấy danh sách tác giả"""
    return Author.query.order_by(Author.name).all()


def load_publishers():
    """Lấy danh sách nhà xuất bản"""
    return Publisher.query.order_by(Publisher.name).all()


def check_member_borrow_eligibility(member_id):
    """
    Kiểm tra điều kiện mượn sách của member
    Returns: dict với status và message
    """
    member = Member.query.get(member_id)
    if not member:
        return {'eligible': False, 'message': 'Không tìm thấy thông tin thành viên'}

    # Kiểm tra tài khoản bị khóa (≥ Level 4)
    if member.statusPenalty.value >= StatusPenalty.LEVEL4.value:
        return {'eligible': False, 'message': 'Tài khoản đã bị khóa. Liên hệ thủ thư'}

    # Kiểm tra số sách đang mượn
    current_count = member.get_current_borrow_count()
    if current_count >= member.borrowLimit:
        return {'eligible': False, 'message': f'Đã mượn tối đa {member.borrowLimit} cuốn'}

    # Kiểm tra sách quá hạn
    if member.has_overdue_books():
        return {'eligible': False, 'message': 'Có sách quá hạn chưa trả'}

    return {'eligible': True, 'available_slots': member.borrowLimit - current_count}


def add_to_waiting_list(member_id, book_id):
    """Thêm vào danh sách chờ"""
    # Kiểm tra đã có trong danh sách chờ chưa
    existing = WaitingList.query.filter_by(member_id=member_id, book_id=book_id).first()
    if existing:
        return {'success': False, 'message': 'Đã có trong danh sách chờ'}

    # Tính priority (thứ tự tiếp theo)
    max_priority = db.session.query(func.max(WaitingList.priority)) \
                       .filter_by(book_id=book_id).scalar() or 0

    waiting_item = WaitingList(
        member_id=member_id,
        book_id=book_id,
        priority=max_priority + 1
    )

    db.session.add(waiting_item)
    db.session.commit()

    return {'success': True, 'position': max_priority + 1}


def get_borrow_statistics():
    """B2: Lấy thống kê cho dashboard"""
    today = date.today()

    # Số yêu cầu chờ duyệt
    pending_requests = BorrowRequest.query.filter_by(statusRequest=StatusRequest.PENDING).count()

    # Số sách đã mượn (chưa trả)
    borrowed_books = BorrowRecord.query.filter(BorrowRecord.returnDate.is_(None)).count()

    # Số sách quá hạn (mượn quá 30 ngày chưa trả)
    overdue_date = today - timedelta(days=30)
    overdue_books = BorrowRecord.query.filter(
        and_(
            BorrowRecord.returnDate.is_(None),
            BorrowRecord.borrowDate <= overdue_date
        )
    ).count()

    # Số yêu cầu hôm nay
    today_requests = BorrowRequest.query.filter(
        func.date(BorrowRequest.requestDate) == today
    ).count()

    return {
        'pending_requests': pending_requests,
        'borrowed_books': borrowed_books,
        'overdue_books': overdue_books,
        'today_requests': today_requests
    }


def get_pending_requests_with_details():
    """B4: Lấy danh sách yêu cầu chờ duyệt với đầy đủ thông tin"""
    requests = db.session.query(BorrowRequest) \
        .join(BorrowRequest.member) \
        .join(Member.user) \
        .join(BorrowRequest.book) \
        .filter(BorrowRequest.statusRequest == StatusRequest.PENDING) \
        .order_by(BorrowRequest.requestDate.desc()) \
        .all()

    return requests


def check_member_violations(member_id):
    """Kiểm tra vi phạm của member - Luồng ngoại lệ"""
    violations = []
    member = Member.query.get(member_id)

    if not member:
        return violations

    # Kiểm tra sách quá hạn
    today = date.today()
    overdue_date = today - timedelta(days=30)

    overdue_records = BorrowRecord.query.filter(
        and_(
            BorrowRecord.member_id == member_id,
            BorrowRecord.returnDate.is_(None),
            BorrowRecord.borrowDate <= overdue_date
        )
    ).all()

    if overdue_records:
        violations.append({
            'type': 'OVERDUE',
            'message': f'Có {len(overdue_records)} sách quá hạn chưa trả',
            'severity': 'high',
            'records': overdue_records
        })

    # Kiểm tra penalty status
    if member.statusPenalty.value >= StatusPenalty.LEVEL3.value:
        violations.append({
            'type': 'PENALTY',
            'message': f'Tài khoản đang bị phạt mức {member.statusPenalty.value}',
            'severity': 'medium'
        })

    return violations


def approve_borrow_request(request_id, approval_type, processor_id, **kwargs):
    """B5-B7: Duyệt yêu cầu mượn sách"""
    try:
        request_obj = BorrowRequest.query.get(request_id)
        if not request_obj:
            return {'success': False, 'message': 'Không tìm thấy yêu cầu'}

        if approval_type == 'approve':
            request_obj.statusRequest = StatusRequest.APPROVED
            request_obj.approvalType = ApprovalType.NORMAL

            # Cập nhật số lượng sách và member
            request_obj.book.availableCopies -= 1
            request_obj.member.currentBorrowCount += 1

            # Tạo BorrowRecord
            borrow_record = BorrowRecord(
                member_id=request_obj.member_id,
                borrowDate=date.today()
            )
            db.session.add(borrow_record)

        elif approval_type == 'conditional':
            request_obj.statusRequest = StatusRequest.APPROVED
            request_obj.approvalType = ApprovalType.CONDITIONAL
            request_obj.specialConditions = kwargs.get('conditions', '')

            # Cập nhật thời hạn nếu có
            if kwargs.get('new_return_date'):
                request_obj.expectedReturnDate = kwargs.get('new_return_date')

        elif approval_type == 'reject':
            request_obj.statusRequest = StatusRequest.REJECTED
            request_obj.rejectionReason = kwargs.get('reason', '')

        # Cập nhật thông tin duyệt
        request_obj.approvedDate = date.today()
        request_obj.processedBy = processor_id

        db.session.commit()

        # TODO: Gửi email thông báo (B6)
        send_approval_notification(request_obj)

        return {'success': True, 'message': 'Duyệt thành công'}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Lỗi: {str(e)}'}


def send_approval_notification(request_obj):
    """B6: Gửi email thông báo kết quả (placeholder)"""
    # TODO: Implement email sending
    email_content = {
        'to': request_obj.member.user.email,
        'subject': f'Kết quả yêu cầu mượn sách: {request_obj.book.title}',
        'status': request_obj.statusRequest.value,
        'book_title': request_obj.book.title,
        'approval_type': request_obj.approvalType.value if request_obj.approvalType else None
    }

    print(f"[EMAIL] Gửi thông báo: {email_content}")
    # Tích hợp với service email thực tế
    return True


def generate_batch_code():
    """Sinh mã batch duy nhất, auto tăng theo ngày"""
    today = datetime.now()
    year = today.strftime("%Y")

    # Lấy mã lớn nhất trong năm hiện tại
    last_code = (
        BorrowRequestBatch.query
        .filter(BorrowRequestBatch.batchCode.like(f"BR{year}%"))
        .order_by(BorrowRequestBatch.batchCode.desc())
        .first()
    )

    if last_code:
        # Tách số thứ tự ở cuối mã
        last_number = int(last_code.batchCode[-3:])
        new_number = last_number + 1
    else:
        new_number = 1

    return f"BR{year}{new_number:03d}"


def create_borrow_request_batch(member_id, total_books, notes=None):
    """Tạo batch yêu cầu mượn sách"""
    try:
        batch = BorrowRequestBatch(
            member_id=member_id,
            batchCode=generate_batch_code(),
            totalBooks=total_books,
            batchStatus=StatusRequest.PENDING,
            requestDate=date.today(),
            notes=notes
        )

        db.session.add(batch)
        db.session.flush()  # Để lấy batch.id
        return batch

    except Exception as e:
        db.session.rollback()
        raise e


def submit_batch_borrow_request(member_id, cart_items):
    """Gửi yêu cầu mượn sách theo batch"""
    try:
        total_books = sum(item['quantity'] for item in cart_items.values())

        # Tạo batch trước
        batch = create_borrow_request_batch(member_id, total_books)

        # Tạo các yêu cầu con
        created_requests = []
        for book_id, item in cart_items.items():
            book = Book.query.get(book_id)
            if not book or book.availableCopies < item['quantity']:
                raise Exception(f'Sách "{item["title"]}" không đủ số lượng!')

            for _ in range(item['quantity']):
                borrow_request = BorrowRequest(
                    member_id=member_id,
                    book_id=book_id,
                    batch_id=batch.id,  # THÊM BATCH_ID
                    requestDate=date.today(),
                    statusRequest=StatusRequest.PENDING
                )
                db.session.add(borrow_request)
                created_requests.append(borrow_request)

        db.session.commit()
        return {
            'success': True,
            'batch': batch,
            'requests': created_requests
        }

    except Exception as e:
        db.session.rollback()
        raise e


def get_member_borrow_batches(member_id):
    """Lấy danh sách batch yêu cầu mượn của member"""
    return BorrowRequestBatch.query.filter_by(member_id=member_id) \
        .order_by(BorrowRequestBatch.requestDate.desc()) \
        .all()


def get_batch_with_details(batch_id):
    """Lấy thông tin chi tiết batch"""
    batch = BorrowRequestBatch.query.get(batch_id)
    if not batch:
        return None

    # Load các requests trong batch
    requests = BorrowRequest.query.filter_by(batch_id=batch_id) \
        .join(Book) \
        .all()

    return {
        'batch': batch,
        'requests': requests,
        'books': [req.book for req in requests]
    }


def approve_batch_request(batch_id, approval_type, processor_id, **kwargs):
    """Duyệt cả batch yêu cầu mượn"""
    try:
        batch = BorrowRequestBatch.query.get(batch_id)
        if not batch:
            return {'success': False, 'message': 'Không tìm thấy batch'}

        # Cập nhật trạng thái batch
        if approval_type == 'approve':
            batch.batchStatus = StatusRequest.APPROVED

            # Duyệt tất cả requests trong batch
            requests = BorrowRequest.query.filter_by(batch_id=batch_id).all()
            for request in requests:
                request.statusRequest = StatusRequest.APPROVED
                request.approvedDate = date.today()
                request.processedBy = processor_id

                # Cập nhật số lượng sách
                request.book.availableCopies -= 1

            # Cập nhật số sách đang mượn của member
            batch.member.currentBorrowCount += len(requests)

        elif approval_type == 'reject':
            batch.batchStatus = StatusRequest.REJECTED

            # Từ chối tất cả requests
            requests = BorrowRequest.query.filter_by(batch_id=batch_id).all()
            for request in requests:
                request.statusRequest = StatusRequest.REJECTED
                request.approvedDate = date.today()
                request.processedBy = processor_id
                request.rejectionReason = kwargs.get('reason', '')

        batch.approvedDate = date.today()
        batch.processedBy = processor_id
        batch.notes = kwargs.get('notes', '')

        db.session.commit()
        return {'success': True, 'message': 'Xử lý batch thành công'}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Lỗi: {str(e)}'}


def cancel_borrow_batch(batch_id, user_id):
    """
    Hủy batch yêu cầu mượn sách
    Args:
        batch_id: ID của batch cần hủy
        user_id: ID của user thực hiện hủy
    Returns:
        dict: kết quả hủy batch
    """
    try:
        from BBOOK.BB.models import BorrowRequestBatch

        # Tìm batch
        batch = BorrowRequestBatch.query.get(batch_id)
        if not batch:
            return {'success': False, 'message': 'Không tìm thấy batch'}

        # Kiểm tra quyền sở hữu
        member = Member.query.filter_by(user_id=user_id).first()
        if not member or batch.member_id != member.id:
            return {'success': False, 'message': 'Không có quyền hủy batch này'}

        # Kiểm tra trạng thái
        if batch.batchStatus != StatusRequest.PENDING:
            return {'success': False, 'message': 'Chỉ có thể hủy batch đang chờ duyệt'}

        # Đếm số requests trong batch
        requests_count = BorrowRequest.query.filter_by(batch_id=batch_id).count()

        # Xóa tất cả requests trong batch
        BorrowRequest.query.filter_by(batch_id=batch_id).delete()

        # Xóa batch
        db.session.delete(batch)
        db.session.commit()

        return {
            'success': True,
            'message': f'Đã hủy batch {batch.batchCode} ({requests_count} yêu cầu)',
            'batch_code': batch.batchCode,
            'cancelled_requests': requests_count
        }
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Lỗi: {str(e)}'}


def get_borrow_management_stats():
    """Lấy thống kê cho dashboard quản lý mượn trả"""
    from datetime import date, timedelta

    today = date.today()

    # Số yêu cầu chờ duyệt
    pending_requests = db.session.query(BorrowRequestBatch).filter_by(
        batchStatus=StatusRequest.PENDING
    ).count()

    # Số sách đã mượn (chưa trả)
    borrowed_books = db.session.query(BorrowRecord).filter(
        BorrowRecord.returnDate.is_(None)
    ).count()

    # Số sách quá hạn (mượn > 30 ngày chưa trả)
    overdue_threshold = today - timedelta(days=30)
    overdue_books = db.session.query(BorrowRecord).filter(
        BorrowRecord.returnDate.is_(None),
        BorrowRecord.borrowDate < overdue_threshold
    ).count()

    # Số yêu cầu hôm nay
    today_requests = db.session.query(BorrowRequestBatch).filter(
        func.date(BorrowRequestBatch.requestDate) == today
    ).count()

    return {
        'pending_requests': pending_requests,
        'borrowed_books': borrowed_books,
        'overdue_books': overdue_books,
        'today_requests': today_requests
    }


def get_pending_requests(page=1, per_page=10, filters=None):
    """Lấy danh sách yêu cầu chờ duyệt với phân trang"""
    query = db.session.query(BorrowRequestBatch).filter_by(
        batchStatus=StatusRequest.PENDING
    ).order_by(BorrowRequestBatch.requestDate.desc())

    # Áp dụng filters nếu có
    if filters:
        if filters.get('member_name'):
            query = query.join(Member).join(User).filter(
                User.fullName.ilike(f"%{filters['member_name']}%")
            )

        if filters.get('date_from'):
            query = query.filter(BorrowRequestBatch.requestDate >= filters['date_from'])

        if filters.get('date_to'):
            query = query.filter(BorrowRequestBatch.requestDate <= filters['date_to'])

    # Phân trang
    total = query.count()
    batches = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        'batches': batches,
        'total': total,
        'pages': (total + per_page - 1) // per_page,
        'current_page': page
    }


def check_member_violations(member_id):
    """Kiểm tra vi phạm của member"""
    from datetime import date, timedelta

    member = Member.query.get(member_id)
    if not member:
        return {'has_violations': False, 'warnings': []}

    warnings = []

    # Kiểm tra sách quá hạn
    overdue_threshold = date.today() - timedelta(days=30)
    overdue_count = db.session.query(BorrowRecord).filter(
        BorrowRecord.member_id == member_id,
        BorrowRecord.returnDate.is_(None),
        BorrowRecord.borrowDate < overdue_threshold
    ).count()

    if overdue_count > 0:
        warnings.append(f"Có {overdue_count} sách quá hạn chưa trả")

    # Kiểm tra số sách đang mượn
    current_borrowed = db.session.query(BorrowRecord).filter(
        BorrowRecord.member_id == member_id,
        BorrowRecord.returnDate.is_(None)
    ).count()

    if current_borrowed >= member.borrowLimit:
        warnings.append(f"Đã mượn {current_borrowed}/{member.borrowLimit} sách (giới hạn)")

    # Kiểm tra penalty level
    if member.statusPenalty.value >= 3:
        warnings.append(f"Mức phạt cao (Level {member.statusPenalty.value})")

    return {
        'has_violations': len(warnings) > 0,
        'warnings': warnings,
        'overdue_count': overdue_count,
        'current_borrowed': current_borrowed,
        'penalty_level': member.statusPenalty.value
    }


def approve_batch_with_conditions(batch_id, approval_type, processor_id, **kwargs):
    """Duyệt batch với các điều kiện khác nhau"""
    try:
        batch = BorrowRequestBatch.query.get(batch_id)
        if not batch:
            return {'success': False, 'message': 'Không tìm thấy batch'}

        if batch.batchStatus != StatusRequest.PENDING:
            return {'success': False, 'message': 'Batch đã được xử lý'}

        member_violations = check_member_violations(batch.member_id)

        if approval_type == 'approve':
            # Duyệt bình thường
            result = _process_approval(batch, processor_id, **kwargs)

        elif approval_type == 'conditional':
            # Duyệt có điều kiện
            result = _process_conditional_approval(batch, processor_id, **kwargs)

        elif approval_type == 'reject':
            # Từ chối
            result = _process_rejection(batch, processor_id, **kwargs)

        else:
            return {'success': False, 'message': 'Loại duyệt không hợp lệ'}

        if result['success']:
            # Gửi email thông báo
            send_approval_notification(batch, approval_type, **kwargs)

        return result

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'message': f'Lỗi: {str(e)}'}


def _process_approval(batch, processor_id, **kwargs):
    """Xử lý duyệt bình thường"""
    batch.batchStatus = StatusRequest.APPROVED
    batch.approvedDate = date.today()
    batch.processedBy = processor_id
    batch.notes = kwargs.get('notes', '')

    # Duyệt tất cả requests trong batch
    requests = BorrowRequest.query.filter_by(batch_id=batch.id).all()
    for request in requests:
        request.statusRequest = StatusRequest.APPROVED
        request.approvedDate = date.today()
        request.processedBy = processor_id

        # Giảm số lượng sách có sẵn
        request.book.availableCopies -= 1

    # Cập nhật số sách đang mượn của member
    batch.member.currentBorrowCount += len(requests)

    db.session.commit()
    return {'success': True, 'message': 'Duyệt thành công'}


def _process_conditional_approval(batch, processor_id, **kwargs):
    """Xử lý duyệt có điều kiện"""
    batch.batchStatus = StatusRequest.APPROVED
    batch.approvedDate = date.today()
    batch.processedBy = processor_id
    batch.notes = f"Điều kiện: {kwargs.get('conditions', '')}"

    requests = BorrowRequest.query.filter_by(batch_id=batch.id).all()
    for request in requests:
        request.statusRequest = StatusRequest.APPROVED
        request.approvedDate = date.today()
        request.processedBy = processor_id
        request.specialConditions = kwargs.get('conditions', '')

        # Áp dụng thay đổi thời hạn nếu có
        if kwargs.get('custom_return_date'):
            request.expectedReturnDate = kwargs['custom_return_date']

        request.book.availableCopies -= 1

    batch.member.currentBorrowCount += len(requests)

    db.session.commit()
    return {'success': True, 'message': 'Duyệt có điều kiện thành công'}


def _process_rejection(batch, processor_id, **kwargs):
    """Xử lý từ chối"""
    batch.batchStatus = StatusRequest.REJECTED
    batch.approvedDate = date.today()
    batch.processedBy = processor_id
    batch.notes = kwargs.get('rejection_reason', '')

    requests = BorrowRequest.query.filter_by(batch_id=batch.id).all()
    for request in requests:
        request.statusRequest = StatusRequest.REJECTED
        request.approvedDate = date.today()
        request.processedBy = processor_id
        request.rejectionReason = kwargs.get('rejection_reason', '')

    db.session.commit()
    return {'success': True, 'message': 'Từ chối thành công'}


def send_approval_notification(batch, approval_type, **kwargs):
    """Gửi email thông báo kết quả duyệt"""
    member = batch.member
    user = member.user

    # Lấy danh sách sách trong batch
    requests = BorrowRequest.query.filter_by(batch_id=batch.id).all()
    books_list = [f"- {req.book.title} ({req.book.author.name})" for req in requests]

    if approval_type == 'approve':
        subject = f"Yêu cầu mượn sách {batch.batchCode} đã được duyệt"
        message = f"""
        Chào {user.fullName},

        Yêu cầu mượn sách của bạn đã được CHẤP NHẬN.

        Mã yêu cầu: {batch.batchCode}
        Số sách: {batch.totalBooks}
        Danh sách sách:
        {chr(10).join(books_list)}

        Vui lòng đến thư viện để nhận sách.

        Trân trọng,
        Thư viện
        """

    elif approval_type == 'conditional':
        subject = f"Yêu cầu mượn sách {batch.batchCode} được duyệt có điều kiện"
        message = f"""
        Chào {user.fullName},

        Yêu cầu mượn sách của bạn được CHẤP NHẬN với điều kiện.

        Mã yêu cầu: {batch.batchCode}
        Điều kiện: {kwargs.get('conditions', '')}

        Danh sách sách:
        {chr(10).join(books_list)}

        Vui lòng tuân thủ điều kiện và đến thư viện nhận sách.

        Trân trọng,
        Thư viện
        """

    elif approval_type == 'reject':
        subject = f"Yêu cầu mượn sách {batch.batchCode} bị từ chối"
        message = f"""
        Chào {user.fullName},

        Rất tiếc, yêu cầu mượn sách của bạn đã bị TỪ CHỐI.

        Mã yêu cầu: {batch.batchCode}
        Lý do: {kwargs.get('rejection_reason', '')}

        Vui lòng liên hệ thư viện để biết thêm chi tiết.

        Trân trọng,
        Thư viện
        """

    # TODO: Tích hợp với email service thực tế
    print(f"[EMAIL] To: {user.email}")
    print(f"[EMAIL] Subject: {subject}")
    print(f"[EMAIL] Message: {message}")

    return True


def get_monthly_borrow_statistics(year, month):
    try:
        from sqlalchemy import func, extract, desc
        from BBOOK.BB.models import BorrowRequest, Book, Author, StatusRequest

        # Query lấy top 10 sách được mượn nhiều nhất
        stats = db.session.query(
            Book.id,
            Book.title,
            Author.name.label('author_name'),
            func.count(BorrowRequest.id).label('borrow_count')
        ).join(
            BorrowRequest, Book.id == BorrowRequest.book_id
        ).join(
            Author, Book.author_id == Author.id, isouter=True
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            extract('year', BorrowRequest.requestDate) == year,
            extract('month', BorrowRequest.requestDate) == month
        ).group_by(
            Book.id, Book.title, Author.name
        ).order_by(
            desc('borrow_count')
        ).limit(10).all()

        # Tính tổng số lượt mượn trong tháng
        total_borrows = db.session.query(
            func.count(BorrowRequest.id)
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            extract('year', BorrowRequest.requestDate) == year,
            extract('month', BorrowRequest.requestDate) == month
        ).scalar()

        return {
            'success': True,
            'data': [
                {
                    'book_id': stat.id,
                    'title': stat.title,
                    'author': stat.author_name or 'Chưa rõ',
                    'borrow_count': stat.borrow_count
                }
                for stat in stats
            ],
            'total_borrows': total_borrows or 0,
            'month': month,
            'year': year
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'data': [],
            'total_borrows': 0
        }


def get_yearly_borrow_overview(year):
    try:
        from sqlalchemy import func, extract
        from BBOOK.BB.models import BorrowRequest, StatusRequest

        # Query lấy số lượt mượn theo từng tháng
        monthly_stats = db.session.query(
            extract('month', BorrowRequest.requestDate).label('month'),
            func.count(BorrowRequest.id).label('total_borrows')
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            extract('year', BorrowRequest.requestDate) == year
        ).group_by(
            extract('month', BorrowRequest.requestDate)
        ).order_by('month').all()

        # Tạo mảng 12 tháng với giá trị mặc định là 0
        months_data = [0] * 12
        month_names = [
            'Tháng 1', 'Tháng 2', 'Tháng 3', 'Tháng 4',
            'Tháng 5', 'Tháng 6', 'Tháng 7', 'Tháng 8',
            'Tháng 9', 'Tháng 10', 'Tháng 11', 'Tháng 12'
        ]

        # Điền dữ liệu thực tế vào
        for stat in monthly_stats:
            month_index = int(stat.month) - 1  # Chuyển từ 1-12 về 0-11
            months_data[month_index] = stat.total_borrows

        return {
            'success': True,
            'year': year,
            'months': month_names,
            'data': months_data,
            'total_year_borrows': sum(months_data)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'year': year,
            'months': [],
            'data': [],
            'total_year_borrows': 0
        }


def get_top_books_all_time(limit=10):

    try:
        from sqlalchemy import func, desc
        from BBOOK.BB.models import BorrowRequest, Book, Author, StatusRequest

        top_books = db.session.query(
            Book.id,
            Book.title,
            Author.name.label('author_name'),
            func.count(BorrowRequest.id).label('total_borrows')
        ).join(
            BorrowRequest, Book.id == BorrowRequest.book_id
        ).join(
            Author, Book.author_id == Author.id, isouter=True
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        ).group_by(
            Book.id, Book.title, Author.name
        ).order_by(
            desc('total_borrows')
        ).limit(limit).all()

        return [
            {
                'book_id': book.id,
                'title': book.title,
                'author': book.author_name or 'Chưa rõ',
                'total_borrows': book.total_borrows
            }
            for book in top_books
        ]

    except Exception as e:
        print(f"Error in get_top_books_all_time: {str(e)}")
        return []


def get_borrow_stats_summary():

    try:
        from datetime import date, timedelta
        from sqlalchemy import func
        from BBOOK.BB.models import BorrowRequest, Book, Member, StatusRequest

        today = date.today()
        this_month_start = today.replace(day=1)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        # Tổng số yêu cầu đã được duyệt
        total_approved = db.session.query(func.count(BorrowRequest.id)).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        ).scalar() or 0

        # Số yêu cầu tháng này
        this_month_requests = db.session.query(func.count(BorrowRequest.id)).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            BorrowRequest.requestDate >= this_month_start
        ).scalar() or 0

        # Số yêu cầu tháng trước
        last_month_requests = db.session.query(func.count(BorrowRequest.id)).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            BorrowRequest.requestDate >= last_month_start,
            BorrowRequest.requestDate < this_month_start
        ).scalar() or 0

        # Tính phần trăm thay đổi
        if last_month_requests > 0:
            change_percent = ((this_month_requests - last_month_requests) / last_month_requests) * 100
        else:
            change_percent = 0 if this_month_requests == 0 else 100

        # Tổng số sách khác nhau đã được mượn
        unique_books_borrowed = db.session.query(
            func.count(func.distinct(BorrowRequest.book_id))
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        ).scalar() or 0

        # Tổng số member đã từng mượn sách
        active_members = db.session.query(
            func.count(func.distinct(BorrowRequest.member_id))
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        ).scalar() or 0

        return {
            'total_approved_requests': total_approved,
            'this_month_requests': this_month_requests,
            'last_month_requests': last_month_requests,
            'change_percent': round(change_percent, 1),
            'unique_books_borrowed': unique_books_borrowed,
            'active_members': active_members,
            'change_direction': 'increase' if change_percent > 0 else 'decrease' if change_percent < 0 else 'stable'
        }

    except Exception as e:
        return {
            'total_approved_requests': 0,
            'this_month_requests': 0,
            'last_month_requests': 0,
            'change_percent': 0,
            'unique_books_borrowed': 0,
            'active_members': 0,
            'change_direction': 'stable',
            'error': str(e)
        }


def get_available_statistics_years():

    try:
        from sqlalchemy import func, extract, desc
        from BBOOK.BB.models import BorrowRequest, StatusRequest

        years = db.session.query(
            extract('year', BorrowRequest.requestDate).label('year')
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        ).distinct().order_by(desc('year')).all()

        return [int(year.year) for year in years] if years else [datetime.now().year]

    except Exception as e:
        print(f"Error getting available years: {str(e)}")
        return [datetime.now().year]


def get_book_borrow_trend(book_id, months=12):

    try:
        from datetime import date, timedelta
        from sqlalchemy import func, extract, desc
        from BBOOK.BB.models import BorrowRequest, Book, StatusRequest

        # Tính ngày bắt đầu
        end_date = date.today()
        start_date = end_date.replace(day=1) - timedelta(days=months * 30)  # Ước tính

        # Query dữ liệu theo tháng
        trend_data = db.session.query(
            extract('year', BorrowRequest.requestDate).label('year'),
            extract('month', BorrowRequest.requestDate).label('month'),
            func.count(BorrowRequest.id).label('borrow_count')
        ).filter(
            BorrowRequest.book_id == book_id,
            BorrowRequest.statusRequest == StatusRequest.APPROVED,
            BorrowRequest.requestDate >= start_date
        ).group_by(
            extract('year', BorrowRequest.requestDate),
            extract('month', BorrowRequest.requestDate)
        ).order_by('year', 'month').all()

        # Lấy thông tin sách
        book = Book.query.get(book_id)

        return {
            'success': True,
            'book_title': book.title if book else 'Unknown',
            'book_id': book_id,
            'trend_data': [
                {
                    'year': int(data.year),
                    'month': int(data.month),
                    'month_name': f"{int(data.month)}/{int(data.year)}",
                    'borrow_count': data.borrow_count
                }
                for data in trend_data
            ],
            'total_period_borrows': sum(data.borrow_count for data in trend_data)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'book_id': book_id,
            'trend_data': [],
            'total_period_borrows': 0
        }


def export_borrow_statistics_to_csv(year=None, month=None):

    try:
        import csv
        import tempfile
        import os
        from datetime import datetime
        from sqlalchemy import func, extract
        from BBOOK.BB.models import BorrowRequest, Book, Author, StatusRequest

        # Tạo query cơ bản
        query = db.session.query(
            Book.title,
            Author.name.label('author_name'),
            extract('year', BorrowRequest.requestDate).label('year'),
            extract('month', BorrowRequest.requestDate).label('month'),
            func.count(BorrowRequest.id).label('borrow_count')
        ).join(
            BorrowRequest, Book.id == BorrowRequest.book_id
        ).join(
            Author, Book.author_id == Author.id, isouter=True
        ).filter(
            BorrowRequest.statusRequest == StatusRequest.APPROVED
        )

        # Áp dụng filter
        if year:
            query = query.filter(extract('year', BorrowRequest.requestDate) == year)
        if month:
            query = query.filter(extract('month', BorrowRequest.requestDate) == month)

        query = query.group_by(
            Book.id, Book.title, Author.name,
            extract('year', BorrowRequest.requestDate),
            extract('month', BorrowRequest.requestDate)
        ).order_by('year', 'month', func.count(BorrowRequest.id).desc())

        results = query.all()

        # Tạo file CSV tạm
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')

        writer = csv.writer(temp_file)
        writer.writerow(['Tên sách', 'Tác giả', 'Năm', 'Tháng', 'Số lượt mượn'])

        for row in results:
            writer.writerow([
                row.title,
                row.author_name or 'Chưa rõ',
                int(row.year),
                int(row.month),
                row.borrow_count
            ])

        temp_file.close()
        return temp_file.name

    except Exception as e:
        print(f"Error exporting to CSV: {str(e)}")
        return None
