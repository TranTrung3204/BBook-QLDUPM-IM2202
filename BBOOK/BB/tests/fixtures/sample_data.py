# tests/fixtures/sample_data.py
from datetime import date, timedelta
from BBOOK.BB.models import *
from BBOOK.BB import db


class TestDataFactory:
    """Factory class để tạo test data"""

    @staticmethod
    def create_publisher(name="Test Publisher"):
        """Tạo publisher test"""
        publisher = Publisher(name=name)
        db.session.add(publisher)
        db.session.flush()
        return publisher

    @staticmethod
    def create_author(name="Test Author"):
        """Tạo author test"""
        author = Author(name=name)
        db.session.add(author)
        db.session.flush()
        return author

    @staticmethod
    def create_category(name="Test Category", description="Test category description"):
        """Tạo book category test"""
        category = BookCategory(categoryName=name, description=description)
        db.session.add(category)
        db.session.flush()
        return category

    @staticmethod
    def create_library(address="123 Test Street"):
        """Tạo library test"""
        library = Library(address=address)
        db.session.add(library)
        db.session.flush()
        return library

    @staticmethod
    def create_user(username="testuser", fullname="Test User", email="test@example.com",
                    password="password", role=UserRole.MEMBER):
        """Tạo user test"""
        import hashlib
        hashed_password = str(hashlib.md5(password.encode('utf-8')).hexdigest())

        user = User(
            username=username,
            fullName=fullname,
            email=email,
            password=hashed_password,
            role=role,
            phone="0123456789",
            registrationDate=date.today()
        )
        db.session.add(user)
        db.session.flush()
        return user

    @staticmethod
    def create_member(user_id, borrow_limit=5, current_count=0, penalty=StatusPenalty.LEVEL1):
        """Tạo member test"""
        member = Member(
            user_id=user_id,
            borrowLimit=borrow_limit,
            currentBorrowCount=current_count,
            statusPenalty=penalty
        )
        db.session.add(member)
        db.session.flush()
        return member

    @staticmethod
    def create_book(title="Test Book", publisher_id=None, library_id=None,
                    author_id=None, category_id=None, available_copies=5, year=2023):
        """Tạo book test"""
        book = Book(
            title=title,
            publisher_id=publisher_id,
            library_id=library_id,
            author_id=author_id,
            category_id=category_id,
            availableCopies=available_copies,
            publicationYear=year,
            pages=200,
            description="Test book description"
        )
        db.session.add(book)
        db.session.flush()
        return book

    @staticmethod
    def create_borrow_request(member_id, book_id, status=StatusRequest.PENDING,
                              batch_id=None, request_date=None):
        """Tạo borrow request test"""
        if request_date is None:
            request_date = date.today()

        request = BorrowRequest(
            member_id=member_id,
            book_id=book_id,
            batch_id=batch_id,
            statusRequest=status,
            requestDate=request_date
        )
        db.session.add(request)
        db.session.flush()
        return request

    @staticmethod
    def create_borrow_batch(member_id, batch_code=None, total_books=1,
                            status=StatusRequest.PENDING):
        """Tạo borrow batch test"""
        if batch_code is None:
            import random
            batch_code = f"BR2024{random.randint(100, 999)}"

        batch = BorrowRequestBatch(
            member_id=member_id,
            batchCode=batch_code,
            totalBooks=total_books,
            batchStatus=status,
            requestDate=date.today()
        )
        db.session.add(batch)
        db.session.flush()
        return batch

    @staticmethod
    def create_borrow_record(member_id, borrow_date=None, return_date=None):
        """Tạo borrow record test"""
        if borrow_date is None:
            borrow_date = date.today()

        record = BorrowRecord(
            member_id=member_id,
            borrowDate=borrow_date,
            returnDate=return_date,
            penalty=0.0
        )
        db.session.add(record)
        db.session.flush()
        return record

    @staticmethod
    def create_complete_book_setup():
        """Tạo setup đầy đủ cho book (publisher, author, category, library)"""
        publisher = TestDataFactory.create_publisher()
        author = TestDataFactory.create_author()
        category = TestDataFactory.create_category()
        library = TestDataFactory.create_library()

        return {
            'publisher': publisher,
            'author': author,
            'category': category,
            'library': library
        }

    @staticmethod
    def create_complete_member_setup(username="testmember"):
        """Tạo setup đầy đủ cho member (user + member)"""
        user = TestDataFactory.create_user(username=username,
                                           email=f"{username}@example.com")
        member = TestDataFactory.create_member(user.id)

        return {
            'user': user,
            'member': member
        }


