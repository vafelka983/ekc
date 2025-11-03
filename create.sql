PRAGMA foreign_keys = ON;

-- Удаляем старые таблицы (чтобы можно было запускать скрипт повторно)
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS covers;
DROP TABLE IF EXISTS book_genres;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;

-- 1. Таблицы
-- Роли
CREATE TABLE roles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

-- Пользователи
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  last_name TEXT NOT NULL,
  first_name TEXT NOT NULL,
  middle_name TEXT,
  role_id INTEGER NOT NULL,
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

-- Жанры
CREATE TABLE genres (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

-- Книги
CREATE TABLE books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  short_description TEXT NOT NULL,
  year INTEGER NOT NULL,
  publisher TEXT NOT NULL,
  author TEXT NOT NULL,
  pages INTEGER NOT NULL
);

-- Связующая таблица many-to-many book <-> genre
CREATE TABLE book_genres (
  book_id INTEGER NOT NULL,
  genre_id INTEGER NOT NULL,
  PRIMARY KEY (book_id, genre_id),
  FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
  FOREIGN KEY (genre_id) REFERENCES genres(id) ON DELETE CASCADE
);

-- Обложки
CREATE TABLE covers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  md5_hash TEXT NOT NULL,
  book_id INTEGER NOT NULL,
  FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE TABLE review_statuses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

INSERT INTO review_statuses (name, description) VALUES
  ('на рассмотрении', 'Рецензия ожидает модерации'),
  ('одобрена', 'Рецензия одобрена и видна всем'),
  ('отклонена', 'Рецензия отклонена модератором');

-- Рецензии (теперь с полем status_id)
CREATE TABLE reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  book_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  rating INTEGER NOT NULL CHECK(rating BETWEEN 0 AND 5),
  text TEXT NOT NULL,
  status_id INTEGER NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (status_id) REFERENCES review_statuses(id) ON DELETE RESTRICT
);


-- Индексы полезные
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_reviews_book ON reviews(book_id);


-- 2. Начальные данные

-- Роли
INSERT INTO roles (name, description) VALUES
  ('админ','суперпользователь, имеет полный доступ к системе, в том числе к созданию и удалению книг'),
  ('модератор','может редактировать данные книг и производить модерацию рецензий'),
  ('пользователь','может оставлять рецензии');

-- Жанры (расширенный набор)
INSERT INTO genres (name) VALUES
  ('фэнтези'),
  ('культивация'),
  ('повседневность'),
  ('романтика'),
  ('литRPG'),
  ('исекай'),
  ('фанфик'),
  ('супергерои'),
  ('урбан-фэнтези'),
  ('тёмное фэнтези'),
  ('приключения'),
  ('триллер'),
  ('вебновелла');

-- Пользователи 
-- Пароли указанны как хеши (оставил существующие три хеша, добавил пару тестовых пользователей).
-- Примечание: если хочешь задать конкретные пароли — замени поле password_hash на нужный хеш.
INSERT INTO users (username, password_hash, last_name, first_name, middle_name, role_id) VALUES
  ('Vafelka', 'scrypt:32768:8:1$Y2PiOSwFzzK4hbwZ$f5dc3b89807dfd364e414772d9a650de84d0684179aff7820c897e8614bb1119f6d3a4f210db413f6004a6401bd795bee617600c0c7ed5d64b33249c09ca828c', 'Казински', 'Зориан', NULL, (SELECT id FROM roles WHERE name='админ')),
  ('noveda', 'scrypt:32768:8:1$RxpRj9PvrEdh1PEt$eaee24075e46aa281be29077cb5825647c2c2e0b28822121a4061ac2332a95ca75e0781c2c90feeec5c62c5be2187bd1ba5b42530b44dfcd68946804c7d805d7', 'Зак', 'Новеда', NULL, (SELECT id FROM roles WHERE name='модератор')),
  ('jornak', 'scrypt:32768:8:1$rWtKx4ddJHIkUltK$05b517a9ed920ef1ab9198ee2f04593c2970674bee9aea37384cb68798e03f46f59f5c6557c3f072b1c798e848ebd46a4fdad1f49b32a8518ca32affcbeeadb4', 'Жорнак', 'Докочин', NULL, (SELECT id FROM roles WHERE name='пользователь'));

