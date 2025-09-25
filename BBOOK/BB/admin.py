from datetime import datetime, date
from flask_admin import Admin, AdminIndexView, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, logout_user, login_required
from flask import redirect, flash, url_for, request, render_template, jsonify
from BBOOK.BB import app, db, dao
from BBOOK.BB.dao import get_borrow_stats_summary
from BBOOK.BB.models import (UserRole, ImportRecord, Book, Librarian, Library,
                             BookCategory, Author, Publisher, BorrowRequest, StatusRequest, Member, WaitingList)
from sqlalchemy import func, desc, or_, extract


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


class ImportRecordView(ModelView):
    can_create = False
    can_edit = False
    can_delete = False
    column_list = ['id', 'book', 'quantity', 'importDate', 'librarian', 'library']

    @expose('/', methods=['GET', 'POST'])
    def index(self):
        records = ImportRecord.query.all()
        libraries = Library.query.all()
        librarians = Librarian.query.all()
        authors = Author.query.all()
        categories = BookCategory.query.all()
        publishers = Publisher.query.all()

        if request.method == 'POST':
            book_title = request.form['book_title'].strip()
            quantity = int(request.form['quantity'])
            import_date = request.form.get('import_date') or date.today().isoformat()
            library_id = request.form['library_id']
            librarian_id = request.form['librarian_id']
            description = request.form.get('description', '')

            # Kiểm tra sách đã tồn tại theo ID nếu có
            book_id = request.form.get('book_id', '').strip()
            if book_id:
                # Sách cũ
                book = Book.query.get(int(book_id))
                if not book:
                    flash('Sách cũ không tồn tại!', 'error')
                    return redirect(url_for('.index'))

                # Cập nhật số lượng có sẵn
                book.availableCopies += quantity

            else:
                # Sách mới
                author_id = request.form['author_id']
                category_id = request.form['category_id']
                publisher_id = request.form['publisher_id']

                # Xử lý publicationYear: nếu rỗng thì dùng None
                publication_year = request.form.get('publication_year', '').strip()
                if publication_year == '':
                    publication_year = None
                else:
                    try:
                        publication_year = int(publication_year)
                    except ValueError:
                        flash('Năm xuất bản không hợp lệ!', 'error')
                        return redirect(url_for('.index'))

                book = Book(
                    title=book_title,
                    author_id=author_id,
                    category_id=category_id,
                    publisher_id=publisher_id,
                    library_id=library_id,
                    publicationYear=publication_year,
                    availableCopies=quantity,
                    description=description
                )
                db.session.add(book)
                db.session.flush()  # để lấy id book mới

            # Tạo phiếu nhập
            import_record = ImportRecord(
                book_id=book.id,
                bookTitle=book.title,
                quantity=quantity,
                importDate=import_date,
                library_id=library_id,
                librarian_id=librarian_id,
                description=description
            )
            db.session.add(import_record)
            db.session.commit()
            flash('Tạo phiếu nhập thành công!', 'success')
            return redirect(url_for('.index'))

        return self.render(
            'admin/import_records.html',
            records=records,
            libraries=libraries,
            librarians=librarians,
            authors=authors,
            categories=categories,
            publishers=publishers,
            date=date.today().isoformat()
        )

    @expose('/delete/<int:record_id>', methods=['POST'])
    def delete_import(self, record_id):
        record = ImportRecord.query.get_or_404(record_id)
        book = record.book

        # Cập nhật lại số lượng
        if book and book.availableCopies >= record.quantity:
            book.availableCopies -= record.quantity
        if book and book.availableCopies == 0:
            db.session.delete(book)

        db.session.delete(record)
        db.session.commit()
        flash('Xóa phiếu thành công!', 'success')
        return redirect(url_for('.index'))



# Thêm các DAO functions hỗ trợ
def search_books_by_query(query, limit=10):
    """Tìm kiếm sách theo mã ID hoặc tên"""
    books_query = Book.query.join(Author, isouter=True).join(BookCategory, isouter=True)

    if query.isdigit():
        # Tìm theo ID
        books_query = books_query.filter(Book.id == int(query))
    else:
        # Tìm theo tên sách hoặc tác giả
        books_query = books_query.filter(
            or_(
                Book.title.ilike(f'%{query}%'),
                Author.name.ilike(f'%{query}%')
            )
        )

    return books_query.limit(limit).all()


