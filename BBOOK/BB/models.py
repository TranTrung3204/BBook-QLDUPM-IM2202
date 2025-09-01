from sqlalchemy import Column, Integer, String, ForeignKey, Date, Boolean, Text, Enum, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as UserEnum
from flask_login import UserMixin
from BBOOK.BB import db, app


class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)


class StatusRequest(UserEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class StatusPenalty(UserEnum):
    LEVEL1 = 1
    LEVEL2 = 2
    LEVEL3 = 3
    LEVEL4 = 4
    LEVEL5 = 5


class UserRole(UserEnum):
    MEMBER = 1
    LIBRARIAN = 2
    ADMIN = 3

class Publisher(BaseModel):
    name = Column(String(255), nullable=False)
    books = relationship("Book", backref="publisher", lazy=True)

    def __str__(self):
        return self.name


class Author(BaseModel):
    name = Column(String(255), nullable=False)
    books = relationship("Book", backref="author", lazy=True)

    def __str__(self):
        return self.name


class BookCategory(BaseModel):
    categoryName = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    books = relationship("Book", backref="category", lazy=True)

    def __str__(self):
        return self.categoryName


class Library(BaseModel):
    address = Column(String(255), nullable=False)
    librarians = relationship("Librarian", backref="library", lazy=True)
    books = relationship("Book", backref="library", lazy=True)
    import_records = relationship("ImportRecord", backref="library", lazy=True)

    def __str__(self):
        return self.address


class User(BaseModel, UserMixin):
    username = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20))
    address = Column(String(255))
    dob = Column(Date)
    avatar = Column(String(50))
    registrationDate = Column(Date, default=datetime.now)
    fullName = Column(String(255), nullable=False)
    isActive = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.MEMBER)

    member = relationship("Member", backref="user", uselist=False)
    librarian = relationship("Librarian", backref="user", uselist=False)

    def __str__(self):
        return self.username


class Member(BaseModel):
    user_id = Column(Integer, ForeignKey(User.id), unique=True, nullable=False)
    borrowLimit = Column(Integer, nullable=False)
    currentBorrowCount = Column(Integer, default=0)
    statusPenalty = Column(Enum(StatusPenalty), default=StatusPenalty.LEVEL1)

    borrow_requests = relationship("BorrowRequest", backref="member", lazy=True)
    borrow_records = relationship("BorrowRecord", backref="member", lazy=True)
    ratings = relationship("Rating", backref="member", lazy=True)


class Librarian(BaseModel):
    user_id = Column(Integer, ForeignKey(User.id), unique=True, nullable=False)
    library_id = Column(Integer, ForeignKey(Library.id), nullable=False)

    import_records = relationship("ImportRecord", backref="librarian", lazy=True)


class Book(BaseModel):
    title = Column(String(255), nullable=False)
    image = Column(String(255))
    publisher_id = Column(Integer, ForeignKey(Publisher.id), nullable=False)
    publicationYear = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey(BookCategory.id))
    author_id = Column(Integer, ForeignKey(Author.id))
    library_id = Column(Integer, ForeignKey(Library.id), nullable=False)
    availableCopies = Column(Integer, default=1)

    ratings = relationship("Rating", backref="book", lazy=True)
    borrow_requests = relationship("BorrowRequest", backref="book", lazy=True)
    borrow_details = relationship("BorrowDetail", backref="book", lazy=True)
    import_records = relationship("ImportRecord", backref="book", lazy=True)

    def __str__(self):
        return self.title


class Rating(BaseModel):
    member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    book_id = Column(Integer, ForeignKey(Book.id), nullable=False)
    score = Column(Integer, nullable=False)
    comment = Column(Text)


class BorrowRequest(BaseModel):
    __tablename__ = "borrow_request"

    member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    book_id = Column(Integer, ForeignKey(Book.id), nullable=False)
    requestDate = Column(Date, default=datetime.now)
    statusRequest = Column(Enum(StatusRequest), default=StatusRequest.PENDING)


class BorrowRecord(BaseModel):
    member_id = Column(Integer, ForeignKey(Member.id), nullable=False)
    penalty = Column(DECIMAL(10, 2), default=0)
    borrowDate = Column(Date, default=datetime.now)
    returnDate = Column(Date)

    books = relationship("BorrowDetail", backref="record", lazy=True)


class BorrowDetail(BaseModel):
    book_id = Column(Integer, ForeignKey(Book.id), nullable=False)
    record_id = Column(Integer, ForeignKey(BorrowRecord.id), nullable=False)
    description = Column(Text)


class ImportRecord(BaseModel):
    book_id = Column(Integer, ForeignKey(Book.id), nullable=False)
    bookTitle = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    library_id = Column(Integer, ForeignKey(Library.id), nullable=False)
    librarian_id = Column(Integer, ForeignKey(Librarian.id), nullable=False)
    importDate = Column(Date, default=datetime.now)
    description = Column(Text)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        db.session.commit()
