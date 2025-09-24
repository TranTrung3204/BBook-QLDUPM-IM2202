import pytest
from datetime import date, timedelta
from BBOOK.BB.models import *
from BBOOK.BB import db


class TestEnumClasses:
    """Test các Enum classes"""

    def test_status_request_enum(self):
        """Test StatusRequest enum values"""
        assert StatusRequest.PENDING.value == "Pending"
        assert StatusRequest.APPROVED.value == "Approved"
        assert StatusRequest.REJECTED.value == "Rejected"

        # Test all enum values exist
        expected_values = ["Pending", "Approved", "Rejected"]
        actual_values = [status.value for status in StatusRequest]
        assert set(expected_values) == set(actual_values)

    def test_status_penalty_enum(self):
        """Test StatusPenalty enum values"""
        assert StatusPenalty.LEVEL1.value == 1
        assert StatusPenalty.LEVEL2.value == 2
        assert StatusPenalty.LEVEL3.value == 3
        assert StatusPenalty.LEVEL4.value == 4
        assert StatusPenalty.LEVEL5.value == 5

        # Test enum order
        levels = [level.value for level in StatusPenalty]
        assert levels == [1, 2, 3, 4, 5]

    def test_user_role_enum(self):
        """Test UserRole enum values"""
        assert UserRole.MEMBER.value == 1
        assert UserRole.LIBRARIAN.value == 2
        assert UserRole.ADMIN.value == 3

        # Test role hierarchy
        assert UserRole.MEMBER.value < UserRole.LIBRARIAN.value
        assert UserRole.LIBRARIAN.value < UserRole.ADMIN.value

    def test_approval_type_enum(self):
        """Test ApprovalType enum values"""
        assert ApprovalType.NORMAL.value == "Normal"
        assert ApprovalType.CONDITIONAL.value == "Conditional"
        assert ApprovalType.REJECTED.value == "Rejected"


class TestUserModel:
    """Test User model"""

    def test_create_user_basic(self, test_db):
        """Test tạo user cơ bản"""
        user = User(
            username='newuser',
            password='hashedpassword',
            email='newuser@test.com',
            fullName='New User',
            role=UserRole.MEMBER
        )
        test_db.session.add(user)
        test_db.session.commit()

        assert user.id is not None
        assert user.username == 'newuser'
        assert user.email == 'newuser@test.com'
        assert user.role == UserRole.MEMBER
        assert user.isActive is True  # Default value
        assert user.registrationDate is not None

    def test_user_string_representation(self, test_db):
        """Test __str__ method của User"""
        user = User(username='test', fullName='Test User', email='test@test.com')
        test_db.session.add(user)
        test_db.session.commit()

        assert str(user) == 'Test User'

    def test_user_relationships(self, test_db):
        """Test relationships của User với Member và Librarian"""
        user = User(username='test', fullName='Test User', email='test@test.com')
        test_db.session.add(user)
        test_db.session.flush()  # Để lấy user.id

        member = Member(user_id=user.id, borrowLimit=5)
        test_db.session.add(member)
        test_db.session.commit()

        # Test relationship
        assert user.member is not None
        assert user.member.borrowLimit == 5
        assert member.user.fullName == 'Test User'

    def test_user_unique_constraints(self, test_db):
        """Test unique constraints"""
        user1 = User(username='unique', email='unique@test.com', fullName='User 1')
        test_db.session.add(user1)
        test_db.session.commit()

        # Thử tạo user với username trùng
        user2 = User(username='unique', email='different@test.com', fullName='User 2')
        test_db.session.add(user2)

        with pytest.raises(Exception):  # Expect database error
            test_db.session.commit()


class TestMemberModel:
    """Test Member model"""

    def test_create_member(self, test_db, sample_user):
        """Test tạo member"""
        member = Member(
            user_id=sample_user.id,
            borrowLimit=10,
            currentBorrowCount=2,
            statusPenalty=StatusPenalty.LEVEL2
        )
        test_db.session.add(member)
        test_db.session.commit()

        assert member.id is not None
        assert member.borrowLimit == 10
        assert member.currentBorrowCount == 2
        assert member.statusPenalty == StatusPenalty.LEVEL2

    def test_member_has_overdue_books(self, test_db, sample_member):
        """Test method has_overdue_books"""
        # Tạo borrow record quá hạn (> 30 ngày)
        overdue_date = date.today() - timedelta(days=35)
        borrow_record = BorrowRecord(
            member_id=sample_member.id,
            borrowDate=overdue_date,
            returnDate=None  # Chưa trả
        )
        test_db.session.add(borrow_record)
        test_db.session.commit()

        assert sample_member.has_overdue_books() is True

    def test_member_get_current_borrow_count(self, test_db, sample_member):
        """Test method get_current_borrow_count"""
        # Tạo 3 borrow records chưa trả
        for i in range(3):
            borrow_record = BorrowRecord(
                member_id=sample_member.id,
                borrowDate=date.today(),
                returnDate=None
            )
            test_db.session.add(borrow_record)
        test_db.session.commit()

        assert sample_member.get_current_borrow_count() == 3


