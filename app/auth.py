from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g
from .db import get_db
from functools import wraps

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Прототипная карта паролей из дампа (в учебном задании)
PASSWORD_MAP = {
    'vafelka': 'Webnovel_659',
    'rar': 'Coolest_354',
    'weng': 'immrgay'
}

def get_user_by_username(username):
    db = get_db()
    return db.execute(
        'SELECT u.id, u.username, u.last_name, u.first_name, u.middle_name, r.name as role_name '
        'FROM users u JOIN roles r ON u.role_id = r.id WHERE username = ?',
        (username,)
    ).fetchone()

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
        g.user_role = None
    else:
        db = get_db()
        user = db.execute(
            'SELECT u.id, u.username, u.last_name, u.first_name, u.middle_name, r.name as role_name '
            'FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = ?',
            (user_id,)
        ).fetchone()
        g.user = user
        g.user_role = user['role_name'] if user else None

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        error = None
        user = get_user_by_username(username)
        if user is None:
            error = 'Невозможно аутентифицироваться с указанными логином и паролем'
        else:
            expected = PASSWORD_MAP.get(username)
            if expected is None or password != expected:
                error = 'Невозможно аутентифицироваться с указанными логином и паролем'

        if error:
            flash(error, 'error')
            return render_template('login.html', username=username, remember=remember)
        else:
            full_name = ' '.join(filter(None, [user['last_name'], user['first_name'], user['middle_name']]))
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = full_name
            if remember:
                session.permanent = True
            else:
                session.permanent = False

            # при редиректе на защищённую страницу часто передают next
            next_page = request.args.get('next') or request.referrer or url_for('books.index')
            if next_page.endswith('/auth/login'):
                next_page = url_for('books.index')
            return redirect(next_page)

    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('full_name', None)
    # перенаправляем на предыдущую или главную
    next_page = request.referrer or url_for('books.index')
    return redirect(next_page)

# Декораторы для проверки прав
def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.get('user') is None:
            flash('Для выполнения данного действия необходимо пройти процедуру аутентификации', 'error')
            # перенаправляем на страницу логина, сохранив next
            return redirect(url_for('auth.login', next=request.path))
        return view(**kwargs)
    return wrapped_view

def roles_required(*allowed_role_names):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.get('user') is None:
                flash('Для выполнения данного действия необходимо пройти процедуру аутентификации', 'error')
                return redirect(url_for('auth.login', next=request.path))
            role = g.get('user_role')
            if role not in allowed_role_names:
                flash('У вас недостаточно прав для выполнения данного действия', 'error')
                return redirect(url_for('books.index'))
            return view(**kwargs)
        return wrapped_view
    return decorator
