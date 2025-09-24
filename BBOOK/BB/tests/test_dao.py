import pytest
import hashlib
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from BBOOK.BB import dao
from BBOOK.BB.models import *
from BBOOK.BB import db


class TestUserFunctions:
    """Test các functions liên quan đến User"""

    def test_add_user_success(self, test_db):
        """Test thêm user thành công"""
        user = dao.add_user(
            fullName='John Doe',
            username='johndoe',
            password='password123',
            email='john@example.com'
        )

        assert user is not None
        assert user.fullName == 'John Doe'
        assert user.username == 'johndoe'
        assert user.email == 'john@example.com'
        # Password được hash
        expected_hash = str(hashlib.md5('password123'.encode('utf-8')).hexdigest())
        assert user.password == expected_hash

        # Kiểm tra Member tự động được tạo
        member = Member.query.filter_by(user_id=user.id).first()
        assert member is not None
        assert member.borrowLimit == 5
        assert member.statusPenalty == StatusPenalty.LEVEL1

    def test_add_user_duplicate_username(self, test_db):
        """Test thêm user với username trùng lặp"""
        # Thêm user đầu tiên
        dao.add_user('User 1', 'testuser', 'pass1', email='user1@test.com')

        # Thử thêm user thứ hai với username trùng
        with pytest.raises(Exception):
            dao.add_user('User 2', 'testuser', 'pass2', email='user2@test.com')

    def test_check_login_success(self, test_db):
        """Test đăng nhập thành công"""
        # Tạo user
        dao.add_user('Test User', 'testuser', 'password', email='test@test.com')

        # Test login
        user = dao.check_login('testuser', 'password')
        assert user is not None
        assert user.username == 'testuser'
        assert user.fullName == 'Test User'

    def test_check_login_wrong_password(self, test_db):
        """Test đăng nhập với password sai"""
        dao.add_user('Test User', 'testuser', 'password', email='test@test.com')

        user = dao.check_login('testuser', 'wrongpassword')
        assert user is None

    def test_check_login_wrong_username(self, test_db):
        """Test đăng nhập với username không tồn tại"""
        user = dao.check_login('nonexistent', 'password')
        assert user is None

    def test_get_user_by_id_success(self, test_db):
        """Test lấy user theo ID thành công"""
        user = dao.add_user('Test User', 'testuser', 'password', email='test@test.com')

        found_user = dao.get_user_by_id(user.id)
        assert found_user is not None
        assert found_user.id == user.id
        assert found_user.username == 'testuser'

    def test_get_user_by_id_not_found(self, test_db):
        """Test lấy user với ID không tồn tại"""
        user = dao.get_user_by_id(99999)
        assert user is None


class TestAuthenticationFunctions:
    """Test các functions xác thực"""

    def test_check_login_with_role_filter_member(self, test_db):
        """Test login với filter role MEMBER"""
        user = dao.add_user('Member User', 'member', 'password', email='member@test.com')
        user.role = UserRole.MEMBER
        test_db.session.commit()

        # Login với role filter
        found_user = dao.check_login('member', 'password', role=UserRole.MEMBER)
        assert found_user is not None
        assert found_user.role == UserRole.MEMBER

    def test_check_login_with_role_filter_fail(self, test_db):
        """Test login với role filter không khớp"""
        user = dao.add_user('Member User', 'member', 'password', email='member@test.com')
        user.role = UserRole.MEMBER
        test_db.session.commit()

        # Thử login với role ADMIN
        found_user = dao.check_login('member', 'password', role=UserRole.ADMIN)
        assert found_user is None

    def test_check_login_with_multiple_roles(self, test_db):
        """Test login với multiple roles filter"""
        user = dao.add_user('Librarian User', 'librarian', 'password', email='lib@test.com')
        user.role = UserRole.LIBRARIAN
        test_db.session.commit()

        # Login với list roles
        found_user = dao.check_login('librarian', 'password',
                                     role=[UserRole.LIBRARIAN, UserRole.ADMIN])
        assert found_user is not None
        assert found_user.role == UserRole.LIBRARIAN

    def test_check_login_empty_credentials(self, test_db):
        """Test login với thông tin trống"""
        assert dao.check_login('', 'password') is None
        assert dao.check_login('username', '') is None
        assert dao.check_login(None, None) is None

    def test_check_login_whitespace_handling(self, test_db):
        """Test login với khoảng trắng"""
        dao.add_user('Test User', 'testuser', 'password', email='test@test.com')

        # Login với khoảng trắng
        user = dao.check_login(' testuser ', ' password ')
        assert user is not None
        assert user.username == 'testuser'