INSERT INTO books (title, short_description, year, publisher, author, pages) VALUES
  ('Мать ученья', 
   'Студент-маг застревает в цикле повторяющегося последнего месяца обучения; каждый цикл позволяет улучшить магические навыки и подготовиться к выходу за пределы школы. История сочетает юмор, методичный прогресс и фокус на обучении магии.', 
   2020, -- русский перевод и активная онлайн-публикация около 2020 (оригинал/переводная история).
   'WebNovella Press', 'Домагой Курмаич (nobody103)', 420),

  ('Преподобный Гу',
   'Культивационная вебновелла про перерождение и рост силы в мире, где «гу» — особые сущности/силы; сюжет фокусируется на выживании, достижении силы и взаимодействиях с кланами/сектах.',
   2012, -- приблизительный год начала публикации (~2012)
   'Ranobe House', 'Gu Zhen Ren (郭真人)', 310),

  ('Дракон Вайнкер',
   'Комбинация фэнтези и игрового механизма: дракон, вор и система квестов/уровней. История местами аркадна и юмористична; точная дата оригинальной публикации в сети не установлена.',
   2015, -- год установлен приблизительно (точная дата неизвестна)
   'NetTales', 'Vainqueur (автор не точно установлен)', 280),

  ('Гарри Поттер и методы рационального мышления',
   'Фанфик, где Гарри — чрезвычайно рациональный и научно мыслящий персонаж; упор на вероятности, гипотезы и экспериментальное мышление в мире магии.',
   2010, -- первая глава 28 февраля 2010 (публикация фанфика началась в 2010)
   'HPMOR Online', 'Элиезер Юдковский', 700),

  ('Червь', 
   'Worm (Wildbow): подросток получает способность управлять насекомыми; сюжет — мрачная и реалистичная эпопея о сверхгероях, тактике и выживании в городе с конфликтами героев и злодеев.',
   2011, -- публикация 2011–2013
   'Wildbow Online', 'John C. McCrae (Wildbow)', 1600), -- pages примерно для полной онлайн-публикации (ориентировочно)

  ('Пакт',
   'Автор John C. McCrae. Урбан-фэнтези/ужасы: библиотечная наследственность втягивает героя в опасный мир магии и духов с высоким уровнем угроз и моральной неоднозначностью.',
   2013, -- ориентировочный год онлайн-публикации (точная дата не указана)
   'WebHorror Press', 'John C. McCrae', 520),

  ('Вечная Воля',
   'Культовая китайская культивация про персонажа, мечтающего о бессмертии; сочетание юмора, приключений и прогресса героя в мире с духовными испытаниями.',
   2016, -- год оригинала примерно 2016
   'Ranobe House', 'Er Gen (耳根)', 560),

  ('Повелитель тайн',
   'Герой просыпается в теле другого человека в мире, где магия и индустрия переплетены; расследование, тайны и постепенное раскрытие прошлого.',
   2024, -- российское издание 2024
   'Murawei Press', 'Е Юань (余鸢)', 420),

  ('Точка зрения Всеведущего читателя',
   'Главный герой обнаруживает, что события популярного романа становятся реальностью; он использует знания «из будущих глав», чтобы выжить и влиять на сюжет.',
   2018, -- год издания/появления примерно 2018
   'LiveLib Editions', 'Син Сён (신숑)', 460),

  ('Ублюдок FFF-ранга',
   'История человека, который после победы над демоном получает низкую «оценку» за характер и начинает путь заново, чтобы изменить своё место в мире — смесь тёмной и героической иронии.',
   2018, -- ориентировочно
   'Ranobe Hub', 'Farnar (파르나르)', 380),

  ('Охотник-суицидник',
   'Про охотника с невзрачным навыком, который оказывается ключом к невероятной силе; типичное повествование «слабый становится сильным» в сеттинге охотников/монстров.',
   2018, -- ориентировочно
   'Ranobe Hub', 'Shin Noah (신노아)', 400),

  ('Теневой раб',
   'Темный роман о персонаже, поднимающемся из нищеты к статусу элитного Пробуждённого; мрачная атмосфера, рост силы и политические интриги.',
   2017, -- примерный год (веб-новелла, точная дата не всегда указана)
   'DarkWeb Novels', 'Guiltythree', 360);


