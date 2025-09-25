from datetime import date
from math import ceil
import cloudinary
from flask import Flask, render_template, request, url_for, redirect, flash, session, jsonify, Blueprint
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import google
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from sqlalchemy import or_

from BBOOK.BB import app, dao, models, db, google_bp
from BBOOK.BB.models import UserRole, Book, User, Rating, Member, BorrowRequest, StatusRequest, StatusPenalty


@app.route("/")
def index():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    kw = request.args.get('kw')
    books = dao.load_books(kw)
    return render_template('index.html', books=books)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_signin'
bp = Blueprint('api', __name__)

@app.route('/contact')
def contact():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    return render_template('contact.html')


@login_manager.user_loader
def user_load(user_id):
    return dao.get_user_by_id(user_id=user_id)


@app.route("/register", methods=['GET', 'POST'])
def user_register():
    err_msg = ""
    if request.method == 'POST':
        fullName = request.form.get('fullName')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        avatar_path = None
        try:
            if password.strip() == confirm.strip():
                avatar = request.files.get('avatar')
                if avatar:
                    res = cloudinary.uploader.upload(avatar)
                    avatar_path = res['secure_url']
                dao.add_user(fullName=fullName, username=username, password=password, email=email, avatar=avatar_path)
                return redirect(url_for('user_signin'))
            else:
                err_msg = 'Passwords do not match'
        except Exception as ex:
            err_msg = "404 not found: " + str(ex)

    return render_template('register.html', err_msg=err_msg)


@app.route("/user-login", methods=['GET', 'POST'])
def user_signin():
    err_msg = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = dao.check_login(username=username, password=password)
        if user:
            login_user(user=user)
            if user.role == UserRole.ADMIN:
                return redirect(url_for('admin_login'))
            else:
                return redirect(url_for('index'))
        else:
            err_msg = 'Username or password is incorrect !!!'
    return render_template('login.html', err_msg=err_msg)


@app.route("/login/google")
def login_google():
    if not google.authorized:
        return redirect(url_for("google.login"))
    return handle_google_oauth()


def handle_google_oauth():
    try:
        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            flash("Không thể lấy thông tin từ Google", "error")
            return redirect(url_for('user_signin'))

        user_info = resp.json()
        email = user_info.get("email")
        full_name = user_info.get("name", "")

        if not email:
            flash("Không thể lấy email từ Google", "error")
            return redirect(url_for('user_signin'))

        # Tìm user trong DB
        user = User.query.filter_by(email=email).first()

        if not user:
            try:
                base_username = email.split("@")[0]
                username = base_username
                counter = 1

                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User(
                    fullName=full_name,
                    email=email,
                    username=username,
                    password="",
                    avatar="",
                    role=UserRole.MEMBER
                )

                db.session.add(user)
                db.session.flush()  # Lấy user.id

                # Tự động tạo Member
                member = Member(
                    user_id=user.id,
                    borrowLimit=5,
                    currentBorrowCount=0,
                    statusPenalty=StatusPenalty.LEVEL1
                )
                db.session.add(member)
                db.session.commit()

            except Exception as e:
                db.session.rollback()
                flash("Lỗi tạo tài khoản", "error")
                return redirect(url_for('user_signin'))

        login_user(user, remember=True)

        if user.role == UserRole.ADMIN:
            return redirect(url_for('admin_login'))
        else:
            flash(f"Chào mừng {user.fullName}!", "success")
            return redirect(url_for('index'))

    except Exception as e:
        flash("Lỗi đăng nhập Google", "danger")
        return redirect(url_for('user_signin'))

@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    print("=== Google OAuth callback triggered ===")
    if not token:
        print("No token received")
        flash("Lỗi xác thực Google", "error")
        return False

    print(f"Token received: {token}")
    try:
        result = handle_google_oauth()
        print("OAuth handling completed")
        return False
    except Exception as e:
        print(f"Error in oauth callback: {str(e)}")
        return False


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = dao.check_login(username=username, password=password,
                               role=[UserRole.ADMIN, UserRole.LIBRARIAN])

        if user:
            login_user(user=user)
            return redirect('/admin')

        else:
            flash('Đăng nhập không hợp lệ. Vui lòng kiểm tra lại thông tin.', 'error')

    return render_template('admin/login.html')


