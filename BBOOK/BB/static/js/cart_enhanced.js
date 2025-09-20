// Enhanced cart.js with improved error handling and validation
document.addEventListener('DOMContentLoaded', function() {
    initializeCartButtons();
    addCartValidation();

    function initializeCartButtons() {
        // Thêm vào giỏ
        const addToCartButtons = document.querySelectorAll('.add-to-cart');
        addToCartButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Validation trước khi thêm
                if (!validateAddToCart(this)) return;
                
                // Disable button tạm thời
                this.disabled = true;
                this.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Đang thêm...';
                
                addToCart(
                    this.dataset.id, 
                    this.dataset.title, 
                    this.dataset.stock, 
                    this.dataset.author
                ).finally(() => {
                    // Enable lại button
                    this.disabled = false;
                    this.innerHTML = '<i class="fa fa-book"></i> Mượn ngay';
                });
            });
        });

        // Giảm số lượng
        const minusButtons = document.querySelectorAll('.btn-minus');
        minusButtons.forEach(button => {
            button.addEventListener('click', function() {
                const row = this.closest('tr');
                const bookId = row.dataset.id;
                updateQuantity(bookId, -1);
            });
        });

        // Tăng số lượng
        const plusButtons = document.querySelectorAll('.btn-plus');
        plusButtons.forEach(button => {
            button.addEventListener('click', function() {
                const row = this.closest('tr');
                const bookId = row.dataset.id;
                updateQuantity(bookId, 1);
            });
        });

        // Xóa sách
        const deleteButtons = document.querySelectorAll('.fa-trash');
        deleteButtons.forEach(button => {
            button.closest('button').addEventListener('click', function() {
                const row = this.closest('tr');
                const bookId = row.dataset.id;
                const bookTitle = row.querySelector('td:nth-child(2)').textContent;
                
                if (confirm(`Bạn có chắc chắn muốn xóa "${bookTitle}" khỏi giỏ mượn?`)) {
                    deleteFromCart(bookId);
                }
            });
        });
    }
    
    function addCartValidation() {
        // Validation khi submit form
        const cartForm = document.querySelector('#cartForm');
        if (cartForm) {
            cartForm.addEventListener('submit', function(e) {
                if (!validateCartSubmission()) {
                    e.preventDefault();
                }
            });
        }
    }
    
    function validateAddToCart(button) {
        const stock = parseInt(button.dataset.stock || 0);
        const title = button.dataset.title;
        
        if (!title) {
            showError('Thông tin sách không hợp lệ!');
            return false;
        }
        
        if (stock <= 0) {
            showError('Sách này hiện đã hết!');
            return false;
        }
        
        return true;
    }
    
    function validateCartSubmission() {
        const cartItems = document.querySelectorAll('.request-item');
        
        if (cartItems.length === 0) {
            showError('Giỏ mượn đang trống! Vui lòng thêm sách trước khi gửi yêu cầu.');
            return false;
        }
        
        // Kiểm tra số lượng tối đa
        let totalBooks = 0;
        cartItems.forEach(item => {
            const quantity = parseInt(item.querySelector('input[type="text"]').value || 0);
            totalBooks += quantity;
        });
        
        if (totalBooks > 10) {
            showError('Bạn chỉ có thể mượn tối đa 10 cuốn sách trong một lần!');
            return false;
        }
        
        return true;
    }
});