INSERT INTO books (title, short_description, year, publisher, author, pages) VALUES
  ('Идеальный забег',
   'Райан «Квиксейв» Романо получает способность ставить "сохранения" как в игре и живёт жизнь заново. Он попадает в Новый Рим — город суперсил, корпораций и монстров, где пытается использовать свою силу, не потеряв человечность.',
   2022,
   'LiveLib Publishing',
   'Максим Дюран (Maxim J. Durand)',
   480),

  ('Зенит Колдовства',
   'После изгнания могущественный маг Маркус возвращается в мир, где сталкиваются монстры, культы и цивилизации. Он не ищет мести, а стремится к пониманию, учёбе и возможно, передаче знаний новому поколению.',
   2023,
   'RanobeHub',
   'Domagoj Kurmaic (nobody103)',
   520),

  ('Re:Zero. Жизнь с нуля в альтернативном мире',
   'Молодой человек Субару Нацуки внезапно переносится в другой мир и обнаруживает, что каждый раз после смерти возвращается назад во времени. Его путь — бесконечные попытки изменить трагические исходы.',
   2012,
   'MF Bunko J',
   'Таппэй Нагацуки (Tappei Nagatsuki)',
   420),

  ('Практическое руководство по злу',
   'Империя Ужаса правит завоёванными землями. Сирота Кэтрин Найдёныш получает шанс стать героиней… но выбирает путь злодейки. Ироничная история о морали, власти и мета-сюжете героизма.',
   2023,
   'WebFiction Publishing',
   'overslept',
   650);

-- Связи книга-жанр (many-to-many)
INSERT INTO book_genres (book_id, genre_id)
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Мать ученья' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Мать ученья' AND g.name='повседневность'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Преподобный Гу' AND g.name='культивация'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Дракон Вайнкер' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Дракон Вайнкер' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Гарри Поттер и методы рационального мышления' AND g.name='фанфик'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Червь' AND g.name='супергерои'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Червь' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Пакт' AND g.name='урбан-фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Вечная Воля' AND g.name='культивация'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Повелитель тайн' AND g.name='мистика'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Повелитель тайн' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Точка зрения Всеведущего читателя' AND g.name='исекай'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Ублюдок FFF-ранга' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Охотник-суицидник' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Теневой раб' AND g.name='тёмное фэнтези';


INSERT INTO book_genres (book_id, genre_id)
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Мать ученья' AND g.name='литRPG'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Мать ученья' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Преподобный Гу' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Дракон Вайнкер' AND g.name='литRPG'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Гарри Поттер и методы рационального мышления' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Гарри Поттер и методы рационального мышления' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Червь' AND g.name='триллер'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Пакт' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Вечная Воля' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Точка зрения Всеведущего читателя' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Теневой раб' AND g.name='приключения';


INSERT INTO book_genres (book_id, genre_id)
  -- Идеальный забег
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Идеальный забег' AND g.name='супергерои'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Идеальный забег' AND g.name='литRPG'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Идеальный забег' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Идеальный забег' AND g.name='вебновелла'

UNION ALL
  -- Зенит Колдовства
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Зенит Колдовства' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Зенит Колдовства' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Зенит Колдовства' AND g.name='приключения'

UNION ALL
  -- Re:Zero
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Re:Zero. Жизнь с нуля в альтернативном мире' AND g.name='исекай'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Re:Zero. Жизнь с нуля в альтернативном мире' AND g.name='романтика'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Re:Zero. Жизнь с нуля в альтернативном мире' AND g.name='приключения'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Re:Zero. Жизнь с нуля в альтернативном мире' AND g.name='тёмное фэнтези'