@app.route("/user-logout")
def user_signout():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    if 'cart' in session:  # xoá giỏ hàng trước khi đăng xuất
        del session['cart']
    logout_user()
    return redirect(url_for('user_signin'))


@app.route('/product-list')
def product_list():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    kw = request.args.get('kw', '').strip()
    category_id = request.args.get('category_id', type=int)

    query = Book.query.order_by(Book.title)

    if kw:
        query = query.filter(Book.title.ilike(f"%{kw}%"))

    if category_id:
        query = query.filter(Book.category_id == category_id)

    total = query.count()
    books = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, ceil(total / per_page))

    categories = dao.load_book_categories()
    for c in categories:
        c.book_count = len(c.books)

    # Lấy danh sách tác giả và nhà xuất bản
    authors = Author.query.all()
    publishers = Publisher.query.all()

    return render_template(
        'product_list.html',
        books=books,
        current_page=page,
        total_pages=total_pages,
        categories=categories,
        authors=authors,
        publishers=publishers,
        kw=kw,
        category_id=category_id
    )


@app.route('/search', methods=['GET'])
def search():
    # Lấy tham số từ URL
    page = request.args.get('page', 1, type=int)
    per_page = 6
    kw = request.args.get('kw', '').strip()
    category_id = request.args.get('category_id', None, type=int)
    year = request.args.get('year', None, type=int)
    author_id = request.args.get('author_id', None, type=int)
    publisher_id = request.args.get('publisher_id', None, type=int)

    # Query cơ bản với join
    query = Book.query.join(Book.author, isouter=True).join(Book.publisher, isouter=True)

    # Tìm kiếm theo từ khóa
    if kw:
        query = query.filter(
            or_(
                Book.title.ilike(f'%{kw}%'),
                Author.name.ilike(f'%{kw}%'),
                Publisher.name.ilike(f'%{kw}%')
            )
        )

    # Lọc theo danh mục
    if category_id:
        query = query.filter(Book.category_id == category_id)

    # Lọc theo năm
    if year:
        query = query.filter(Book.publicationYear == year)

    # Lọc theo tác giả
    if author_id:
        query = query.filter(Book.author_id == author_id)

    # Lọc theo nhà xuất bản
    if publisher_id:
        query = query.filter(Book.publisher_id == publisher_id)

    # Tính tổng số kết quả và phân trang
    total = query.count()
    books = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, ceil(total / per_page))

    # Lấy dữ liệu cho dropdown
    categories = dao.load_book_categories()
    authors = Author.query.all()
    publishers = Publisher.query.all()

    return render_template(
        'product_list.html',
        books=books,
        categories=categories,
        authors=authors,
        publishers=publishers,
        current_page=page,
        total_pages=total_pages,
        kw=kw,
        category_id=category_id,
        year=year,
        author_id=author_id,
        publisher_id=publisher_id
    )


@app.route('/category/<int:category_id>')
def filter_by_category(category_id):
    page = request.args.get('page', 1, type=int)
    per_page = 6

    query = Book.query.filter(Book.category_id == category_id)

    total_products = query.count()
    total_pages = max(1, ceil(total_products / per_page))

    products = query.offset((page - 1) * per_page).limit(per_page).all()

    categories = dao.load_book_categories()

    return render_template('product_list.html',
                           books=products,
                           categories=categories,
                           category_id=category_id,
                           current_page=page if total_products > per_page else 1,
                           total_pages=total_pages if total_products > per_page else 1)


@app.route('/cart')
@login_required
def cart():
    cart = session.get('cart', {})
    return render_template('cart.html', cart=cart, stats=dao.cart_stats(cart))