def create_book_with_import(book_data, import_data):
    """Tạo sách mới kèm phiếu nhập"""
    try:
        # Tạo sách mới
        book = Book(
            title=book_data['title'],
            author_id=book_data['author_id'],
            category_id=book_data['category_id'],
            publisher_id=book_data['publisher_id'],
            library_id=book_data['library_id'],
            publicationYear=book_data['publication_year'],
            availableCopies=import_data['quantity'],
            description=book_data.get('description')
        )

        db.session.add(book)
        db.session.flush()  # Để lấy book.id

        # Tạo phiếu nhập
        import_record = ImportRecord(
            book_id=book.id,
            bookTitle=book.title,
            quantity=import_data['quantity'],
            librarian_id=import_data['librarian_id'],
            library_id=import_data['library_id'],
            importDate=import_data['import_date'],
            description=import_data.get('description')
        )

        db.session.add(import_record)
        db.session.commit()

        return {'success': True, 'book': book, 'record': import_record}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def update_book_quantity_with_import(book_id, import_data):
    """Cập nhật số lượng sách có sẵn và tạo phiếu nhập"""
    try:
        book = Book.query.get(book_id)
        if not book:
            return {'success': False, 'error': 'Sách không tồn tại'}

        # Cập nhật số lượng
        book.availableCopies += import_data['quantity']

        # Tạo phiếu nhập
        import_record = ImportRecord(
            book_id=book.id,
            bookTitle=book.title,
            quantity=import_data['quantity'],
            librarian_id=import_data['librarian_id'],
            library_id=import_data['library_id'],
            importDate=import_data['import_date'],
            description=import_data.get('description')
        )

        db.session.add(import_record)
        db.session.commit()

        return {'success': True, 'book': book, 'record': import_record}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


class LogoutView(BaseView):
    @expose('/')
    def index(self):
        logout_user()
        return redirect(url_for('admin_login'))

    def is_accessible(self):
        return current_user.is_authenticated



class BorrowRequestView(AuthenticatedModelView):
    column_list = ('id', 'member_id', 'book_id', 'requestDate', 'statusRequest')
    column_labels = {
        'id': 'ID',
        'member_id': 'Thành viên ID',
        'book_id': 'Sách ID',
        'requestDate': 'Ngày yêu cầu',
        'statusRequest': 'Trạng thái'
    }

    column_filters = ('statusRequest', 'requestDate')


    form_columns = ('statusRequest',)  # Chỉ cho phép sửa trạng thái

    column_default_sort = [('requestDate', True)]  # Sắp xếp theo ngày mới nhất
    page_size = 20

    def is_accessible(self):
        return (current_user.is_authenticated and
                current_user.role in [UserRole.ADMIN, UserRole.LIBRARIAN])


class MemberView(AuthenticatedModelView):
    column_list = ('id', 'user_id', 'borrowLimit', 'currentBorrowCount', 'statusPenalty')
    column_labels = {
        'id': 'ID',
        'user_id': 'Người dùng ID',
        'borrowLimit': 'Giới hạn mượn',
        'currentBorrowCount': 'Đang mượn',
        'statusPenalty': 'Mức phạt'
    }


    form_columns = ('user_id', 'borrowLimit', 'currentBorrowCount', 'statusPenalty')

    def is_accessible(self):
        return (current_user.is_authenticated and
                current_user.role in [UserRole.ADMIN, UserRole.LIBRARIAN])


class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return redirect(url_for('admin_login'))

        # Get statistics
        stats = {
            'pending_requests': BorrowRequest.query.filter_by(statusRequest=StatusRequest.PENDING).count(),
            'approved_requests': BorrowRequest.query.filter_by(statusRequest=StatusRequest.APPROVED).count(),
            'total_books': Book.query.count(),
            'total_members': Member.query.count()
        }

        # Get recent requests (last 10)
        recent_requests = BorrowRequest.query.order_by(desc(BorrowRequest.requestDate)).limit(10).all()

        # Get popular books (most borrowed)
        popular_books = db.session.query(
            Book,
            func.count(BorrowRequest.id).label('borrow_count')
        ).join(BorrowRequest).group_by(Book.id).order_by(desc('borrow_count')).limit(5).all()

        # Get active members
        active_members = Member.query.filter(Member.currentBorrowCount > 0).order_by(desc(Member.currentBorrowCount)).limit(5).all()

        return self.render('admin/index.html',
                         stats=stats,
                         recent_requests=recent_requests,
                         popular_books=popular_books,
                         active_members=active_members)

    def is_accessible(self):
        return current_user.is_authenticated and current_user.role in [UserRole.ADMIN, UserRole.LIBRARIAN]