UNION ALL
  -- Практическое руководство по злу
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Практическое руководство по злу' AND g.name='фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Практическое руководство по злу' AND g.name='тёмное фэнтези'
UNION ALL
  SELECT b.id, g.id FROM books b, genres g WHERE b.title='Практическое руководство по злу' AND g.name='вебновелла';


-- Обложки (md5_hash — заглушки; при наличии файлов замени хэши/имена)
INSERT INTO covers (filename, mime_type, md5_hash, book_id) VALUES 
('mat_uchenya.jpg','image/jpeg','f41e2431ebfe833196524a7c88040387',(SELECT id FROM books WHERE title='Мать ученья')),
('prep_g.jpg','image/jpeg','5024ee558af420feb6934dae7ec1e3cc',(SELECT id FROM books WHERE title='Преподобный Гу')),
('dragon_v.jpg','image/jpeg','9b69e965b9618d6d880ecc71ad660db2',(SELECT id FROM books WHERE title='Дракон Вайнкер')),
('hpmor.jpg','image/jpeg','9bbf53ab5e34f5c60888f52de99ca2b4',(SELECT id FROM books WHERE title='Гарри Поттер и методы рационального мышления')),
('worm.jpg','image/jpeg','2475caaa1463894cc4a41c006e2076fd',(SELECT id FROM books WHERE title='Червь')),
('pact.jpg','image/jpeg','b9f5c9e61a3a29faf559c8a06e239584',(SELECT id FROM books WHERE title='Пакт')),
('a_will_eternal.jpg','image/jpeg','b358fb4a239bef910695091b05b2d502',(SELECT id FROM books WHERE title='Вечная Воля')),
('lord_of_secrets.jpg','image/jpeg','074965b0086c47e10154763f9d78a6c1',(SELECT id FROM books WHERE title='Повелитель тайн')),
('omniscient_reader.jpg','image/jpeg','fa3e10982a09fdd2dde391e266d0770c',(SELECT id FROM books WHERE title='Точка зрения Всеведущего читателя')),
('trashero.jpg','image/jpeg','9ba17a82ecdc89b401c05aa4e57feb50',(SELECT id FROM books WHERE title='Ублюдок FFF-ранга')),
('suicide_hunter.jpg','image/jpeg','87cfd276f4fb28abc6798878a1eec19c',(SELECT id FROM books WHERE title='Охотник-суицидник')),
('shadow_slave.jpg','image/jpeg','c2ddbf03881222a1d97cafa86f559987',(SELECT id FROM books WHERE title='Теневой раб'));

INSERT INTO covers (filename, mime_type, md5_hash, book_id) VALUES 
('ideal_run.jpg','image/jpeg','e8b672167b6aa6a704e1c853ae08234b',(SELECT id FROM books WHERE title='Идеальный забег')),
('zenith_of_magic.jpg','image/jpeg','897adfa947608c26cbf4b0b25cb0968d',(SELECT id FROM books WHERE title='Зенит Колдовства')),
('rezero.jpg','image/jpeg','b7ecb216b7d08c2a4cd33b15762d551d',(SELECT id FROM books WHERE title='Re:Zero. Жизнь с нуля в альтернативном мире')),
('guide_to_evil.jpg','image/jpeg','afed31fe2a12d9dbd52ac2c14fa2b350',(SELECT id FROM books WHERE title='Практическое руководство по злу'));

