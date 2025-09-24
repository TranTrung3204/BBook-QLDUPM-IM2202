class ImportRecordManager {
    constructor() {
        this.$searchInput = $("#book_search");
        this.$bookId = $("#book_id");
        this.$bookTitle = $("#book_title");
        this.$newBookFields = $("#new_book_fields");
        this.$oldBookFields = $("#old_book_fields");
        this.init();
    }

    init() {
        this.bindEvents();
    }

    bindEvents() {
        this.$searchInput.on("input", () => {
            let query = this.$searchInput.val().trim();
            if (query.length >= 2) {
                this.searchBooks(query);
            } else {
                this.closeSuggestions();
            }
        });
    }

    searchBooks(query) {
        $.ajax({
    url: '/api/check_book/' + bookId, // phải đúng route Flask
    type: 'GET',
    success: function(response) {
        // xử lý response
    },
    error: function() {
        alert('Lỗi khi kiểm tra sách!');
    }
});

    }

    showSuggestions(books) {
        this.closeSuggestions();
        let $list = $("<ul>", { class: "list-group position-absolute w-100", id: "book_suggestions" });
        books.forEach(book => {
            let $item = $("<li>", {
                class: "list-group-item list-group-item-action",
                text: `${book.id} - ${book.title}`
            });
            $item.on("click", () => {
                this.selectBook(book);
            });
            $list.append($item);
        });
        this.$searchInput.after($list);
    }

    closeSuggestions() {
        $("#book_suggestions").remove();
    }

    selectBook(book) {
        this.$bookId.val(book.id);
        this.$searchInput.val(`${book.id} - ${book.title}`);
        if (book.is_existing) {
            this.$newBookFields.hide();
            this.$oldBookFields.show();
            $("#is_new").val("false");
        } else {
            this.$newBookFields.show();
            this.$oldBookFields.show();
            $("#is_new").val("true");
        }
        this.closeSuggestions();
    }
}

$(document).ready(() => {
    new ImportRecordManager();
});
