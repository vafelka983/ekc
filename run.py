from app import create_app

app = create_app()

if __name__ == '__main__':
    # Для разработки запускаем с debug=True
    app.run(debug=True, host='127.0.0.1', port=5000)