-- Примеры рецензий (добавлено больше рецензий, разная оценка)
INSERT INTO reviews (book_id, user_id, rating, text, status_id) VALUES
  ((SELECT id FROM books WHERE title='Мать ученья'), (SELECT id FROM users WHERE username='zorian'), 5, 'Его звали Зориан Казински. И он победил.', 2),
  ((SELECT id FROM books WHERE title='Мать ученья'), (SELECT id FROM users WHERE username='noveda'), 5, 'Его звали Зак Новеда. И он победил.', 2),
  ((SELECT id FROM books WHERE title='Мать ученья'), (SELECT id FROM users WHERE username='jornak'), 1, 'Его звали Джорнак Докочин. И он победил.', 2),
  ((SELECT id FROM books WHERE title='Дракон Вайнкер'), (SELECT id FROM users WHERE username='noveda'), 4, 'Колоритный мир и забавные ситуации, но хотелось бы чуть больше логики в механике квестов.', 2),
  ((SELECT id FROM books WHERE title='Гарри Поттер и методы рационального мышления'), (SELECT id FROM users WHERE username='noveda'), 5, 'Глубокая и умная реинтерпретация — много полезных мыслей о рациональности.', 2),
  ((SELECT id FROM books WHERE title='Червь'), (SELECT id FROM users WHERE username='jornak'), 5, 'Мощная, тёмная и детальная история — на любителя, но очень сильная.', 2),
  ((SELECT id FROM books WHERE title='Пакт'), (SELECT id FROM users WHERE username='jornak'), 3, 'Интересная идея, но атмосфера чересчур мрачная; для некоторых читателей это минус.', 2),
  ((SELECT id FROM books WHERE title='Вечная Воля'), (SELECT id FROM users WHERE username='noveda'), 4, 'Комичный герой, но в то же время искренний — хорошо балансирует серьёзность и юмор.', 2),
  ((SELECT id FROM books WHERE title='Точка зрения Всеведущего читателя'), (SELECT id FROM users WHERE username='noveda'), 4, 'Идея о мирe-романе реализована живо; моменты борьбы за сюжет захватывают.', 2);

  -- Рецензии для новых книг
INSERT INTO reviews (book_id, user_id, rating, text, status_id) VALUES
  -- Идеальный забег
  ((SELECT id FROM books WHERE title='Идеальный забег'), (SELECT id FROM users WHERE username='zorian'), 5, 'Фантастическая механика жизни заново, напряжённый сюжет и интересные персонажи.', 2),
  ((SELECT id FROM books WHERE title='Идеальный забег'), (SELECT id FROM users WHERE username='jornak'), 3, 'Хорошо, но слишком похоже на игровую механику; немного теряется сюжет.', 2),

  -- Зенит Колдовства  ((SELECT id FROM books WHERE title='Зенит Колдовства'), (SELECT id FROM users WHERE username='noveda'), 4, 'Сильная культивация, но иногда сюжет предсказуем.'),
  ((SELECT id FROM books WHERE title='Зенит Колдовства'), (SELECT id FROM users WHERE username='jornak'), 3, 'Местами затянуто, но магия и приключения держат интерес.', 2),

  -- Re:Zero
  ((SELECT id FROM books WHERE title='Re:Zero. Жизнь с нуля в альтернативном мире'), (SELECT id FROM users WHERE username='zorian'), 5, 'Смерть и возврат во времени создают невероятное напряжение, герой живёт каждую ошибку.', 2),
   ((SELECT id FROM books WHERE title='Re:Zero. Жизнь с нуля в альтернативном мире'), (SELECT id FROM users WHERE username='jornak'), 4, 'Люблю персонажей и их борьбу, но сюжет местами усложнён лишними деталями.', 2),

  -- Практическое руководство по злу
  ((SELECT id FROM books WHERE title='Практическое руководство по злу'), (SELECT id FROM users WHERE username='zorian'), 5, 'Интересный поворот на стороне злодея, интриги и моральные вопросы на высоте.', 2),
  ((SELECT id FROM books WHERE title='Практическое руководство по злу'), (SELECT id FROM users WHERE username='noveda'), 4, 'Сюжет захватывает, героиня интересная, но хотелось бы больше политических деталей.', 2);















    
-- Дополнительные полезные индексы
CREATE INDEX idx_books_author ON books(author);
CREATE INDEX idx_genres_name ON genres(name);


CREATE INDEX idx_reviews_status_created ON reviews(status_id, created_at);
CREATE INDEX idx_reviews_user ON reviews(user_id);