function addToCart(id, title, stock, author) {
    // Validation input
    if (!id || !title) {
        showError('Thông tin sách không hợp lệ!');
        return Promise.reject('Invalid book data');
    }
    
    return fetch('/api/add-cart', {
        method: 'POST',
        body: JSON.stringify({
            'id': id,
            'title': title,
            'stock': stock,
            'author': author
        }),
        headers: { 
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json();
    })
    .then(data => {
        if (data.code === 200) {
            updateCartCounter(data.data.total_quantity);
            showSuccess('Thêm sách vào giỏ thành công!');
        } else {
            showError(data.message || 'Có lỗi xảy ra khi thêm sách!');
        }
        return data;
    })
    .catch(err => {
        console.error('Add to cart error:', err);
        showError('Lỗi kết nối! Vui lòng thử lại sau.');
        throw err;
    });
}

function updateQuantity(bookId, change) {
    if (!bookId) {
        showError('ID sách không hợp lệ!');
        return;
    }
    
    const quantityInput = document.querySelector(`#quantity-${bookId}`);
    const currentQuantity = parseInt(quantityInput?.value || 0);
    
    // Validation
    if (change === -1 && currentQuantity <= 1) {
        if (confirm('Bạn có muốn xóa sách này khỏi giỏ mượn?')) {
            deleteFromCart(bookId);
        }
        return;
    }
    
    if (change === 1 && currentQuantity >= 5) {
        showError('Bạn chỉ có thể mượn tối đa 5 cuốn cho mỗi đầu sách!');
        return;
    }
    
    fetch('/api/update-cart', {
        method: 'POST',
        body: JSON.stringify({ 'id': bookId, 'change': change }),
        headers: { 
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json();
    })
    .then(data => {
        if (data.code === 200) {
            if (quantityInput) {
                quantityInput.value = data.updated_quantity;
            }
            updateCartCounter(data.cart_total_quantity);
        } else {
            showError(data.message || 'Có lỗi xảy ra khi cập nhật!');
        }
    })
    .catch(err => {
        console.error('Update quantity error:', err);
        showError('Lỗi kết nối! Vui lòng thử lại sau.');
    });
}

function deleteFromCart(bookId) {
    if (!bookId) {
        showError('ID sách không hợp lệ!');
        return;
    }
    
    fetch('/api/delete-cart', {
        method: 'POST',
        body: JSON.stringify({ 'id': bookId }),
        headers: { 
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json();
    })
    .then(data => {
        const bookRow = document.getElementById(`book-${bookId}`);
        if (bookRow) {
            bookRow.remove();
        }
        
        updateCartCounter(data.cart_total_quantity);
        showSuccess('Đã xóa sách khỏi giỏ mượn!');

        if (data.cart_total_quantity === 0) {
            setTimeout(() => location.reload(), 1000);
        }
    })
    .catch(err => {
        console.error('Delete from cart error:', err);
        showError('Lỗi kết nối! Vui lòng thử lại sau.');
    });
}

// Helper functions
function updateCartCounter(count) {
    const cartCounter = document.getElementById('cartCounter');
    if (cartCounter) {
        cartCounter.innerText = count || 0;
    }
    
    // Update navbar counter
    const navbarCounter = document.querySelector('.navbar .badge');
    if (navbarCounter) {
        navbarCounter.innerText = count || 0;
    }
}

function showSuccess(message) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: 'success',
            title: 'Thành công!',
            text: message,
            timer: 2000,
            showConfirmButton: false
        });
    } else {
        alert('✅ ' + message);
    }
}

function showError(message) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: 'error',
            title: 'Có lỗi xảy ra!',
            text: message,
            confirmButtonText: 'OK'
        });
    } else {
        alert('❌ ' + message);
    }
}

function showWarning(message) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: 'warning',
            title: 'Cảnh báo!',
            text: message,
            confirmButtonText: 'OK'
        });
    } else {
        alert('⚠️ ' + message);
    }
}

// Auto-save cart to prevent data loss
function autoSaveCart() {
    const cartData = {};
    document.querySelectorAll('.request-item').forEach(item => {
        const id = item.dataset.id;
        const quantity = item.querySelector('input[type="text"]').value;
        if (id && quantity) {
            cartData[id] = quantity;
        }
    });
    
    localStorage.setItem('bbook_cart_backup', JSON.stringify({
        data: cartData,
        timestamp: Date.now()
    }));
}

// Recovery cart on page load
function recoverCart() {
    const backup = localStorage.getItem('bbook_cart_backup');
    if (backup) {
        try {
            const parsed = JSON.parse(backup);
            // Only recover if backup is less than 1 hour old
            if (Date.now() - parsed.timestamp < 3600000) {
                console.log('Cart backup found:', parsed.data);
                // Implement recovery logic if needed
            }
        } catch (e) {
            console.error('Error parsing cart backup:', e);
        }
    }
}

// Initialize auto-save
setInterval(autoSaveCart, 30000); // Auto-save every 30 seconds
