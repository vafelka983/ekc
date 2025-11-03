import os
import math
import hashlib
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, current_app, g, url_for, redirect, flash
from .db import get_db
from .auth import login_required, roles_required

# внешние библиотеки для Markdown + санитайза
import markdown
import bleach

bp = Blueprint('books', __name__)

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_filename(filename):
    if not filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in ALLOWED_EXT


def save_cover_file(uploaded_file):
    """Сохранить файл обложки в static и вернуть (filename, mime, md5)"""
    if uploaded_file is None or uploaded_file.filename == '':
        return None
    filename = secure_filename(uploaded_file.filename)
    if not allowed_filename(filename):
        return None
    static_folder = current_app.static_folder
    base, ext = os.path.splitext(filename)
    digest = hashlib.md5((filename + str(os.urandom(8))).encode('utf-8')).hexdigest()[:12]
    filename = f"{base}_{digest}{ext}"
    path = os.path.join(static_folder, filename)
    uploaded_file.save(path)

    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    md5_hex = md5.hexdigest()
    mime = uploaded_file.mimetype or 'application/octet-stream'
    return filename, mime, md5_hex


# --- Markdown -> HTML + санитайзер ---
ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em', 'i', 'li', 'ol',
    'pre', 'strong', 'ul', 'p', 'br', 'h1', 'h2', 'h3', 'h4', 'hr'
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
}


def render_review_text(md_text: str) -> str:
    """Конвертирует Markdown в безопасный HTML"""
    if md_text is None:
        return ''
    # конвертируем Markdown -> HTML
    html = markdown.markdown(md_text, extensions=['extra', 'sane_lists'])
    # очищаем HTML от опасных тегов/атрибутов
    clean = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)
    # превращаем найденные URL'ы в ссылки (bleach.linkify)
    clean = bleach.linkify(clean)
    # безопасно: добавим rel="nofollow" к ссылкам — bleach.linkify это делает по умолчанию для target? нет, но rel оставить
    # (bleach.linkify при необходимости можно настроить, но для простоты оставим стандартное)
    return clean


def get_search_filters():
    """Получить параметры поиска из запроса"""
    title = request.args.get('title', '').strip()
    genres = request.args.getlist('genres')
    years = request.args.getlist('years')
    pages_min = request.args.get('pages_min', '').strip()
    pages_max = request.args.get('pages_max', '').strip()
    author = request.args.get('author', '').strip()

    return {
        'title': title,
        'genres': genres,
        'years': years,
        'pages_min': pages_min,
        'pages_max': pages_max,
        'author': author
    }


def build_search_query(filters, page, per_page):
    """Построить SQL запрос с фильтрами"""
    where_conditions = []
    params = []

    # Фильтр по названию (частичное совпадение)
    if filters['title']:
        where_conditions.append("b.title LIKE ?")
        params.append(f"%{filters['title']}%")

    # Фильтр по автору (частичное совпадение)
    if filters['author']:
        where_conditions.append("b.author LIKE ?")
        params.append(f"%{filters['author']}%")

    # Фильтр по жанрам
    if filters['genres']:
        placeholders = ','.join(['?'] * len(filters['genres']))
        where_conditions.append(f"g.id IN ({placeholders})")
        params.extend(filters['genres'])

    # Фильтр по годам
    if filters['years']:
        placeholders = ','.join(['?'] * len(filters['years']))
        where_conditions.append(f"b.year IN ({placeholders})")
        params.extend(filters['years'])

    # Фильтр по объёму страниц
    if filters['pages_min']:
        try:
            where_conditions.append("b.pages >= ?")
            params.append(int(filters['pages_min']))
        except ValueError:
            pass

    if filters['pages_max']:
        try:
            where_conditions.append("b.pages <= ?")
            params.append(int(filters['pages_max']))
        except ValueError:
            pass

    # Базовый запрос
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # Запрос для подсчёта общего количества
    count_query = f"""
    SELECT COUNT(DISTINCT b.id) as cnt 
    FROM books b
    LEFT JOIN book_genres bg ON bg.book_id = b.id
    LEFT JOIN genres g ON g.id = bg.genre_id
    {where_clause}
    """

    # Основной запрос
    offset = (page - 1) * per_page
    main_query = f"""
    SELECT b.id, b.title, b.year, b.author, b.pages,
           REPLACE(GROUP_CONCAT(DISTINCT g.name), ',', ', ') as genres,
           COALESCE(ar.avg_rating, 0) as avg_rating,
           COALESCE(rc.cnt, 0) as review_count,
           c.filename as cover
    FROM books b
    LEFT JOIN book_genres bg ON bg.book_id = b.id
    LEFT JOIN genres g ON g.id = bg.genre_id
    LEFT JOIN (
        SELECT book_id, ROUND(AVG(rating), 2) as avg_rating FROM reviews GROUP BY book_id
    ) ar ON ar.book_id = b.id
    LEFT JOIN (
        SELECT book_id, COUNT(*) as cnt FROM reviews GROUP BY book_id
    ) rc ON rc.book_id = b.id
    LEFT JOIN covers c ON c.book_id = b.id
    {where_clause}
    GROUP BY b.id
    ORDER BY b.year DESC, b.id DESC
    LIMIT ? OFFSET ?
    """

    params.extend([per_page, offset])

    return count_query, main_query, params


