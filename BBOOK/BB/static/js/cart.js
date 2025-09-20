//document.addEventListener('DOMContentLoaded', function() {
//    initializeCartButtons();
//
//    function initializeCartButtons() {
//        // Thêm vào giỏ
//        const addToCartButtons = document.querySelectorAll('.add-to-cart');
//        addToCartButtons.forEach(button => {
//            button.addEventListener('click', function(e) {
//                e.preventDefault();
//                addToCart(this.dataset.id, this.dataset.title);
//            });
//        });
//
//        // Giảm số lượng
//        const minusButtons = document.querySelectorAll('.btn-minus');
//        minusButtons.forEach(button => {
//            button.addEventListener('click', function() {
//                const row = this.closest('tr');
//                const bookId = row.dataset.id;
//                updateQuantity(bookId, -1);
//            });
//        });
//
//        // Tăng số lượng
//        const plusButtons = document.querySelectorAll('.btn-plus');
//        plusButtons.forEach(button => {
//            button.addEventListener('click', function() {
//                const row = this.closest('tr');
//                const bookId = row.dataset.id;
//                updateQuantity(bookId, 1);
//            });
//        });
//
//        // Xóa sách
//        const deleteButtons = document.querySelectorAll('.fa-trash');
//        deleteButtons.forEach(button => {
//            button.closest('button').addEventListener('click', function() {
//                const row = this.closest('tr');
//                const bookId = row.dataset.id;
//                deleteFromCart(bookId);
//            });
//        });
//    }
//});

// ===== DEFINE GLOBAL FUNCTIONS FIRST =====
function addToCart(id, title, stock, author) {
    console.log('addToCart called:', id, title, stock, author);

    fetch('/api/add-cart', {
        method: 'POST',
        body: JSON.stringify({
            'id': id,
            'title': title,
            'stock': stock,
            'author': author
        }),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        console.log('Response:', data);

        if (data.code === 200) {
            // Cập nhật counter
            const cartCounter = document.getElementById('cartCounter');
            if (cartCounter) {
                cartCounter.innerText = data.data.total_quantity;
            }

            // SweetAlert2 notification
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'success',
                    title: 'Thành công!',
                    text: `Đã thêm "${title}" vào giỏ!`,
                    timer: 2500,
                    timerProgressBar: true,
                    showConfirmButton: true,
                    confirmButtonText: 'OK'
                });
            } else {
                alert(`Đã thêm "${title}" vào giỏ thành công!`);
            }
        } else {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'error',
                    title: 'Lỗi!',
                    text: data.message || 'Không thể thêm vào giỏ',
                    confirmButtonText: 'OK'
                });
            } else {
                alert(data.message || 'Có lỗi xảy ra!');
            }
        }
    })
    .catch(err => {
        console.error('Add to cart error:', err);
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'error',
                title: 'Lỗi kết nối!',
                text: 'Có lỗi xảy ra. Vui lòng thử lại!',
                confirmButtonText: 'OK'
            });
        } else {
            alert('Có lỗi xảy ra. Vui lòng thử lại!');
        }
    });
}

function updateQuantity(bookId, change) {
    fetch('/api/update-cart', {
        method: 'POST',
        body: JSON.stringify({ 'id': bookId, 'change': change }),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.code === 200) {
            const quantityInput = document.querySelector(`#quantity-${bookId}`);
            if (quantityInput) {
                quantityInput.value = data.updated_quantity;
            }

            const cartCounter = document.getElementById('cartCounter');
            if (cartCounter) {
                cartCounter.innerText = data.cart_total_quantity;
            }

            // Reload page nếu cart trống
            if (data.cart_total_quantity === 0) {
                location.reload();
            }
        } else {
            alert(data.message || 'Có lỗi xảy ra!');
        }
    })
    .catch(err => {
        console.error('Update quantity error:', err);
        alert('Có lỗi xảy ra! Vui lòng thử lại.');
    });
}

function deleteFromCart(bookId) {
    if (!confirm('Bạn có chắc muốn xóa sách này khỏi giỏ?')) {
        return;
    }

    fetch('/api/delete-cart', {
        method: 'POST',
        body: JSON.stringify({ 'id': bookId }),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        const bookRow = document.getElementById(`book-${bookId}`);
        if (bookRow) {
            bookRow.remove();
        }

        const cartCounter = document.getElementById('cartCounter');
        if (cartCounter) {
            cartCounter.innerText = data.cart_total_quantity;
        }

        if (data.cart_total_quantity === 0) {
            location.reload();
        }
    })
    .catch(err => {
        console.error('Delete from cart error:', err);
        alert('Có lỗi xảy ra! Vui lòng thử lại.');
    });
}

// ===== DOM EVENT HANDLERS =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('Cart.js loaded');
    initializeCartButtons();
});

function initializeCartButtons() {
    // Thêm vào giỏ buttons (cho trang cart.html)
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const id = this.dataset.id;
            const title = this.dataset.title || 'Sách';
            const stock = this.dataset.stock || '1';
            const author = this.dataset.author || 'Chưa rõ';
            addToCart(id, title, stock, author);
        });
    });

    // Giảm số lượng buttons
    const minusButtons = document.querySelectorAll('.btn-minus');
    minusButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const row = this.closest('tr');
            if (row) {
                const bookId = row.dataset.id;
                updateQuantity(bookId, -1);
            }
        });
    });

    // Tăng số lượng buttons
    const plusButtons = document.querySelectorAll('.btn-plus');
    plusButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const row = this.closest('tr');
            if (row) {
                const bookId = row.dataset.id;
                updateQuantity(bookId, 1);
            }
        });
    });

    // Xóa sách buttons
    const deleteButtons = document.querySelectorAll('.fa-trash');
    deleteButtons.forEach(button => {
        const deleteBtn = button.closest('button');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function(e) {
                e.preventDefault();
                const row = this.closest('tr');
                if (row) {
                    const bookId = row.dataset.id;
                    deleteFromCart(bookId);
                }
            });
        }
    });
}