class TestMemberFunctions:
    """Test các functions liên quan đến Member"""

    def test_get_or_create_member_existing(self, test_db, sample_user, sample_member):
        """Test lấy member đã tồn tại"""
        member = dao.get_or_create_member(sample_user.id)

        assert member is not None
        assert member.id == sample_member.id
        assert member.user_id == sample_user.id

    def test_get_or_create_member_create_new(self, test_db):
        """Test tạo member mới khi chưa tồn tại"""
        # Tạo user không có member
        user = User(
            username='nomember',
            email='nomember@test.com',
            fullName='No Member User',
            role=UserRole.MEMBER
        )
        test_db.session.add(user)
        test_db.session.commit()

        # Get or create member
        member = dao.get_or_create_member(user.id)

        assert member is not None
        assert member.user_id == user.id
        assert member.borrowLimit == 5
        assert member.statusPenalty == StatusPenalty.LEVEL1

    def test_get_or_create_member_non_member_role(self, test_db):
        """Test với user không có role MEMBER"""
        user = User(
            username='admin',
            email='admin@test.com',
            fullName='Admin User',
            role=UserRole.ADMIN
        )
        test_db.session.add(user)
        test_db.session.commit()

        member = dao.get_or_create_member(user.id)
        assert member is None


class TestBookFunctions:
    """Test các functions liên quan đến Book"""

    def setup_sample_books(self, test_db):
        """Helper method tạo sample books"""
        # Tạo dependencies
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        category = BookCategory(categoryName='Science')

        test_db.session.add_all([publisher, library, category])
        test_db.session.flush()

        # Tạo books
        books = [
            Book(title='Python Programming', publisher_id=publisher.id,
                 library_id=library.id, category_id=category.id, publicationYear=2023),
            Book(title='Java Basics', publisher_id=publisher.id,
                 library_id=library.id, category_id=category.id, publicationYear=2022),
            Book(title='Data Science', publisher_id=publisher.id,
                 library_id=library.id, category_id=category.id, publicationYear=2024)
        ]

        test_db.session.add_all(books)
        test_db.session.commit()
        return books, category

    def test_load_books_all(self, test_db):
        """Test load tất cả books"""
        books, _ = self.setup_sample_books(test_db)

        result = dao.load_books()
        assert len(result) == 3
        titles = [book.title for book in result]
        assert 'Python Programming' in titles
        assert 'Java Basics' in titles
        assert 'Data Science' in titles

    def test_load_books_with_keyword(self, test_db):
        """Test load books với keyword"""
        self.setup_sample_books(test_db)

        result = dao.load_books(kw='Python')
        assert len(result) == 1
        assert result[0].title == 'Python Programming'

    def test_search_books_success(self, test_db):
        """Test search books thành công"""
        self.setup_sample_books(test_db)

        result = dao.search_books('Java')
        assert len(result) == 1
        assert result[0].title == 'Java Basics'

    def test_search_books_case_insensitive(self, test_db):
        """Test search books không phân biệt hoa thường"""
        self.setup_sample_books(test_db)

        result = dao.search_books('python')  # lowercase
        assert len(result) == 1
        assert result[0].title == 'Python Programming'

    def test_search_books_empty_keyword(self, test_db):
        """Test search với keyword trống"""
        self.setup_sample_books(test_db)

        assert dao.search_books('') == []
        assert dao.search_books(None) == []

    def test_get_book_by_id_success(self, test_db):
        """Test lấy book theo ID"""
        books, _ = self.setup_sample_books(test_db)
        book_id = books[0].id

        result = dao.get_book_by_id(book_id)
        assert result is not None
        assert result.title == 'Python Programming'

    def test_load_books_by_category(self, test_db):
        """Test load books theo category"""
        books, category = self.setup_sample_books(test_db)

        result = dao.load_books_by_category(category.id)
        assert len(result) == 3  # All books in same category