@app.route('/api/add-cart', methods=['POST'])
@login_required
def add_to_cart():
    """API thêm sách vào giỏ - Tự động tạo Member nếu cần"""
    data = request.json
    book_id = str(data.get('id'))
    book = Book.query.get(book_id)

    if not book:
        return jsonify({'code': 404, 'message': 'Sách không tồn tại!'})

    # Tự động lấy hoặc tạo Member
    member = dao.get_or_create_member(current_user.id)
    if not member:
        return jsonify({'code': 403, 'message': 'Không thể tạo tài khoản mượn sách!'})

    cart = session.get('cart', {})
    current_quantity = cart[book_id]['quantity'] if book_id in cart else 0

    if current_quantity + 1 > book.availableCopies:
        return jsonify({'code': 400, 'message': 'Số lượng sách không đủ để mượn!'})

    if book_id in cart:
        cart[book_id]['quantity'] += 1
    else:
        cart[book_id] = {
            'id': book_id,
            'title': book.title,
            'author': book.author.name if book.author else 'Chưa rõ',
            'quantity': 1
        }

    session['cart'] = cart
    return jsonify({'code': 200, 'data': dao.cart_stats(cart)})

@app.route('/api/update-cart', methods=['POST'])
@login_required
def update_cart():
    data = request.json
    book_id = str(data.get('id'))
    change = data.get('change')

    cart = session.get('cart', {})
    book = Book.query.get(book_id)

    if not book:
        return jsonify({'code': 404, 'message': 'Sách không tồn tại!'})

    if book_id in cart:
        new_quantity = cart[book_id]['quantity'] + change

        if new_quantity > book.availableCopies:
            return jsonify({
                'code': 400,
                'message': 'Không đủ sách để mượn!',
                'available': book.availableCopies,
                'current_quantity': cart[book_id]['quantity']
            })

        if new_quantity > 0:
            cart[book_id]['quantity'] = new_quantity
        else:
            del cart[book_id]

    session['cart'] = cart
    cart_stats = dao.cart_stats(cart)

    return jsonify({
        'code': 200,
        'updated_quantity': cart[book_id]['quantity'] if book_id in cart else 0,
        'cart_total_quantity': cart_stats['total_quantity']
    })


@app.route('/api/delete-cart', methods=['POST'])
@login_required
def delete_cart():
    data = request.json
    book_id = str(data.get('id'))

    cart = session.get('cart', {})
    if book_id in cart:
        del cart[book_id]

    session['cart'] = cart
    cart_stats = dao.cart_stats(cart)

    return jsonify({
        'cart_total_quantity': cart_stats['total_quantity']
    })

@app.context_processor
def common_context():
    cart = session.get('cart', {})
    return {
        "cart_stats": dao.cart_stats(cart)
    }

@bp.route('/api/search_books', methods=['GET'])
def search_books():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'books': []})

    # Tìm sách theo ID hoặc tên chứa query
    books = Book.query.filter(
        (Book.id.like(f"%{query}%")) | (Book.title.ilike(f"%{query}%"))
    ).all()

    books_data = []
    for book in books:
        books_data.append({
            'id': book.id,
            'title': book.title,
            'is_existing': True  # sách đã có trong DB
        })

    # Nếu chưa có sách nào khớp (có thể là sách mới)
    if not books_data:
        # trả về một đối tượng sách tạm để JS hiển thị là sách mới
        books_data.append({
            'id': query,
            'title': '',
            'is_existing': False
        })

    return jsonify({'books': books_data})

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    """Trang chi tiết sách - Không cần kiểm tra Member"""
    book = dao.get_book_by_id(book_id)
    if not book:
        return render_template('404.html'), 404


    # Lấy sách cùng thể loại
    related_books = []
    if book.category_id:
        related_books = dao.get_books_by_category(
            book.category_id,
            limit=8,
            exclude_id=book.id
        )

    # Lấy đánh giá
    rating_data = dao.get_book_rating(book_id)

    # Kiểm tra trạng thái sách
    book_status = "Có sẵn" if book.availableCopies > 0 else "Hết sách"

    # Kiểm tra User có thể mượn không (không cần Member)
    can_borrow = current_user.is_authenticated and current_user.role == UserRole.MEMBER

    return render_template(
        'book_detail_new.html',
        book=book,
        related_books=related_books,
        rating_data=rating_data,
        book_status=book_status,
        can_borrow=can_borrow
    )

