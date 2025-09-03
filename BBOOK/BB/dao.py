import hashlib
from BBOOK.BB import db
from BBOOK.BB.models import BookCategory, Book, User


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
        products = products.filter(Book.name.contains(kw))
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
        Book.name.ilike(f"%{kw}%")
    ).all()

def load_books_by_category(category_id):
    return Book.query.filter(Book.category_id == category_id).all()

def load_book_categories():
    categories = BookCategory.query.order_by('id').all()
    for category in categories:
        category.product_count = Book.query.filter(Book.category_id == category.id).count()
    return categories


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