# --- Список книг с поиском ---
@bp.route('/')
def index():
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    per_page = 10

    db = get_db()

    # Получить фильтры поиска
    filters = get_search_filters()

    # Получить уникальные годы для селекта
    years = db.execute("SELECT DISTINCT year FROM books ORDER BY year DESC").fetchall()

    # Получить все жанры
    genres_all = db.execute('SELECT id, name FROM genres ORDER BY name').fetchall()

    # Построить запрос с фильтрами
    count_query, main_query, params = build_search_query(filters, page, per_page)

    # Выполнить запросы
    total = db.execute(count_query, params[:-2]).fetchone()['cnt']  # Исключаем LIMIT/OFFSET параметры
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    books = db.execute(main_query, params).fetchall()

    return render_template('index.html',
                           books=books,
                           page=page,
                           total_pages=total_pages,
                           filters=filters,
                           years=years,
                           genres_all=genres_all)


# --- Просмотр книги: теперь отдаём отдельно рецензию текущего пользователя и остальные рецензии ---
@bp.route('/book/<int:book_id>')
def book_view(book_id):
    db = get_db()
    book = db.execute(
        "SELECT b.id, b.title, b.short_description, b.year, b.publisher, b.author, b.pages, "
        "REPLACE(GROUP_CONCAT(DISTINCT g.name), ',', ', ') as genres, c.filename as cover "
        "FROM books b "
        "LEFT JOIN book_genres bg ON bg.book_id = b.id "
        "LEFT JOIN genres g ON g.id = bg.genre_id "
        "LEFT JOIN covers c ON c.book_id = b.id "
        "WHERE b.id = ? "
        "GROUP BY b.id",
        (book_id,)
    ).fetchone()
    if book is None:
        flash('Книга не найдена', 'error')
        return redirect(url_for('books.index'))

    # id текущего пользователя (если залогинен)
    current_user_id = g.user['id'] if g.get('user') else None

    # 1) Получаем одобренные рецензии (видимые всем), но исключаем рецензию текущего пользователя
    approved_rows = db.execute(
        "SELECT r.id, r.user_id, r.rating, r.text, r.created_at, u.username, u.last_name, u.first_name "
        "FROM reviews r "
        "JOIN review_statuses rs ON r.status_id = rs.id "
        "JOIN users u ON r.user_id = u.id "
        "WHERE r.book_id = ? AND rs.name = 'одобрена' "
        "ORDER BY r.created_at DESC",
        (book_id,)
    ).fetchall()

    approved_reviews = []
    for r in approved_rows:
        # исключаем собственную рецензию, чтобы не дублировать
        if current_user_id is not None and r['user_id'] == current_user_id:
            continue
        approved_reviews.append({
            'id': r['id'],
            'rating': r['rating'],
            'created_at': r['created_at'],
            'username': r['username'],
            'name': ' '.join(filter(None, [r['last_name'], r['first_name']])),
            'html': render_review_text(r['text'])
        })

    # 2) Если пользователь залогинен — получаем его собственную рецензию (любого статуса)
    user_review = None
    if current_user_id:
        ur = db.execute(
            "SELECT r.id, r.rating, r.text, r.created_at, rs.name as status_name "
            "FROM reviews r JOIN review_statuses rs ON r.status_id = rs.id "
            "WHERE r.book_id = ? AND r.user_id = ? LIMIT 1",
            (book_id, current_user_id)
        ).fetchone()
        if ur:
            user_review = {
                'id': ur['id'],
                'rating': ur['rating'],
                'created_at': ur['created_at'],
                'status': ur['status_name'],
                'html': render_review_text(ur['text'])
            }

    return render_template('book.html', book=book, user_review=user_review, reviews=approved_reviews)