class TestBorrowingSystemFunctions:
    """Test các functions của hệ thống mượn sách"""

    def test_check_member_borrow_eligibility_success(self, test_db, sample_member):
        """Test kiểm tra điều kiện mượn sách thành công"""
        result = dao.check_member_borrow_eligibility(sample_member.id)

        assert result['eligible'] is True
        assert result['available_slots'] == 5  # borrowLimit = 5, currentBorrowCount = 0

    def test_check_member_borrow_eligibility_max_books(self, test_db, sample_member):
        """Test không thể mượn khi đã đạt giới hạn"""
        # Set member đã mượn max books
        sample_member.currentBorrowCount = sample_member.borrowLimit
        test_db.session.commit()

        result = dao.check_member_borrow_eligibility(sample_member.id)

        assert result['eligible'] is False
        assert 'tối đa' in result['message']

    def test_check_member_borrow_eligibility_account_locked(self, test_db, sample_member):
        """Test không thể mượn khi tài khoản bị khóa"""
        sample_member.statusPenalty = StatusPenalty.LEVEL4
        test_db.session.commit()

        result = dao.check_member_borrow_eligibility(sample_member.id)

        assert result['eligible'] is False
        assert 'bị khóa' in result['message']

    def test_check_member_borrow_eligibility_overdue_books(self, test_db, sample_member):
        """Test không thể mượn khi có sách quá hạn"""
        # Mock has_overdue_books method
        with patch.object(sample_member, 'has_overdue_books', return_value=True):
            result = dao.check_member_borrow_eligibility(sample_member.id)

            assert result['eligible'] is False
            assert 'quá hạn' in result['message']

    def test_check_member_borrow_eligibility_member_not_found(self, test_db):
        """Test với member không tồn tại"""
        result = dao.check_member_borrow_eligibility(99999)

        assert result['eligible'] is False
        assert 'Không tìm thấy' in result['message']

    def test_cart_stats_empty(self, test_db):
        """Test thống kê cart rỗng"""
        result = dao.cart_stats(None)
        assert result['total_quantity'] == 0

        result = dao.cart_stats({})
        assert result['total_quantity'] == 0

    def test_cart_stats_with_items(self, test_db):
        """Test thống kê cart có items"""
        cart = {
            '1': {'quantity': 2, 'title': 'Book 1'},
            '2': {'quantity': 1, 'title': 'Book 2'},
            '3': {'quantity': 3, 'title': 'Book 3'}
        }

        result = dao.cart_stats(cart)
        assert result['total_quantity'] == 6

    def test_add_to_waiting_list_success(self, test_db, sample_member):
        """Test thêm vào waiting list thành công"""
        # Tạo book
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(title='Popular Book', publisher_id=publisher.id,
                    library_id=library.id, publicationYear=2023, availableCopies=0)
        test_db.session.add(book)
        test_db.session.commit()

        result = dao.add_to_waiting_list(sample_member.id, book.id)

        assert result['success'] is True
        assert result['position'] == 1

    def test_add_to_waiting_list_already_exists(self, test_db, sample_member):
        """Test thêm vào waiting list khi đã tồn tại"""
        # Setup book
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(title='Popular Book', publisher_id=publisher.id,
                    library_id=library.id, publicationYear=2023)
        test_db.session.add(book)
        test_db.session.flush()

        # Thêm lần đầu
        dao.add_to_waiting_list(sample_member.id, book.id)

        # Thử thêm lần thứ hai
        result = dao.add_to_waiting_list(sample_member.id, book.id)

        assert result['success'] is False
        assert 'đã có trong danh sách' in result['message']