admin = Admin(
    app=app,
    name="Quản lý Thư viện",
    template_mode="bootstrap4",
    index_view=MyAdminIndexView()
)


@app.route('/admin/waiting-list')
@login_required
def admin_waiting_list():
    """Quản lý danh sách chờ"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return redirect('/')

    waiting_list = WaitingList.query.join(WaitingList.book, WaitingList.member) \
        .order_by(WaitingList.book_id, WaitingList.priority) \
        .all()

    return render_template('admin/waiting_list.html', waiting_list=waiting_list)


@app.route('/admin/process-return/<int:book_id>')
@login_required
def process_book_return(book_id):
    """Xử lý trả sách và thông báo người chờ"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'})

    try:
        # Cập nhật số lượng sách
        book = Book.query.get(book_id)
        book.availableCopies += 1

        # Thông báo người đầu tiên trong danh sách chờ
        next_waiter = WaitingList.query.filter_by(book_id=book_id) \
            .order_by(WaitingList.priority.asc()).first()

        if next_waiter:
            # TODO: Gửi email/thông báo cho member
            # Xóa khỏi danh sách chờ hoặc chuyển thành yêu cầu mượn
            db.session.delete(next_waiter)

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/admin/borrow-management')
@login_required
def borrow_management_dashboard():
    """B1-B2: Dashboard quản lý mượn trả"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return redirect('/')

    # Lấy thống kê
    stats = dao.get_borrow_statistics()

    return render_template('admin/borrow_dashboard.html', stats=stats)


@app.route('/admin/pending-requests')
@login_required
def pending_requests():
    """B3-B4: Danh sách yêu cầu chờ duyệt"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return redirect('/')

    requests = dao.get_pending_requests_with_details()

    return render_template('admin/pending_requests.html', requests=requests)