# tests/fixtures/__init__.py
from .sample_data import TestDataFactory

__all__ = ['TestDataFactory']

# Thêm vào tests/conftest.py
import pytest
from tests.fixtures import TestDataFactory


@pytest.fixture(scope='function')
def data_factory(test_db):
    """Fixture cung cấp TestDataFactory"""
    return TestDataFactory


@pytest.fixture(scope='function')
def complete_book_setup(test_db, data_factory):
    """Fixture tạo complete book setup"""
    setup = data_factory.create_complete_book_setup()
    test_db.session.commit()
    return setup


@pytest.fixture(scope='function')
def complete_member_setup(test_db, data_factory):
    """Fixture tạo complete member setup"""
    setup = data_factory.create_complete_member_setup()
    test_db.session.commit()
    return setup


@pytest.fixture(scope='function')
def sample_books(test_db, complete_book_setup):
    """Fixture tạo nhiều sample books"""
    setup = complete_book_setup

    books = [
        data_factory.create_book("Python Programming",
                                 publisher_id=setup['publisher'].id,
                                 library_id=setup['library'].id,
                                 author_id=setup['author'].id,
                                 category_id=setup['category'].id),
        data_factory.create_book("Java Basics",
                                 publisher_id=setup['publisher'].id,
                                 library_id=setup['library'].id,
                                 author_id=setup['author'].id,
                                 category_id=setup['category'].id),
        data_factory.create_book("Data Science with R",
                                 publisher_id=setup['publisher'].id,
                                 library_id=setup['library'].id,
                                 author_id=setup['author'].id,
                                 category_id=setup['category'].id)
    ]
    test_db.session.commit()
    return books


@pytest.fixture(scope='function')
def multiple_members(test_db, data_factory):
    """Fixture tạo nhiều members"""
    members_data = []

    for i in range(3):
        setup = data_factory.create_complete_member_setup(f"member{i + 1}")
        members_data.append(setup)

    test_db.session.commit()
    return members_data


# Advanced fixtures cho complex test scenarios
@pytest.fixture(scope='function')
def overdue_scenario(test_db, complete_member_setup, data_factory):
    """Fixture tạo scenario có sách quá hạn"""
    member_setup = complete_member_setup
    member = member_setup['member']

    # Tạo borrow record quá hạn (35 ngày trước)
    overdue_date = date.today() - timedelta(days=35)
    overdue_record = data_factory.create_borrow_record(
        member_id=member.id,
        borrow_date=overdue_date,
        return_date=None  # Chưa trả
    )

    test_db.session.commit()

    return {
        'member': member,
        'user': member_setup['user'],
        'overdue_record': overdue_record
    }


@pytest.fixture(scope='function')
def penalty_scenario(test_db, complete_member_setup):
    """Fixture tạo scenario member bị phạt"""
    member_setup = complete_member_setup
    member = member_setup['member']

    # Set penalty level cao
    member.statusPenalty = StatusPenalty.LEVEL4
    test_db.session.commit()

    return {
        'member': member,
        'user': member_setup['user']
    }


@pytest.fixture(scope='function')
def full_batch_scenario(test_db, complete_member_setup, complete_book_setup, data_factory):
    """Fixture tạo scenario batch request hoàn chỉnh"""
    member_setup = complete_member_setup
    book_setup = complete_book_setup

    member = member_setup['member']

    # Tạo nhiều books
    books = []
    for i in range(3):
        book = data_factory.create_book(
            title=f"Book {i + 1}",
            publisher_id=book_setup['publisher'].id,
            library_id=book_setup['library'].id,
            author_id=book_setup['author'].id,
            category_id=book_setup['category'].id
        )
        books.append(book)

    # Tạo batch
    batch = data_factory.create_borrow_batch(
        member_id=member.id,
        batch_code="BR2024TEST",
        total_books=3
    )

    # Tạo requests trong batch
    requests = []
    for book in books:
        request = data_factory.create_borrow_request(
            member_id=member.id,
            book_id=book.id,
            batch_id=batch.id
        )
        requests.append(request)

    test_db.session.commit()

    return {
        'member': member,
        'user': member_setup['user'],
        'books': books,
        'batch': batch,
        'requests': requests
    }