# --- Удаление книги (без изменений) ---
@bp.route('/book/<int:book_id>/delete', methods=['POST'])
@roles_required('админ')
def book_delete(book_id):
    db = get_db()
    covers = db.execute('SELECT filename FROM covers WHERE book_id = ?', (book_id,)).fetchall()
    cover_filenames = [row['filename'] for row in covers]

    book = db.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        flash('Книга не найдена', 'error')
        return redirect(url_for('books.index'))
    title = book['title']

    db.execute('DELETE FROM books WHERE id = ?', (book_id,))
    db.commit()

    static_folder = current_app.static_folder
    for fn in cover_filenames:
        try:
            path = os.path.join(static_folder, fn)
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            current_app.logger.exception(f'Не удалось удалить файл обложки {fn}')

    flash(f'Книга «{title}» успешно удалена', 'success')
    return redirect(url_for('books.index'))


# --- Добавление книги (без изменений) ---
@bp.route('/book/add', methods=['GET', 'POST'])
@roles_required('админ')
def book_add():
    db = get_db()
    genres_all = db.execute('SELECT id, name FROM genres ORDER BY name').fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        short_description = request.form.get('short_description', '').strip()
        year = request.form.get('year', '').strip() or None
        publisher = request.form.get('publisher', '').strip()
        author = request.form.get('author', '').strip()
        pages = request.form.get('pages', '').strip() or None
        genres_selected = request.form.getlist('genres')

        if not title or not short_description or not year or not publisher or not author or not pages:
            flash('Заполните все обязательные поля', 'error')
            return render_template('book_form.html', genres=genres_all, form=request.form)

        cur = db.execute(
            'INSERT INTO books (title, short_description, year, publisher, author, pages) VALUES (?, ?, ?, ?, ?, ?)',
            (title, short_description, int(year), publisher, author, int(pages))
        )
        book_id = cur.lastrowid

        if genres_selected:
            for gid in genres_selected:
                db.execute('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, int(gid)))

        file = request.files.get('cover')
        saved = save_cover_file(file)
        if saved:
            filename, mime, md5 = saved
            db.execute('INSERT INTO covers (filename, mime_type, md5_hash, book_id) VALUES (?, ?, ?, ?)',
                       (filename, mime, md5, book_id))

        db.commit()
        flash('Книга успешно добавлена', 'success')
        return redirect(url_for('books.book_view', book_id=book_id))

    return render_template('book_form.html', genres=genres_all, form=None, action='add')


# --- Редактирование книги (без изменений) ---
@bp.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
@roles_required('админ', 'модератор')
def book_edit(book_id):
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        flash('Книга не найдена', 'error')
        return redirect(url_for('books.index'))

    genres_all = db.execute('SELECT id, name FROM genres ORDER BY name').fetchall()
    current_genres = [str(row['genre_id']) for row in
                      db.execute('SELECT genre_id FROM book_genres WHERE book_id = ?', (book_id,)).fetchall()]

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        short_description = request.form.get('short_description', '').strip()
        year = request.form.get('year', '').strip() or None
        publisher = request.form.get('publisher', '').strip()
        author = request.form.get('author', '').strip()
        pages = request.form.get('pages', '').strip() or None
        genres_selected = request.form.getlist('genres')

        if not title or not short_description or not year or not publisher or not author or not pages:
            flash('Заполните все обязательные поля', 'error')
            return render_template('book_form.html', genres=genres_all, form=request.form, action='edit', book=book,
                                   current_genres=current_genres)

        db.execute('UPDATE books SET title=?, short_description=?, year=?, publisher=?, author=?, pages=? WHERE id=?',
                   (title, short_description, int(year), publisher, author, int(pages), book_id))

        db.execute('DELETE FROM book_genres WHERE book_id = ?', (book_id,))
        if genres_selected:
            for gid in genres_selected:
                db.execute('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, int(gid)))

        file = request.files.get('cover')
        if file and file.filename != '':
            covers = db.execute('SELECT filename FROM covers WHERE book_id = ?', (book_id,)).fetchall()
            for row in covers:
                fn = row['filename']
                if fn:
                    try:
                        path = os.path.join(current_app.static_folder, fn)
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception:
                        current_app.logger.exception(f'Не удалось удалить старый файл обложки {fn}')
            db.execute('DELETE FROM covers WHERE book_id = ?', (book_id,))

            saved = save_cover_file(file)
            if saved:
                filename, mime, md5 = saved
                db.execute('INSERT INTO covers (filename, mime_type, md5_hash, book_id) VALUES (?, ?, ?, ?)',
                           (filename, mime, md5, book_id))

        db.commit()
        flash('Книга успешно обновлена', 'success')
        return redirect(url_for('books.book_view', book_id=book_id))

    return render_template('book_form.html', genres=genres_all, form=book, action='edit', book=book,
                           current_genres=current_genres)


# --- НОВЫЙ: создание рецензии ---
@bp.route('/book/<int:book_id>/review/add', methods=['GET', 'POST'])
@login_required
@roles_required('пользователь', 'модератор', 'админ')
def book_review_add(book_id):
    db = get_db()
    # проверим, что книга существует
    book = db.execute('SELECT id, title FROM books WHERE id = ?', (book_id,)).fetchone()
    if book is None:
        flash('Книга не найдена', 'error')
        return redirect(url_for('books.index'))

    user_id = g.user['id']

    # проверим, не писал ли пользователь рецензию ранее
    existing = db.execute('SELECT id FROM reviews WHERE book_id = ? AND user_id = ?', (book_id, user_id)).fetchone()
    if existing:
        flash('Вы уже оставляли рецензию на эту книгу', 'error')
        return redirect(url_for('books.book_view', book_id=book_id))

    if request.method == 'POST':
        # оценка и текст
        try:
            rating = int(request.form.get('rating', '5'))
        except ValueError:
            rating = None
        text = request.form.get('text', '').strip()

        if rating is None or rating < 0 or rating > 5:
            flash('Неверная оценка', 'error')
            return render_template('review_form.html', book=book, form=request.form)

        if not text:
            flash('Текст рецензии не может быть пустым', 'error')
            return render_template('review_form.html', book=book, form=request.form)

        # вставка: сохраняем исходный Markdown в БД, рендерим только при отображении
        db.execute('INSERT INTO reviews (book_id, user_id, rating, text) VALUES (?, ?, ?, ?)',
                   (book_id, user_id, rating, text))
        db.commit()
        flash('Рецензия успешно сохранена', 'success')
        return redirect(url_for('books.book_view', book_id=book_id))

    # GET
    return render_template('review_form.html', book=book, form=None)


@bp.route('/reviews/my')
@login_required
def my_reviews():
    db = get_db()
    uid = g.user['id']
    rows = db.execute(
        "SELECT r.id, r.rating, r.text, r.created_at, rs.name as status_name, b.id as book_id, b.title as book_title "
        "FROM reviews r "
        "JOIN review_statuses rs ON r.status_id = rs.id "
        "JOIN books b ON r.book_id = b.id "
        "WHERE r.user_id = ? "
        "ORDER BY r.created_at DESC",
        (uid,)
    ).fetchall()

    reviews = []
    for r in rows:
        reviews.append({
            'id': r['id'],
            'rating': r['rating'],
            'created_at': r['created_at'],
            'status': r['status_name'],
            'book_id': r['book_id'],
            'book_title': r['book_title'],
            'html': render_review_text(r['text'])
        })

    return render_template('my_reviews.html', reviews=reviews)


@bp.route('/moderation/reviews')
@roles_required('модератор')
def moderation_list():
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        page = 1
    per_page = 10
    offset = (page - 1) * per_page

    db = get_db()
    total_row = db.execute(
        "SELECT COUNT(*) as cnt FROM reviews r JOIN review_statuses rs ON r.status_id = rs.id WHERE rs.name = 'на рассмотрении'"
    ).fetchone()
    total = total_row['cnt'] if total_row else 0
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    rows = db.execute(
        "SELECT r.id, r.created_at, u.username, u.last_name, u.first_name, b.id as book_id, b.title as book_title "
        "FROM reviews r "
        "JOIN review_statuses rs ON r.status_id = rs.id "
        "JOIN users u ON r.user_id = u.id "
        "JOIN books b ON r.book_id = b.id "
        "WHERE rs.name = 'на рассмотрении' "
        "ORDER BY r.created_at ASC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()

    items = []
    for r in rows:
        items.append({
            'id': r['id'],
            'created_at': r['created_at'],
            'username': r['username'],
            'name': ' '.join(filter(None, [r['last_name'], r['first_name']])),
            'book_id': r['book_id'],
            'book_title': r['book_title']
        })

    return render_template('moderation_list.html', reviews=items, page=page, total_pages=total_pages)


@bp.route('/moderation/review/<int:review_id>', methods=['GET', 'POST'])
@roles_required('модератор')
def moderation_review(review_id):
    db = get_db()
    row = db.execute(
        "SELECT r.id, r.rating, r.text, r.created_at, u.username, u.last_name, u.first_name, b.id as book_id, b.title as book_title, rs.name as status_name "
        "FROM reviews r "
        "JOIN users u ON r.user_id = u.id "
        "JOIN books b ON r.book_id = b.id "
        "JOIN review_statuses rs ON r.status_id = rs.id "
        "WHERE r.id = ?",
        (review_id,)
    ).fetchone()

    if row is None:
        flash('Рецензия не найдена', 'error')
        return redirect(url_for('books.moderation_list'))

    review = {
        'id': row['id'],
        'rating': row['rating'],
        'created_at': row['created_at'],
        'username': row['username'],
        'name': ' '.join(filter(None, [row['last_name'], row['first_name']])),
        'book_id': row['book_id'],
        'book_title': row['book_title'],
        'status': row['status_name'],
        'html': render_review_text(row['text'])
    }

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'approve':
            # set status to 'одобрена'
            db.execute(
                "UPDATE reviews SET status_id = (SELECT id FROM review_statuses WHERE name='одобрена') WHERE id = ?",
                (review_id,)
            )
            db.commit()
            flash('Рецензия одобрена', 'success')
            return redirect(url_for('books.moderation_list'))
        elif action == 'reject':
            db.execute(
                "UPDATE reviews SET status_id = (SELECT id FROM review_statuses WHERE name='отклонена') WHERE id = ?",
                (review_id,)
            )
            db.commit()
            flash('Рецензия отклонена', 'success')
            return redirect(url_for('books.moderation_list'))
        else:
            flash('Неизвестное действие', 'error')

    return render_template('moderation_review.html', review=review)