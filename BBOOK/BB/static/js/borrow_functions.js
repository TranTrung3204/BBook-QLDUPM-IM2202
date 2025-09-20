// Utility functions cho chức năng mượn sách

function checkMemberStatus() {
    /**
     * Kiểm tra trạng thái member trước khi cho phép mượn
     */
    return $.get('/api/member-status')
        .then(function(data) {
            return data;
        })
        .catch(function() {
            return {eligible: false, message: 'Không thể kiểm tra trạng thái'};
        });
}

function addToWaitingList(bookId) {
    /**
     * Thêm sách vào danh sách chờ
     */
    return $.post('/api/add-to-waiting-list', {
        book_id: bookId
    }).then(function(data) {
        if (data.success) {
            showNotification('success',
                `Đã thêm vào danh sách chờ. Vị trí: ${data.position}`);
        } else {
            showNotification('error', data.message);
        }
        return data;
    });
}

function showNotification(type, message) {
    /**
     * Hiển thị thông báo Toast
     */
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const notification = `
        <div class="alert ${alertClass} alert-dismissible fade show notification-toast"
             style="position: fixed; top: 20px; right: 20px; z-index: 9999;">
            <button type="button" class="close" data-dismiss="alert">&times;</button>
            ${message}
        </div>
    `;

    $('body').append(notification);

    // Tự động ẩn sau 5 giây
    setTimeout(function() {
        $('.notification-toast').fadeOut();
    }, 5000);
}

function validateBorrowForm(formData) {
    /**
     * Validate form đăng ký mượn sách
     */
    const errors = [];

    if (!formData.expected_return_date) {
        errors.push('Vui lòng chọn ngày trả dự kiến');
    } else {
        const returnDate = new Date(formData.expected_return_date);
        const today = new Date();

        if (returnDate <= today) {
            errors.push('Ngày trả phải sau hôm nay');
        }

        // Kiểm tra không được quá 30 ngày
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 30);

        if (returnDate > maxDate) {
            errors.push('Ngày trả không được quá 30 ngày kể từ hôm nay');
        }
    }

    return {
        isValid: errors.length === 0,
        errors: errors
    };
}