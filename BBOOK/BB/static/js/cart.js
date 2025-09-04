document.addEventListener('DOMContentLoaded', function() {
    initializeCartButtons();

    function initializeCartButtons() {
        // Thêm vào giỏ
        const addToCartButtons = document.querySelectorAll('.add-to-cart');
        addToCartButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                addToCart(this.dataset.id, this.dataset.title);
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
                deleteFromCart(bookId);
            });
        });
    }
});

function addToCart(id, title, stock, author) {
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
        if (data.code === 200) {
            document.getElementById('cartCounter').innerText = data.data.total_quantity;
            alert('Thêm sách vào giỏ thành công!');
        } else {
            alert(data.message);
        }
    })
    .catch(err => console.error(err));
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
            document.querySelector(`#quantity-${bookId}`).value = data.updated_quantity;
            document.getElementById('cartCounter').innerText = data.cart_total_quantity;
        }
    })
    .catch(err => console.error('Error:', err));
}


function deleteFromCart(bookId) {
    fetch('/api/delete-cart', {
        method: 'POST',
        body: JSON.stringify({ 'id': bookId }),
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById(`book-${bookId}`).remove();
        document.getElementById('cartCounter').innerText = data.cart_total_quantity;

        if (data.cart_total_quantity === 0) {
            location.reload();
        }
    });
}
