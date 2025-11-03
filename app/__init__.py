import os
from flask import Flask

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'dev-secret-key')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'library.db')

    # ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # init db
    from . import db
    db.init_app(app)

    # register auth blueprint
    from . import auth
    app.register_blueprint(auth.bp)

    # register books blueprint (главная и страницы книг)
    from . import books
    app.register_blueprint(books.bp)

    return app