@app.route('/api/rate-book', methods=['POST'])
@login_required
def rate_book():
    """API để người dùng đánh giá sách"""
    try:
        data = request.json
        book_id = data.get('book_id')
        rating = data.get('rating')
        comment = data.get('comment', '')

        if not book_id or not rating:
            return jsonify({'code': 400, 'message': 'Thiếu thông tin đánh giá!'})

        if not (1 <= int(rating) <= 5):
            return jsonify({'code': 400, 'message': 'Điểm đánh giá phải từ 1 đến 5!'})

        # Kiểm tra sách có tồn tại không
        book = Book.query.get(book_id)
        if not book:
            return jsonify({'code': 404, 'message': 'Sách không tồn tại!'})

        # Kiểm tra member có tồn tại không
        member = Member.query.filter_by(user_id=current_user.id).first()
        if not member:
            return jsonify({'code': 403, 'message': 'Bạn cần có tài khoản thành viên để đánh giá!'})

        # Kiểm tra đã đánh giá chưa
        existing_rating = Rating.query.filter_by(
            member_id=member.id,
            book_id=book_id
        ).first()

        if existing_rating:
            # Cập nhật đánh giá cũ
            existing_rating.score = rating
            existing_rating.comment = comment
        else:
            # Tạo đánh giá mới
            new_rating = Rating(
                member_id=member.id,
                book_id=book_id,
                score=rating,
                comment=comment
            )
            db.session.add(new_rating)

        db.session.commit()
        return jsonify({'code': 200, 'message': 'Đánh giá thành công!'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'Lỗi server: {str(e)}'})


@app.route('/api/submit-borrow-request', methods=['POST'])
@login_required
def submit_borrow_request():
    """API gửi yêu cầu mượn sách theo batch"""
    try:
        # Tự động lấy hoặc tạo Member
        member = dao.get_or_create_member(current_user.id)
        if not member:
            return jsonify({'code': 403, 'message': 'Không thể tạo tài khoản mượn sách!'})

        # Kiểm tra điều kiện mượn
        eligibility = dao.check_member_borrow_eligibility(member.id)
        if not eligibility['eligible']:
            return jsonify({'code': 400, 'message': eligibility['message']})

        cart = session.get('cart', {})
        if not cart:
            return jsonify({'code': 400, 'message': 'Giỏ mượn trống!'})

        # Sử dụng function mới để tạo batch
        result = dao.submit_batch_borrow_request(member.id, cart)

        if result['success']:
            session.pop('cart', None)  # Xóa giỏ hàng

            return jsonify({
                'code': 200,
                'message': f'Yêu cầu mượn sách đã được tạo (Mã: {result["batch"].batchCode})',
                'batch_code': result["batch"].batchCode,
                'total_books': result["batch"].totalBooks
            })
        else:
            return jsonify({'code': 400, 'message': 'Có lỗi xảy ra khi tạo yêu cầu'})

    except Exception as e:
        return jsonify({'code': 500, 'message': f'Lỗi server: {str(e)}'})


# Thêm API mới để lấy danh sách batch
@app.route('/my-borrow-batches')
@login_required
def my_borrow_batches():
    """Xem danh sách batch yêu cầu mượn"""
    member = Member.query.filter_by(user_id=current_user.id).first()
    if not member:
        flash('Bạn cần đăng ký thành viên!', 'error')
        return redirect(url_for('index'))

    batches = dao.get_member_borrow_batches(member.id)
    return render_template('my_borrow_batches.html', batches=batches)


@app.route('/batch-detail/<int:batch_id>')
@login_required
def batch_detail(batch_id):
    """Xem chi tiết batch"""
    member = Member.query.filter_by(user_id=current_user.id).first()
    if not member:
        flash('Bạn cần đăng ký thành viên!', 'error')
        return redirect(url_for('index'))

    batch_details = dao.get_batch_with_details(batch_id)
    if not batch_details or batch_details['batch'].member_id != member.id:
        flash('Không tìm thấy batch hoặc không có quyền truy cập!', 'error')
        return redirect(url_for('my_borrow_batches'))

    return render_template('batch_detail.html', **batch_details)


