# ANALYSIS.md — Investing Demo

Документ фиксирует результаты заданий №1–3 по исходной версии приложения Investing Demo (Python/Django) и по состоянию кода после модернизации в этой копии проекта.

Рабочая ветка на момент начала работы называлась `cursor-agent` (не `cursor-work`). Переключение веток не выполнялось. К моменту завершения отчёта каталог `.git` в текущей копии проекта отсутствует; это отражено в `AGENT_REPORT.md`.

---

## Задание №1. Анализ исходного кода

### 1. Назначение и технологический стек

Investing Demo — учебное веб-приложение для просмотра списка акций, их карточек с графиком котировок, ручного CRUD инструментов и периодического обновления последней цены через Tinkoff Invest API.

Исходный стек:

| Слой | Технологии |
| --- | --- |
| Язык / фреймворк | Python, Django 4.1.7 |
| HTTP API | Django REST Framework 3.14, django-filter |
| Фоновые задачи | Celery 5.2.7, Redis как брокер |
| СУБД | PostgreSQL (`psycopg2-binary`), Docker Compose |
| Рыночные данные | `tinkoff-investments` (клиент `tinkoff.invest.Client`) |
| Графики | Plotly |
| Формы / UI | django-crispy-forms + crispy-bootstrap3, шаблоны Django, локальный Bootstrap CSS (файлы CSS в репозитории отсутствовали) |
| Авторизация | стандартная модель `django.contrib.auth.models.User` |

После модернизации: Django 4.2.16 LTS, DRF 3.15.2, Celery 5.4.0, crispy-bootstrap5, SQLite по умолчанию (PostgreSQL остаётся опцией через `USE_SQLITE=0`).

### 2. Структура проекта

```
config/          — настройки Django, URL корневого проекта, Celery
dashboard/       — акции, шаблоны, API, Celery-задачи, сервисы рынка/графиков
user/            — регистрация, вход, выход
docker-compose.yml
manage.py
requirements.txt
```

Основные пакеты:

- `config.settings` — конфигурация, БД, Celery, токен Tinkoff.
- `dashboard.models.Share` — единственная исходная сущность.
- `dashboard.views` — HTML CRUD и детальная страница.
- `dashboard.api.v1` — REST `ModelViewSet` для `/api/v1/shares/`.
- `dashboard.tasks.update_last_price` — периодическое обновление `last_price`.
- `dashboard.services.market_data` / `graph` — обращения к Tinkoff API.
- `dashboard.management.commands.add_shares` — первичная загрузка инструментов.
- `user.views` / `user.forms` — регистрация и аутентификация.

### 3. Архитектура и взаимодействие

Классический монолит Django:

1. Браузер бьёт в маршруты `config.urls` → `dashboard.urls` или `user.urls`.
2. Список/карточка акций читают модель `Share`.
3. Карточка строит график через Tinkoff (`get_all_candles` за 180 дней) и вставляет HTML Plotly.
4. Авторизованный пользователь может создавать/менять/удалять `Share` через `ModelForm`.
5. REST API дублирует CRUD без проверки прав (AllowAny по умолчанию).
6. Celery Beat планирует `update_last_price`; worker вызывает Tinkoff `get_last_prices` и пишет `last_price` / `is_trend_high`.
7. `add_shares` один раз наполняет таблицу акциями из `client.instruments.shares()`.

После модернизации тот же контур сохранён. Добавлены:

- сохранение снимков цены (`SharePriceHistory`) в той же Celery-задаче;
- виртуальный портфель (`PortfolioPosition`, `PortfolioTransaction`) с HTML-сценариями покупки/продажи;
- график сначала строится из локальной истории, Tinkoff используется как запасной источник.

### 4. Зависимости и внешние системы

Исходный `requirements.txt` фиксировал устаревшие версии (Django 4.1.7, pydantic 1.x, protobuf 3.20, `tinkoff==0.1.1`, `tinkoff-investments==0.2.0b50`).

Внешние системы:

- Tinkoff Invest API (обязателен для загрузки бумаг, live-графика и обновления цены).
- PostgreSQL и Redis (Docker Compose).
- CDN (Plotly, jQuery, Font Awesome и др. в исходном `base.html`).

Токен задавался пустой константой `TINKOFF_TOKEN = ""` в `config/settings.py`.

### 5. Модель данных (исходная)

Сущность **Share**:

| Поле | Смысл |
| --- | --- |
| `figi`, `isin`, `uid` | идентификаторы инструмента |
| `name`, `ticker`, `currency` | отображаемые атрибуты |
| `last_price` | последняя цена (float, nullable) |
| `is_trend_high` | флаг роста относительно предыдущей цены |
| `updated_at` | `auto_now` |