class TestBookModel:
    """Test Book model"""

    def test_create_book(self, test_db):
        """Test tạo book với đầy đủ thông tin"""
        # Tạo các dependencies trước
        publisher = Publisher(name='Test Publisher')
        test_db.session.add(publisher)
        test_db.session.flush()

        author = Author(name='Test Author')
        test_db.session.add(author)
        test_db.session.flush()

        category = BookCategory(categoryName='Test Category')
        test_db.session.add(category)
        test_db.session.flush()

        library = Library(address='Test Library')
        test_db.session.add(library)
        test_db.session.flush()

        book = Book(
            title='Test Book',
            publisher_id=publisher.id,
            publicationYear=2023,
            category_id=category.id,
            author_id=author.id,
            library_id=library.id,
            availableCopies=5,
            pages=200
        )
        test_db.session.add(book)
        test_db.session.commit()

        assert book.id is not None
        assert book.title == 'Test Book'
        assert book.availableCopies == 5
        assert str(book) == 'Test Book'

    def test_book_relationships(self, test_db):
        """Test relationships của Book"""
        # Setup dependencies
        publisher = Publisher(name='Test Publisher')
        author = Author(name='Test Author')
        category = BookCategory(categoryName='Test Category')
        library = Library(address='Test Library')

        test_db.session.add_all([publisher, author, category, library])
        test_db.session.flush()

        book = Book(
            title='Test Book',
            publisher_id=publisher.id,
            author_id=author.id,
            category_id=category.id,
            library_id=library.id,
            publicationYear=2023
        )
        test_db.session.add(book)
        test_db.session.commit()

        # Test relationships
        assert book.publisher.name == 'Test Publisher'
        assert book.author.name == 'Test Author'
        assert book.category.categoryName == 'Test Category'
        assert book.library.address == 'Test Library'


class TestBorrowRequestBatchModel:
    """Test BorrowRequestBatch model"""

    def test_create_batch(self, test_db, sample_member):
        """Test tạo borrow request batch"""
        batch = BorrowRequestBatch(
            member_id=sample_member.id,
            batchCode='BR2024001',
            totalBooks=3,
            batchStatus=StatusRequest.PENDING,
            requestDate=date.today()
        )
        test_db.session.add(batch)
        test_db.session.commit()

        assert batch.id is not None
        assert batch.batchCode == 'BR2024001'
        assert batch.totalBooks == 3
        assert str(batch) == 'Batch BR2024001 - 3 cuốn'


class TestBorrowRequestModel:
    """Test BorrowRequest model"""

    def test_create_borrow_request(self, test_db, sample_member):
        """Test tạo borrow request"""
        # Setup book
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(
            title='Test Book',
            publisher_id=publisher.id,
            library_id=library.id,
            publicationYear=2023
        )
        test_db.session.add(book)
        test_db.session.flush()

        borrow_request = BorrowRequest(
            member_id=sample_member.id,
            book_id=book.id,
            requestDate=date.today(),
            statusRequest=StatusRequest.PENDING
        )
        test_db.session.add(borrow_request)
        test_db.session.commit()

        assert borrow_request.id is not None
        assert borrow_request.statusRequest == StatusRequest.PENDING
        assert borrow_request.member.id == sample_member.id
        assert borrow_request.book.title == 'Test Book'


class TestBorrowRecordModel:
    """Test BorrowRecord model"""

    def test_create_borrow_record(self, test_db, sample_member):
        """Test tạo borrow record"""
        borrow_record = BorrowRecord(
            member_id=sample_member.id,
            borrowDate=date.today(),
            penalty=0.0
        )
        test_db.session.add(borrow_record)
        test_db.session.commit()

        assert borrow_record.id is not None
        assert borrow_record.penalty == 0.0
        assert borrow_record.returnDate is None  # Chưa trả


class TestWaitingListModel:
    """Test WaitingList model"""

    def test_create_waiting_list(self, test_db, sample_member):
        """Test tạo waiting list entry"""
        # Setup book
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(
            title='Popular Book',
            publisher_id=publisher.id,
            library_id=library.id,
            publicationYear=2023,
            availableCopies=0  # Hết sách
        )
        test_db.session.add(book)
        test_db.session.flush()

        waiting_list = WaitingList(
            member_id=sample_member.id,
            book_id=book.id,
            priority=1
        )
        test_db.session.add(waiting_list)
        test_db.session.commit()

        assert waiting_list.id is not None
        assert waiting_list.priority == 1
        assert waiting_list.member.id == sample_member.id
        assert waiting_list.book.title == 'Popular Book'


class TestSupportingModels:
    """Test các supporting models"""

    def test_publisher_model(self, test_db):
        """Test Publisher model"""
        publisher = Publisher(name='Penguin Books')
        test_db.session.add(publisher)
        test_db.session.commit()

        assert publisher.id is not None
        assert str(publisher) == 'Penguin Books'

    def test_author_model(self, test_db):
        """Test Author model"""
        author = Author(name='J.K. Rowling')
        test_db.session.add(author)
        test_db.session.commit()

        assert author.id is not None
        assert str(author) == 'J.K. Rowling'

    def test_book_category_model(self, test_db):
        """Test BookCategory model"""
        category = BookCategory(
            categoryName='Science Fiction',
            description='Books about future and space'
        )
        test_db.session.add(category)
        test_db.session.commit()

        assert category.id is not None
        assert str(category) == 'Science Fiction'

    def test_library_model(self, test_db):
        """Test Library model"""
        library = Library(address='123 Main Street, City')
        test_db.session.add(library)
        test_db.session.commit()

        assert library.id is not None
        assert str(library) == '123 Main Street, City'

    def test_rating_model(self, test_db, sample_member):
        """Test Rating model"""
        # Setup book
        publisher = Publisher(name='Test Publisher')
        library = Library(address='Test Library')
        test_db.session.add_all([publisher, library])
        test_db.session.flush()

        book = Book(
            title='Rated Book',
            publisher_id=publisher.id,
            library_id=library.id,
            publicationYear=2023
        )
        test_db.session.add(book)
        test_db.session.flush()

        rating = Rating(
            member_id=sample_member.id,
            book_id=book.id,
            score=5,
            comment='Excellent book!'
        )
        test_db.session.add(rating)
        test_db.session.commit()

        assert rating.id is not None
        assert rating.score == 5
        assert rating.comment == 'Excellent book!'