class TestBatchRequestFunctions:
    """Test các functions liên quan đến Batch Requests"""

    def test_generate_batch_code(self, test_db):
        """Test sinh batch code"""
        code = dao.generate_batch_code()

        # Code format: BR{YEAR}{NUMBER:03d}
        import datetime
        year = datetime.datetime.now().year
        expected_prefix = f"BR{year}"

        assert code.startswith(expected_prefix)
        assert len(code) == len(expected_prefix) + 3  # 3 digits
        assert code[-3:].isdigit()

    def test_create_borrow_request_batch(self, test_db, sample_member):
        """Test tạo batch request"""
        batch = dao.create_borrow_request_batch(
            member_id=sample_member.id,
            total_books=5,
            notes='Test batch'
        )

        assert batch is not None
        assert batch.member_id == sample_member.id
        assert batch.totalBooks == 5
        assert batch.notes == 'Test batch'
        assert batch.batchStatus == StatusRequest.PENDING

    def test_submit_batch_borrow_request_success(self, test_db, sample_member):
        """Test submit batch borrow request thành công"""
        # Setup books
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book1 = Book(title='Book 1', publisher_id=publisher.id,
                     library_id=library.id, publicationYear=2023, availableCopies=5)
        book2 = Book(title='Book 2', publisher_id=publisher.id,
                     library_id=library.id, publicationYear=2023, availableCopies=3)
        test_db.session.add_all([book1, book2])
        test_db.session.commit()

        # Setup cart
        cart_items = {
            str(book1.id): {'quantity': 2, 'title': 'Book 1'},
            str(book2.id): {'quantity': 1, 'title': 'Book 2'}
        }

        result = dao.submit_batch_borrow_request(sample_member.id, cart_items)

        assert result['success'] is True
        assert result['batch'] is not None
        assert len(result['requests']) == 3  # 2 + 1 requests

    def test_submit_batch_borrow_request_insufficient_copies(self, test_db, sample_member):
        """Test submit khi không đủ số lượng sách"""
        # Setup book với insufficient copies
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(title='Popular Book', publisher_id=publisher.id,
                    library_id=library.id, publicationYear=2023, availableCopies=1)
        test_db.session.add(book)
        test_db.session.commit()

        cart_items = {
            str(book.id): {'quantity': 3, 'title': 'Popular Book'}  # Request 3, only 1 available
        }

        with pytest.raises(Exception) as exc_info:
            dao.submit_batch_borrow_request(sample_member.id, cart_items)

        assert 'không đủ số lượng' in str(exc_info.value)

    def test_get_member_borrow_batches(self, test_db, sample_member):
        """Test lấy danh sách batch của member"""
        # Tạo một số batches
        batch1 = dao.create_borrow_request_batch(sample_member.id, 2)
        batch2 = dao.create_borrow_request_batch(sample_member.id, 3)
        test_db.session.commit()

        batches = dao.get_member_borrow_batches(sample_member.id)

        assert len(batches) == 2
        batch_ids = [b.id for b in batches]
        assert batch1.id in batch_ids
        assert batch2.id in batch_ids

    def test_get_batch_with_details(self, test_db, sample_member):
        """Test lấy chi tiết batch"""
        # Tạo batch với requests
        batch = dao.create_borrow_request_batch(sample_member.id, 1)
        test_db.session.flush()

        # Setup book và request
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(title='Test Book', publisher_id=publisher.id,
                    library_id=library.id, publicationYear=2023)
        test_db.session.add(book)
        test_db.session.flush()

        request = BorrowRequest(
            member_id=sample_member.id,
            book_id=book.id,
            batch_id=batch.id
        )
        test_db.session.add(request)
        test_db.session.commit()

        result = dao.get_batch_with_details(batch.id)

        assert result is not None
        assert result['batch'].id == batch.id
        assert len(result['requests']) == 1
        assert len(result['books']) == 1
        assert result['books'][0].title == 'Test Book'


class TestStatisticsFunctions:
    """Test các functions thống kê"""

    def test_get_borrow_statistics(self, test_db, sample_member):
        """Test lấy thống kê mượn sách"""
        # Setup data
        today = date.today()

        # Tạo pending requests
        batch1 = BorrowRequestBatch(member_id=sample_member.id, batchCode='BR001',
                                    batchStatus=StatusRequest.PENDING, totalBooks=2)
        batch2 = BorrowRequestBatch(member_id=sample_member.id, batchCode='BR002',
                                    batchStatus=StatusRequest.PENDING, totalBooks=1)
        test_db.session.add_all([batch1, batch2])

        # Tạo borrowed books (chưa trả)
        borrow1 = BorrowRecord(member_id=sample_member.id, borrowDate=today, returnDate=None)
        borrow2 = BorrowRecord(member_id=sample_member.id, borrowDate=today, returnDate=None)
        test_db.session.add_all([borrow1, borrow2])

        # Tạo overdue book
        overdue_date = today - timedelta(days=35)
        borrow3 = BorrowRecord(member_id=sample_member.id, borrowDate=overdue_date, returnDate=None)
        test_db.session.add(borrow3)

        # Tạo today requests
        request1 = BorrowRequest(member_id=sample_member.id, book_id=1, requestDate=today)
        request2 = BorrowRequest(member_id=sample_member.id, book_id=2, requestDate=today)
        test_db.session.add_all([request1, request2])

        test_db.session.commit()

        stats = dao.get_borrow_statistics()

        assert stats['pending_requests'] == 2  # 2 pending batches
        assert stats['borrowed_books'] == 3  # 3 unreturned records
        assert stats['overdue_books'] == 1  # 1 overdue record
        assert stats['today_requests'] == 2  # 2 requests today

    def test_get_borrow_management_stats(self, test_db, sample_member):
        """Test lấy thống kê quản lý mượn trả"""
        # Setup similar data as above
        today = date.today()

        batch = BorrowRequestBatch(member_id=sample_member.id, batchCode='BR001',
                                   batchStatus=StatusRequest.PENDING, totalBooks=1,
                                   requestDate=today)
        test_db.session.add(batch)

        borrow_record = BorrowRecord(member_id=sample_member.id, borrowDate=today, returnDate=None)
        test_db.session.add(borrow_record)
        test_db.session.commit()

        stats = dao.get_borrow_management_stats()

        assert 'pending_requests' in stats
        assert 'borrowed_books' in stats
        assert 'overdue_books' in stats
        assert 'today_requests' in stats
        assert stats['pending_requests'] >= 1
        assert stats['borrowed_books'] >= 1
        assert stats['today_requests'] >= 1