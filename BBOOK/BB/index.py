from math import ceil

import cloudinary
from flask import Flask, render_template, request, url_for, redirect, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from BBOOK.BB import app, dao, models
from BBOOK.BB.models import UserRole, Book


@app.route("/")
def index():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    kw = request.args.get('kw')
    prods = dao.load_books(kw)
    return render_template('index.html', products=prods)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'user_signin'


@app.route('/contact')
def contact():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    return render_template('contact.html')


@login_manager.user_loader
def user_load(user_id):
    return dao.get_user_by_id(user_id=user_id)


@app.route("/register", methods=['GET', 'POST'])
def user_register():
    err_msg = ""
    if request.method == 'POST':
        fullName = request.form.get('fullName')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        avatar_path = None
        try:
            if password.strip() == confirm.strip():
                avatar = request.files.get('avatar')
                if avatar:
                    res = cloudinary.uploader.upload(avatar)
                    avatar_path = res['secure_url']
                dao.add_user(fullName=fullName, username=username, password=password, email=email, avatar=avatar_path)
                return redirect(url_for('user_signin'))
            else:
                err_msg = 'Passwords do not match'
        except Exception as ex:
            err_msg = "404 not found: " + str(ex)

    return render_template('register.html', err_msg=err_msg)


@app.route("/user-login", methods=['GET', 'POST'])
def user_signin():
    err_msg = ""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = dao.check_login(username=username, password=password)
        if user:
            login_user(user=user)
            # Kiểm tra vai trò người dùng và chuyển hướng phù hợp
            if user.role == UserRole.ADMIN:
                return redirect(url_for('admin_login'))
            else:
                return redirect(url_for('index'))
        else:
            err_msg = 'Username or password is incorrect !!!'
    return render_template('login.html', err_msg=err_msg)


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = dao.check_login(username=username, password=password,
                               role=[UserRole.ADMIN, UserRole.LIBRARIAN])

        if user:
            login_user(user=user)
            return redirect('/admin')
        else:
            flash('Đăng nhập không hợp lệ. Vui lòng kiểm tra lại thông tin.', 'error')

    return render_template('admin/login.html')


@app.route("/user-logout")
def user_signout():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin_login'))
    if 'cart' in session:  # xoá giỏ hàng trước khi đăng xuất
        del session['cart']
    logout_user()
    return redirect(url_for('user_signin'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