@app.route('/admin/request-detail/<int:request_id>')
@login_required
def request_detail(request_id):
    """Xem chi tiết yêu cầu và kiểm tra vi phạm"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'})

    request_obj = BorrowRequest.query.get_or_404(request_id)

    # Kiểm tra vi phạm của member
    violations = dao.check_member_violations(request_obj.member_id)

    return render_template('admin/request_detail.html',
                           request=request_obj,
                           violations=violations)


@app.route('/admin/process-request', methods=['POST'])
@login_required
def process_request():
    """B5-B7: Xử lý duyệt yêu cầu"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'})

    try:
        data = request.json
        request_id = data.get('request_id')
        action = data.get('action')  # 'approve', 'conditional', 'reject'
        reason = data.get('reason', '')
        conditions = data.get('conditions', '')
        new_return_date = data.get('new_return_date')

        result = dao.approve_borrow_request(
            request_id=request_id,
            approval_type=action,
            processor_id=current_user.id,
            reason=reason,
            conditions=conditions,
            new_return_date=new_return_date
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'})


@app.route('/admin/bulk-process', methods=['POST'])
@login_required
def bulk_process_requests():
    """Duyệt hàng loạt yêu cầu"""
    if current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
        return jsonify({'success': False, 'message': 'Không có quyền'})

    try:
        data = request.json
        request_ids = data.get('request_ids', [])
        action = data.get('action')

        results = []
        for req_id in request_ids:
            result = dao.approve_borrow_request(
                request_id=req_id,
                approval_type=action,
                processor_id=current_user.id
            )
            results.append({'request_id': req_id, 'result': result})

        success_count = sum(1 for r in results if r['result']['success'])

        return jsonify({
            'success': True,
            'message': f'Đã xử lý {success_count}/{len(request_ids)} yêu cầu',
            'details': results
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'})



# VIEWS QUẢN LÝ MƯỢN TRẢ
class BorrowManagementView(BaseView):
    """Dashboard quản lý mượn trả"""

    @expose('/')
    def index(self):
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return redirect(url_for('admin_login'))

        # Lấy thống kê
        stats = dao.get_borrow_management_stats()

        # Lấy một số yêu cầu gần đây
        recent_requests = dao.get_pending_requests(page=1, per_page=5)

        return self.render('admin/borrow_management_dashboard.html',
                           stats=stats,
                           recent_requests=recent_requests['batches'])


class PendingRequestsView(BaseView):
    """Xem danh sách yêu cầu chờ duyệt"""

    @expose('/')
    def index(self):
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return redirect(url_for('admin_login'))

        page = request.args.get('page', 1, type=int)
        per_page = 10

        # Lấy filters từ URL
        filters = {}
        if request.args.get('member_name'):
            filters['member_name'] = request.args.get('member_name')
        if request.args.get('date_from'):
            filters['date_from'] = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d').date()
        if request.args.get('date_to'):
            filters['date_to'] = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d').date()

        # Lấy data
        result = dao.get_pending_requests(page=page, per_page=per_page, filters=filters)

        return self.render('admin/pending_requests.html', **result, filters=request.args)


class RequestDetailView(BaseView):
    """Chi tiết yêu cầu mượn và duyệt"""

    @expose('/')
    def index(self):
        """Default view - redirect to pending requests"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return redirect(url_for('admin_login'))

        return redirect(url_for('pendingrequests.index'))

    @expose('/<int:batch_id>')
    def detail(self, batch_id):
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return redirect(url_for('admin_login'))

        # Lấy thông tin batch
        batch_info = dao.get_batch_with_details(batch_id)
        if not batch_info:
            flash('Không tìm thấy yêu cầu mượn!', 'error')
            return redirect(url_for('pendingrequests.index'))

        # Kiểm tra vi phạm của member
        violations = dao.check_member_violations(batch_info['batch'].member_id)

        return self.render('admin/request_detail.html',
                           batch_info=batch_info,
                           violations=violations)

    @expose('/process', methods=['POST'])
    def process_request(self):
        """Xử lý duyệt/từ chối yêu cầu"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return jsonify({'success': False, 'message': 'Không có quyền truy cập'})

        try:
            data = request.get_json()
            batch_id = data.get('batch_id')
            approval_type = data.get('approval_type')  # 'approve', 'conditional', 'reject'

            kwargs = {}
            if approval_type == 'conditional':
                kwargs['conditions'] = data.get('conditions', '')
                if data.get('custom_return_date'):
                    kwargs['custom_return_date'] = datetime.strptime(
                        data['custom_return_date'], '%Y-%m-%d'
                    ).date()
            elif approval_type == 'reject':
                kwargs['rejection_reason'] = data.get('rejection_reason', '')

            kwargs['notes'] = data.get('notes', '')

            # Xử lý
            result = dao.approve_batch_with_conditions(
                batch_id=batch_id,
                approval_type=approval_type,
                processor_id=current_user.id,
                **kwargs
            )

            return jsonify(result)

        except Exception as e:
            return jsonify({'success': False, 'message': f'Lỗi: {str(e)}'})

# API ENDPOINTS
class BorrowManagementAPI(BaseView):
    """API endpoints cho quản lý mượn trả"""

    @expose('/')
    def index(self):
        """Default API index"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 401

        return jsonify({
            'message': 'Borrow Management API',
            'endpoints': [
                '/member-status/<member_id>',
                '/stats'
            ]
        })

    @expose('/member-status/<int:member_id>')
    def check_member_status(self, member_id):
        """API kiểm tra trạng thái member"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 401

        violations = dao.check_member_violations(member_id)
        return jsonify(violations)

    @expose('/stats')
    def get_stats(self):
        """API lấy thống kê dashboard"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.LIBRARIAN, UserRole.ADMIN]:
            return jsonify({'error': 'Unauthorized'}), 401

        stats = dao.get_borrow_management_stats()
        return jsonify(stats)


class BorrowStatisticsView(BaseView):
    """View báo cáo thống kê mượn sách"""

    @expose('/')
    def index(self):
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return redirect(url_for('admin_login'))

        # Lấy danh sách năm có dữ liệu
        years = dao.get_available_statistics_years()

        # Lấy tổng quan thống kê
        summary_stats = dao.get_borrow_stats_summary()

        return self.render(
            'admin/borrow_statistics.html',
            years=years,
            current_year=datetime.now().year,
            current_month=datetime.now().month,
            summary_stats=summary_stats
        )

    @expose('/api/monthly-stats')
    def monthly_stats_api(self):
        """API lấy thống kê theo tháng"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            year = request.args.get('year', datetime.now().year, type=int)
            month = request.args.get('month', datetime.now().month, type=int)

            # Sử dụng function từ dao.py
            stats = dao.get_monthly_borrow_statistics(year, month)

            if not stats['success']:
                return jsonify({'error': stats.get('error', 'Unknown error')}), 500

            # Chuẩn bị dữ liệu cho Chart.js
            data = {
                'labels': [f"{item['title']} ({item['author']})" for item in stats['data']],
                'data': [item['borrow_count'] for item in stats['data']],
                'total_requests': stats['total_borrows']
            }

            return jsonify(data)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @expose('/api/yearly-overview')
    def yearly_overview_api(self):
        """API lấy tổng quan theo năm"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            year = request.args.get('year', datetime.now().year, type=int)

            # Sử dụng function từ dao.py
            overview = dao.get_yearly_borrow_overview(year)

            if not overview['success']:
                return jsonify({'error': overview.get('error', 'Unknown error')}), 500

            data = {
                'labels': ['T1', 'T2', 'T3', 'T4', 'T5', 'T6',
                           'T7', 'T8', 'T9', 'T10', 'T11', 'T12'],
                'data': overview['data'],
                'year': year
            }

            return jsonify(data)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @expose('/export-csv')
    def export_csv(self):
        """Xuất dữ liệu thống kê ra file CSV"""
        if not current_user.is_authenticated or current_user.role not in [UserRole.ADMIN, UserRole.LIBRARIAN]:
            return redirect(url_for('admin_login'))

        try:
            year = request.args.get('year', type=int)
            month = request.args.get('month', type=int)

            # Xuất CSV
            csv_file_path = dao.export_borrow_statistics_to_csv(year, month)

            if csv_file_path:
                from flask import send_file
                import os

                # Tạo tên file với thời gian
                filename_suffix = ""
                if year and month:
                    filename_suffix = f"_{year}_{month:02d}"
                elif year:
                    filename_suffix = f"_{year}"

                filename = f"borrow_statistics{filename_suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

                response = send_file(
                    csv_file_path,
                    as_attachment=True,
                    download_name=filename,
                    mimetype='text/csv'
                )

                # Xóa file tạm sau khi gửi
                @response.call_on_close
                def remove_temp_file():
                    try:
                        os.unlink(csv_file_path)
                    except:
                        pass

                return response
            else:
                flash('Lỗi khi xuất dữ liệu!', 'error')
                return redirect(url_for('borrowstatistics.index'))

        except Exception as e:
            flash(f'Lỗi xuất CSV: {str(e)}', 'error')
            return redirect(url_for('borrowstatistics.index'))

admin.add_view(BookView(Book, db.session, name="Sách"))
admin.add_view(BookCategoryView(BookCategory, db.session, name="Loại sách"))
admin.add_view(AuthorView(Author, db.session, name="Tác giả"))
admin.add_view(PublisherView(Publisher, db.session, name="Nhà xuất bản"))
admin.add_view(LibraryView(Library, db.session, name="Thư viện"))
admin.add_view(LibrarianView(Librarian, db.session, name="Thủ thư"))
admin.add_view(MemberView(Member, db.session, name="Thành viên"))
admin.add_view(BorrowManagementView(name='Dashboard', endpoint='borrowmanagement', category='Quản lý mượn trả'))
admin.add_view(PendingRequestsView(name='Yêu cầu chờ duyệt', endpoint='pendingrequests', category='Quản lý mượn trả'))
admin.add_view(RequestDetailView(name='Chi tiết yêu cầu', endpoint='requestdetail', category='Quản lý mượn trả'))
admin.add_view(ImportRecordView(ImportRecord, db.session, name="Phiếu nhập sách", endpoint="importrecords"))
admin.add_view(BorrowStatisticsView(name='Báo cáo thống kê',endpoint='borrowstatistics', category='Báo cáo'))
admin.add_view(LogoutView(name="Đăng xuất"))