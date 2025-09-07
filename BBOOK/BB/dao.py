import hashlib
from BBOOK.BB import db
from BBOOK.BB.models import BookCategory, Book, User, Author, Publisher


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


def add_user(fullName, username, password, **kwargs):
    password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())
    user = User(fullName=fullName.strip(),
                username=username.strip(),
                password=password,
                email=kwargs.get('email'),
                avatar=kwargs.get('avatar'))
    db.session.add(user)
    db.session.commit()


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