Связей с пользователем не было: акции глобальны для всего приложения.

Пользователь — стандартный `auth.User`. Регистрация пишет `username=email`. Отдельной модели профиля нет (`user/models.py` только импортирует `get_user_model()`).

### 6. Обработка запросов и БД

- HTML: CBV `ListView` / `CreateView` / `UpdateView` / `DeleteView` / самописный `ShareDetailView`.
- API: DRF router, пагинация LimitOffset, фильтры по `name`/`ticker`, поиск по имени.
- ORM: прямые `Share.objects.get/filter/update/get_or_create`.
- Миграции `dashboard/migrations/0001`–`0007` описывают эволюцию `Share`.

---

## Задание №2. Восстановленные функциональные требования

Ниже — поведение, которое **действительно было реализовано** в исходном коде, с указанием подтверждающих мест. Желаемые, но не реализованные возможности (персональный watchlist, портфель, локальная история цен) сюда не входят.

1. **Неавторизованный пользователь видит список акций на главной странице.**  
   `dashboard/views.py` (`ShareListView`), `dashboard/urls.py` (`path("", ... name="index")`), шаблон `dashboard/templates/dashboard/list.html`.

2. **Список пагинируется по 100 записей и сортируется по названию.**  
   `ShareListView.paginate_by = 100`, `ordering = ["name"]`; пагинация в `list.html`.

3. **В таблице отображаются тикер, название, ISIN, текущая цена и валюта.**  
   `list.html`; цена подсвечивается зелёным при `is_trend_high`, иначе красным (в т.ч. когда флаг `None`).

4. **По клику на тикер открывается карточка акции с именем, ценой, временем обновления и графиком.**  
   `ShareDetailView.get`, `dashboard/templates/dashboard/detail.html`, `dashboard/services/graph.py`.

5. **График на карточке строится по дневным свечам Tinkoff за последние 180 дней (поле `close.units`).**  
   `get_graph()` в `dashboard/services/graph.py`.

6. **Кнопки «Добавить», «Редактировать», «Удалить» видны только аутентифицированному пользователю.**  
   `{% if user.is_authenticated %}` в `list.html`.

7. **Создание, изменение и удаление акции доступны только аутентифицированному пользователю; иначе выполняется редирект.**  
   `IsUserAuthenticatedMixin` в `dashboard/views.py` (исходно редирект на `dashboard:index`, не на логин).

8. **Форма инструмента позволяет задать все поля модели `Share`.**  
   `ShareModelForm` с `fields = "__all__"`, шаблон `create.html`.

9. **Удаление требует подтверждения на отдельной странице.**  
   `ShareDeleteView`, `delete.html`.

10. **Пользователь может зарегистрироваться по email и двум полям пароля, после успеха выполняется вход и редирект на главную.**  
    `user/views.py` (`RegistrationView`), `user/forms.py` (`RegistrationForm.save` → `create_user` + `authenticate` + `login`).

11. **Регистрация отклоняется, если пароли не совпадают или email уже есть.**  
    `RegistrationForm.clean`.

12. **Пользователь входит по email и паролю; при ошибке показывается сообщение «Неверный логин или пароль!».**  
    `AuthView.post`, `user/templates/user/auth.html`.

13. **Выход выполняется GET-запросом и возвращает на главную.**  
    `LogoutView`, `user/urls.py` `path("logout/", ...)`.

14. **В шапке отображается email вошедшего пользователя или кнопка «Войти».**  
    `dashboard/templates/dashboard/base.html`.

15. **REST API предоставляет список акций с пагинацией по адресу `/api/v1/shares/`.**  
    `dashboard/api/v1/router.py`, `ShareViewSet`, `REST_FRAMEWORK["PAGE_SIZE"] = 100`. Исходные тесты: `dashboard/tests.py`.

16. **API позволяет получить, создать, полностью обновить и удалить акцию; неполный PUT и создание без обязательных полей дают 400, отсутствующий id — 404.**  
    `ShareViewSet` + `ShareSerializer`; тесты `test_share_*` в `dashboard/tests.py`.

17. **API фильтрует по `name` и `ticker`, сортирует по этим полям, ищет по `name`.**  
    `ShareFilter`, `ordering_fields`, `search_fields` в `dashboard/api/v1/views.py`.

18. **Администратор Django может просматривать и искать акции.**  
    `dashboard/admin.py` (`ShareAdmin`).

19. **Команда `python manage.py add_shares` загружает инструменты из Tinkoff в таблицу `Share`.**  
    `dashboard/management/commands/add_shares.py`.