@app.route('/api/check-borrow-eligibility/<int:book_id>')
@login_required
def check_borrow_eligibility(book_id):
    """API kiểm tra điều kiện mượn sách"""
    try:
        member = Member.query.filter_by(user_id=current_user.id).first()
        if not member:
            return jsonify({'eligible': False, 'message': 'Bạn cần đăng ký thành viên!'})

        book = Book.query.get(book_id)
        if not book:
            return jsonify({'eligible': False, 'message': 'Sách không tồn tại!'})

        # Kiểm tra điều kiện member
        eligibility = dao.check_member_borrow_eligibility(member.id)

        # Thông tin trạng thái sách
        book_available = book.availableCopies > 0

        return jsonify({
            'eligible': eligibility['eligible'] and book_available,
            'member_status': eligibility,
            'book_status': {
                'available': book_available,
                'available_copies': book.availableCopies,
                'can_wait': not book_available
            }
        })

    except Exception as e:
        return jsonify({'eligible': False, 'message': f'Lỗi server: {str(e)}'})




@app.route('/api/add-to-waiting-list', methods=['POST'])
@login_required
def add_to_waiting_list_api():
    """API thêm vào danh sách chờ"""
    try:
        data = request.json
        book_id = data.get('book_id')

        member = Member.query.filter_by(user_id=current_user.id).first()
        if not member:
            return jsonify({'success': False, 'message': 'Bạn cần đăng ký thành viên!'})

        result = dao.add_to_waiting_list(member.id, book_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'})



@app.route('/api/cancel-batch', methods=['POST'])
@login_required
def cancel_batch():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'message': 'Dữ liệu request không hợp lệ'
            }), 400

        batch_id = data.get('batch_id')
        if not batch_id:
            return jsonify({
                'code': 400,
                'message': 'Thiếu batch_id'
            }), 400

        # Import model nếu chưa có
        from BBOOK.BB.models import BorrowRequestBatch

        # Tìm batch
        batch = BorrowRequestBatch.query.get(batch_id)
        if not batch:
            return jsonify({
                'code': 404,
                'message': 'Không tìm thấy yêu cầu mượn!'
            }), 404

        # Kiểm tra quyền sở hữu
        member = Member.query.filter_by(user_id=current_user.id).first()
        if not member or batch.member_id != member.id:
            return jsonify({
                'code': 403,
                'message': 'Không có quyền hủy yêu cầu này!'
            }), 403

        # Chỉ cho phép hủy batch đang Pending
        if batch.batchStatus != StatusRequest.PENDING:
            return jsonify({
                'code': 400,
                'message': 'Chỉ có thể hủy yêu cầu đang chờ duyệt!'
            }), 400

        # Hủy tất cả requests trong batch
        requests_in_batch = BorrowRequest.query.filter_by(batch_id=batch_id).all()

        for req in requests_in_batch:
            db.session.delete(req)

        # Xóa batch
        db.session.delete(batch)
        db.session.commit()

        return jsonify({
            'code': 200,
            'message': f'Đã hủy yêu cầu mượn {batch.batchCode} thành công!',
            'cancelled_requests': len(requests_in_batch)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'message': f'Lỗi server: {str(e)}'
        }), 500


