from datetime import datetime
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, logout_user
from flask import redirect, flash, url_for, request, render_template
from BBOOK.BB import app, db
from BBOOK.BB.models import (UserRole, ImportRecord, Book, Librarian, Library,
                             BookCategory, Author, Publisher)


class AuthenticatedModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated


class BookView(AuthenticatedModelView):
    column_list = ('id', 'title', 'author_id', 'category_id', 'publisher_id', 'library_id',
                   'availableCopies', 'publicationYear')
    column_labels = {
        'id': 'ID',
        'title': 'Tiêu đề',
        'author_id': 'Tác giả',
        'category_id': 'Danh mục',
        'publisher_id': 'Nhà xuất bản',
        'library_id': 'Thư viện',
        'availableCopies': 'Số lượng có sẵn',
        'publicationYear': 'Năm xuất bản',
        'image': 'Ảnh bìa'
    }

    # Tìm kiếm
    column_searchable_list = ('title',)

    # Lọc
    column_filters = ('author_id', 'category_id', 'publisher_id', 'publicationYear')

    # Form tạo/sửa
    form_columns = ('title', 'author_id', 'category_id', 'publisher_id', 'library_id',
                    'publicationYear', 'availableCopies', 'image')

    column_default_sort = 'title'
    page_size = 20

class BookCategoryView(AuthenticatedModelView):
    column_list = ('id', 'categoryName', 'description')
    column_searchable_list = ('categoryName',)
    form_columns = ('categoryName', 'description')

    column_labels = {
        'id': 'ID',
        'categoryName': 'Tên danh mục',
        'description': 'Mô tả'
    }

    column_default_sort = 'categoryName'


class AuthorView(AuthenticatedModelView):
    column_list = ('id', 'name')
    column_searchable_list = ('name',)
    form_columns = ('name',)

    column_labels = {
        'id': 'ID',
        'name': 'Tên tác giả'
    }

    column_default_sort = 'name'


class PublisherView(AuthenticatedModelView):
    column_list = ('id', 'name')
    column_searchable_list = ('name',)
    form_columns = ('name',)

    column_labels = {
        'id': 'ID',
        'name': 'Tên nhà xuất bản'
    }

    column_default_sort = 'name'

class LibraryView(AuthenticatedModelView):
    column_list = ('id', 'address')
    column_searchable_list = ('address',)
    form_columns = ('address',)

    column_labels = {
        'id': 'ID',
        'address': 'Địa chỉ thư viện'
    }

    column_default_sort = 'address'


class LibrarianView(AuthenticatedModelView):
    column_list = ('id', 'user_id', 'library_id')
    form_columns = ('user_id', 'library_id')

    column_labels = {
        'id': 'ID',
        'user_id': 'Người dùng',
        'library_id': 'Thư viện'
    }


class ImportRecordView(BaseView):
    @expose('/')
    def index(self):
        page = request.args.get('page', 1, type=int)
        per_page = 15

        records = ImportRecord.query.order_by(ImportRecord.importDate.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Dữ liệu cho form thêm mới
        books = Book.query.order_by(Book.title).all()
        librarians = Librarian.query.all()
        libraries = Library.query.order_by(Library.address).all()

        return self.render('admin/import_records.html',
                           records=records,
                           books=books,
                           librarians=librarians,
                           libraries=libraries)

    @expose('/add', methods=['POST'])
    def add_import(self):
        try:
            # Lấy dữ liệu từ form
            book_id = request.form.get('book_id', type=int)
            quantity = request.form.get('quantity', type=int)
            librarian_id = request.form.get('librarian_id', type=int)
            library_id = request.form.get('library_id', type=int)
            import_date = request.form.get('import_date')
            description = request.form.get('description', '').strip()

            if not all([book_id, quantity, librarian_id, library_id]):
                flash("Vui lòng điền đầy đủ thông tin bắt buộc!", "error")
                return redirect(url_for('.index'))

            if quantity <= 0:
                flash("Số lượng phải lớn hơn 0!", "error")
                return redirect(url_for('.index'))

            if import_date:
                try:
                    import_date = datetime.strptime(import_date, "%Y-%m-%d").date()
                except ValueError:
                    flash("Định dạng ngày không hợp lệ!", "error")
                    return redirect(url_for('.index'))
            else:
                import_date = datetime.now().date()

            book = Book.query.get(book_id)
            librarian = Librarian.query.get(librarian_id)
            library = Library.query.get(library_id)

            if not book:
                flash("Sách không tồn tại!", "error")
                return redirect(url_for('.index'))
            if not librarian:
                flash("Thủ thư không tồn tại!", "error")
                return redirect(url_for('.index'))
            if not library:
                flash("Thư viện không tồn tại!", "error")
                return redirect(url_for('.index'))

            # Cập nhật số lượng sách có sẵn
            book.availableCopies += quantity

            # Tạo phiếu nhập mới
            import_record = ImportRecord(
                book_id=book_id,
                bookTitle=book.title,
                quantity=quantity,
                librarian_id=librarian_id,
                library_id=library_id,
                importDate=import_date,
                description=description if description else None
            )

            db.session.add(import_record)
            db.session.commit()

            flash(f'Nhập sách "{book.title}" thành công! Số lượng: {quantity}', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Đã xảy ra lỗi: {str(e)}', 'error')

        return redirect(url_for('.index'))

    @expose('/delete/<int:record_id>')
    def delete_import(self, record_id):
        try:
            record = ImportRecord.query.get_or_404(record_id)
            book = Book.query.get(record.book_id)

            if book and book.availableCopies >= record.quantity:
                book.availableCopies -= record.quantity
                db.session.delete(record)
                db.session.commit()
                flash(f'Đã xóa phiếu nhập sách "{record.bookTitle}"', 'success')
            else:
                flash('Không thể xóa phiếu nhập này vì sẽ làm số lượng sách âm!', 'error')

        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi khi xóa: {str(e)}', 'error')

        return redirect(url_for('.index'))

    def is_accessible(self):
        return current_user.is_authenticated


class LogoutView(BaseView):
    @expose('/')
    def index(self):
        logout_user()
        return redirect(url_for('admin_login'))

    def is_accessible(self):
        return current_user.is_authenticated



class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return redirect(url_for('admin_login'))
        return super(MyAdminIndexView, self).index()

    def is_accessible(self):
        return current_user.is_authenticated and current_user.role in [UserRole.ADMIN, UserRole.LIBRARIAN]



admin = Admin(
    app=app,
    name="Quản lý Thư viện",
    template_mode="bootstrap4",
    index_view=MyAdminIndexView()
)


admin.add_view(BookView(Book, db.session, name="Sách"))
admin.add_view(BookCategoryView(BookCategory, db.session, name="Loại sách"))
admin.add_view(AuthorView(Author, db.session, name="Tác giả"))
admin.add_view(PublisherView(Publisher, db.session, name="Nhà xuất bản"))
admin.add_view(LibraryView(Library, db.session, name="Thư viện"))
admin.add_view(LibrarianView(Librarian, db.session, name="Thủ thư"))
admin.add_view(ImportRecordView(name="Phiếu nhập sách", endpoint="importrecords"))
admin.add_view(LogoutView(name="Đăng xuất"))