20. **Фоновая задача обновляет `last_price` и `is_trend_high` по последней цене Tinkoff.**  
    `dashboard/tasks.py`, расписание в `config/celery.py`.

### Сценарии пользователя (как в коде)

1. Открыть `/` → просмотреть таблицу → открыть `/<id>` → увидеть график (нужен токен Tinkoff).
2. `/user/registration/` → регистрация → главная с кнопками CRUD.
3. `/user/login/` — фактически в исходнике маршрут был `path("user", include(...))`, то есть URL получался `/userlogin/` без слэша; это дефект, не требование.
4. Создать/изменить/удалить акцию формами.
5. Вызвать REST `/api/v1/shares/`.
6. Администратор использует `/admin/`.
7. Операции: `add_shares`, Celery worker/beat.

### Бизнес-правила исходной версии

- Тикер и FIGI уникальны.
- CRUD HTML только для аутентифицированных.
- CRUD API **не** требует аутентификации (это реализованное поведение, не «дыра, которую код запрещает»).
- Регистрация сравнивает пароли и проверяет занятость email.
- Тренд: `last_price` (новое) >= старое → рост; сравнение ломалось при `last_price is None` (дефект).
- Цена в графике и `get_last_data` брала только `units`, без `nano` (дефект точности).

### Неоднозначности и дефекты исходной реализации (не требования)

- Пустой `SECRET_KEY` — Django не стартует.
- `ALLOWED_HOSTS = []`.
- В репозитории не было `bootstrap.min.css`, хотя шаблоны на него ссылались.
- `path("user", include("user.urls"))` склеивал `/user` и `login/` в `/userlogin/`.
- Логин делал `email.lower()`, регистрация сохраняла email как есть — вход с другим регистром не работал.
- `RegistrationForm.clean` падал с `KeyError`, если email невалиден; страница регистрации падала на `form.errors["__all__"].data[0].message`.
- `ShareDetailView` вызывал `Share.objects.get` без 404.
- Mixin редиректил на главную, а не на логин.
- Celery-задача называлась «каждые 5 мин», интервал был 10 секунд.
- `get_or_create` в `add_shares` использовал все поля как lookup и мог конфликтовать по unique `figi`.
- API-сериализатор не включает `uid`, хотя поле обязательное и уникальное.
- Нет хранения истории цен: график каждый раз ходит во внешний API.

---

## Задание №3. Аудит, дефекты, модернизация

### Зависимости и совместимость

- Django 4.1.7 — EOL; обновлён до **4.2.16 LTS**.
- Пакет `tinkoff==0.1.1` с PyPI не ставится; SDK `tinkoff-investments` — pre-release. В этой среде `pip` не нашёл дистрибутив (`from versions: none`), индекс T-Bank отверг SSL. Импорт SDK сделан ленивым, чтобы приложение и тесты работали без него.
- Docker в среде отсутствует; PostgreSQL по умолчанию заменён на SQLite (`USE_SQLITE=1`), Postgres остаётся через переменные окружения.
- Bootstrap подключён с CDN (Bootstrap 5.3), crispy переведён на bootstrap5.

### Исправленные проблемы

1. Пустой `SECRET_KEY` / токен / хосты — чтение из окружения и `.env`, безопасный dev-ключ только для локальной работы.
2. Префикс `/user/` в `config/urls.py`.
3. Нормализация email при регистрации и входе.
4. Устойчивая обработка ошибок форм.
5. `get_object_or_404` на карточке акции.
6. `LoginRequiredMixin` вместо самописного mixin.
7. Учёт дробной части котировки (`units + nano/1e9`).
8. Сравнение тренда при `last_price is None`.
9. `get_or_create` по `figi` с `defaults`.
10. Расписание Celery — 300 секунд (5 минут).
11. График не падает без токена/SDK: используется сохранённая история.
12. SQLite для тестов и локального запуска без Docker.

### Рефакторинг

- Вынесены `dashboard/services/quotations.py` и `portfolio.py`.
- Явный импорт `ShareViewSet` в router вместо `import *`.
- Логирование через `logging.getLogger("main")` в задачах.
- Шаблоны упрощены (валидная разметка цены, сообщения Django).

### Проверки запуска

Выполнено в предыдущей итерации на Python 3.11:

- `python manage.py migrate` — миграции 0001–0008 применены.
- `python manage.py check` — без замечаний.
- `python manage.py test` — **26 тестов, OK**.

Повторная проверка запускается в текущей сессии после восстановления пропавших файлов рабочей копии.

Не проверено и почему:

- Живой Tinkoff API — нет токена и не устанавливается SDK.
- PostgreSQL / Redis / Celery worker — нет Docker и брокера.
- Сравнение с веткой Copilot — работа велась только в этой копии.