@app.route('/admin/api/validate-book-data', methods=['POST'])
@login_required
def validate_book_data():
    """API validate dữ liệu sách trước khi submit"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403

    try:
        data = request.json
        errors = []
        warnings = []

        # Kiểm tra tên sách trùng lặp
        title = data.get('title', '').strip()
        if title:
            existing_book = Book.query.filter(Book.title.ilike(title)).first()
            if existing_book:
                warnings.append(f'Đã có sách với tên "{title}" (ID: {existing_book.id})')

        # Kiểm tra thông tin bắt buộc cho sách mới
        if data.get('is_new_book'):
            required_fields = ['title', 'author_id', 'category_id', 'publisher_id', 'publication_year']
            for field in required_fields:
                if not data.get(field):
                    errors.append(f'Thiếu thông tin: {field}')

            # Kiểm tra năm xuất bản hợp lệ
            year = data.get('publication_year')
            if year:
                current_year = datetime.now().year
                if year < 1800 or year > current_year + 1:
                    errors.append(f'Năm xuất bản không hợp lệ: {year}')

        # Kiểm tra số lượng
        quantity = data.get('quantity')
        if not quantity or quantity <= 0:
            errors.append('Số lượng phải lớn hơn 0')
        elif quantity > 10000:
            warnings.append('Số lượng rất lớn, vui lòng kiểm tra lại')

        return jsonify({
            'success': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'}), 500


@app.route('/admin/api/get-book-suggestions')
@login_required
def get_book_suggestions():
    """API gợi ý sách dựa trên input của user"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'suggestions': []}), 403

    try:
        query = request.args.get('q', '').strip()
        suggestion_type = request.args.get('type', 'title')  # 'title', 'author', 'publisher'

        suggestions = []

        if len(query) >= 2:
            if suggestion_type == 'title':
                # Gợi ý tên sách
                books = Book.query.filter(Book.title.ilike(f'%{query}%')).limit(5).all()
                suggestions = [{'value': book.title, 'id': book.id} for book in books]

            elif suggestion_type == 'author':
                # Gợi ý tác giả
                authors = Author.query.filter(Author.name.ilike(f'%{query}%')).limit(5).all()
                suggestions = [{'value': author.name, 'id': author.id} for author in authors]

            elif suggestion_type == 'publisher':
                # Gợi ý nhà xuất bản
                publishers = Publisher.query.filter(Publisher.name.ilike(f'%{query}%')).limit(5).all()
                suggestions = [{'value': pub.name, 'id': pub.id} for pub in publishers]

        return jsonify({'suggestions': suggestions})

    except Exception as e:
        return jsonify({'suggestions': [], 'error': str(e)})


