import hashlib

def get_md5(file_path):
    """Возвращает MD5-хэш файла."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:  # читаем файл в бинарном режиме
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except FileNotFoundError:
        return "Файл не найден"

if __name__ == "__main__":
    path = "app/static/suicide_hunter.jpg"
    print("MD5:", get_md5(path))
