import pytest
import os
import tempfile
from BBOOK.BB import app, db
from BBOOK.BB.models import *
from datetime import date


@pytest.fixture(scope='function')
def test_app():
    """Tạo Flask app cho test với database in-memory"""
    # Tạo database tạm thời
    db_fd, db_path = tempfile.mkstemp()

    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False  # Tắt CSRF cho test
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def test_client(test_app):
    """Tạo test client"""
    return test_app.test_client()


@pytest.fixture(scope='function')
def test_db(test_app):
    """Fixture database cho test"""
    with test_app.app_context():
        yield db


@pytest.fixture(scope='function')
def sample_user(test_db):
    """Tạo user mẫu cho test"""
    user = User(
        username='testuser',
        password='5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',  # 'password' hashed
        email='test@example.com',
        fullName='Test User',
        phone='0123456789',
        role=UserRole.MEMBER
    )
    test_db.session.add(user)
    test_db.session.commit()
    return user


@pytest.fixture(scope='function')
def sample_member(test_db, sample_user):
    """Tạo member mẫu cho test"""
    member = Member(
        user_id=sample_user.id,
        borrowLimit=5,
        currentBorrowCount=0,
        statusPenalty=StatusPenalty.LEVEL1
    )
    test_db.session.add(member)
    test_db.session.commit()
    return member