@app.route('/admin/api/create-new-entity', methods=['POST'])
@login_required
def create_new_entity():
    """API tạo nhanh Author, Publisher, Category mới"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'}), 403

    try:
        data = request.json
        entity_type = data.get('type')  # 'author', 'publisher', 'category'
        name = data.get('name', '').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Tên không được để trống'})

        if entity_type == 'author':
            # Kiểm tra trùng lặp
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                return jsonify({'success': False, 'message': 'Tác giả đã tồn tại'})

            new_entity = Author(name=name)

        elif entity_type == 'publisher':
            existing = Publisher.query.filter(Publisher.name.ilike(name)).first()
            if existing:
                return jsonify({'success': False, 'message': 'Nhà xuất bản đã tồn tại'})

            new_entity = Publisher(name=name)

        elif entity_type == 'category':
            existing = BookCategory.query.filter(BookCategory.categoryName.ilike(name)).first()
            if existing:
                return jsonify({'success': False, 'message': 'Danh mục đã tồn tại'})

            description = data.get('description', '')
            new_entity = BookCategory(categoryName=name, description=description)

        else:
            return jsonify({'success': False, 'message': 'Loại entity không hợp lệ'})

        db.session.add(new_entity)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Đã tạo {entity_type} mới thành công',
            'entity': {
                'id': new_entity.id,
                'name': name
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})


@app.route('/admin/api/import-statistics')
@login_required
def import_statistics():
    from datetime import datetime

    # Lấy tham số lọc từ request
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    # Câu query gốc: tổng số lượng nhập theo sách
    query = db.session.query(
        Book.title,
        func.sum(ImportRecord.quantity).label("total_quantity")
    ).join(Book, ImportRecord.book_id == Book.id)

    # Nếu có lọc theo năm
    if year:
        query = query.filter(func.extract("year", ImportRecord.importDate) == year)

    # Nếu có lọc theo tháng
    if month:
        query = query.filter(func.extract("month", ImportRecord.importDate) == month)

    # Nhóm theo sách + sắp xếp giảm dần
    results = (
        query.group_by(Book.id, Book.title)
        .order_by(func.sum(ImportRecord.quantity).desc())
        .limit(5)  # Lấy top 5 sách nhập nhiều nhất
        .all()
    )

    # Convert dữ liệu sang JSON
    data = [{"book": r.title, "total_quantity": int(r.total_quantity)} for r in results]

    return jsonify(data)


# Thêm các import cần thiết ở đầu file index.py
from datetime import date, datetime
from flask import jsonify, request
from BBOOK.BB.models import Book, Author, BookCategory, Publisher, Library, Librarian, ImportRecord
from BBOOK.BB import db


# Thêm đoạn code này vào cuối file index.py

# =================== API FOR IMPORT RECORDS ===================

@app.route('/api/check_book/<int:book_id>', methods=['GET'])
def check_book(book_id):
    """
    API để kiểm tra sách đã tồn tại hay chưa.
    Trả về thông tin sách nếu tồn tại, ngược lại lỗi 404.
    """
    book = Book.query.get(book_id)
    if book:
        return jsonify({
            'id': book.id,
            'title': book.title,
            'author': book.author.name if book.author else 'N/A',
            'category': book.category.categoryName if book.category else 'N/A',
            'publisher': book.publisher.name if book.publisher else 'N/A',
            'publication_year': book.publicationYear,
            'available_copies': book.availableCopies
        })
    return jsonify({'message': 'Book not found'}), 404


@app.route('/api/select_data', methods=['GET'])
def get_select_data():
    """
    API cung cấp dữ liệu cho các trường <select> (dropdown).
    """
    authors = [{'id': a.id, 'text': a.name} for a in Author.query.all()]
    categories = [{'id': c.id, 'text': c.categoryName} for c in BookCategory.query.all()]
    publishers = [{'id': p.id, 'text': p.name} for p in Publisher.query.all()]
    libraries = [{'id': l.id, 'text': l.address} for l in Library.query.all()]
    librarians = [{'id': li.id, 'text': li.user.fullName} for li in Librarian.query.join(Librarian.user).all()]

    return jsonify({
        'authors': authors,
        'categories': categories,
        'publishers': publishers,
        'libraries': libraries,
        'librarians': librarians
    })


@app.route('/api/import_records', methods=['POST'])
def create_import_record():
    """
    API để xử lý việc tạo phiếu nhập sách.
    """
    data = request.json
    book_id = data.get('book_id')
    quantity = int(data.get('quantity', 0))

    try:
        # --- Trường hợp sách đã tồn tại ---
        if book_id:
            book = Book.query.get(book_id)
            if not book:
                return jsonify({'success': False, 'message': 'Sách không tồn tại!'}), 404

            # Cập nhật số lượng
            book.availableCopies += quantity

        # --- Trường hợp sách mới ---
        else:
            # Xử lý tác giả, danh mục, nhà xuất bản (có thể là mới hoặc cũ)
            author_name = data.get('author')
            category_name = data.get('category')
            publisher_name = data.get('publisher')

            # Hàm hỗ trợ để lấy hoặc tạo mới
            def get_or_create(model, name_field, name_value):
                instance = model.query.filter(getattr(model, name_field) == name_value).first()
                if not instance:
                    instance = model(**{name_field: name_value})
                    db.session.add(instance)
                    db.session.flush()  # Để lấy ID ngay lập tức
                return instance.id

            author_id = get_or_create(Author, 'name', author_name)
            category_id = get_or_create(BookCategory, 'categoryName', category_name)
            publisher_id = get_or_create(Publisher, 'name', publisher_name)

            book = Book(
                title=data.get('title'),
                author_id=author_id,
                category_id=category_id,
                publisher_id=publisher_id,
                publicationYear=int(data.get('publication_year')),
                availableCopies=quantity,
                # =========================================================
                # SỬA LỖI Ở ĐÂY: Thêm library_id khi tạo sách mới
                library_id=int(data.get('library_id'))
                # =========================================================
            )
            db.session.add(book)
            db.session.flush()  # Để lấy book.id

        # --- Tạo phiếu nhập trong mọi trường hợp ---
        record = ImportRecord(
            book_id=book.id,
            bookTitle=book.title,  # Lưu lại tiêu đề để tiện truy vấn
            quantity=quantity,
            importDate=datetime.strptime(data.get('import_date'), '%Y-%m-%d').date(),
            library_id=int(data.get('library_id')),
            librarian_id=int(data.get('librarian_id')),
            description=data.get('description')
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Tạo phiếu nhập thành công!'})

    except Exception as e:
        db.session.rollback()
        # In ra lỗi chi tiết hơn để gỡ rối
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    from BBOOK.BB.admin import *

    app.run(debug=True, port=5000)

# 123
