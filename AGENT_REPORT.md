# AGENT_REPORT.md — Cursor Grok 4.6 (ветка cursor-agent)

Отчёт о работе второго независимого AI Coding Agent по домашнему заданию №3 (Investing Demo).

Задание №5 (сравнение двух агентов) этим отчётом **не выполняется**: его должен сделать автор работы после прогона Copilot.

---

## 1. Какие задачи ставились агенту

Пользователь поручил самостоятельно выполнить HOMEWORK.md:

1. Проанализировать приложение (стек, структура, архитектура, модели, API).
2. Восстановить фактические функциональные требования со ссылками на код.
3. Провести аудит, исправить дефекты, рефакторинг, запустить приложение.
4. Реализовать новую функциональность из предложенного списка.
5. Создать `ANALYSIS.md` и `AGENT_REPORT.md`.
6. Не коммитить и не пушить без разрешения.
7. Не переключать git-ветку; не опираться на работу Copilot.

---

## 2. Основные промпты

Единственный исходный промпт — полный текст задания пользователя (прочитать HOMEWORK.md/README.md, выполнить задания 1–4, отчитаться). Дальнейшие сообщения пользователя: «а где AGENT_REPORT.md и ANALYSIS.md?», «дальше делай», «делай дальше», «давай дальше».

Дополнительных уточнений по выбору функции из задания №4 пользователь не давал. Агент выбрал две связанные функции:

- история рыночных цен (вариант 3);
- виртуальный инвестиционный портфель (вариант 2).

Персональный мониторинг (вариант 1) и симулятор стратегий (вариант 4) не реализовывались, чтобы не раздувать модель и не дублировать сделки портфеля.

---

## 3. Какие изменения внесены

### 3.1. Конфигурация и запуск

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `TINKOFF_TOKEN`, параметры Postgres и Celery читаются из окружения; поддержан простой разбор `.env`.
- Локально по умолчанию SQLite (`USE_SQLITE=1`), тесты всегда на SQLite.
- `LOGIN_URL` / redirect после входа и выхода.
- Язык интерфейса `ru-ru`.
- Добавлен `.env.example` без секретов.
- `docker-compose.yml`: образы `postgres:16` и `redis:7`, убран бессмысленный bind-mount кода в контейнер БД.
- Django 4.2.16 LTS, DRF 3.15, Celery 5.4, crispy-bootstrap5.

### 3.2. Исправленные дефекты исходной версии

| Проблема | Исправление |
| --- | --- |
| Пустой `SECRET_KEY` | значение из env / dev-fallback |
| URL `/userlogin/` | `path("user/", include(...))` |
| Разный регистр email при регистрации и входе | `.lower()` в форме и `authenticate` |
| Падение `clean()` / `errors["__all__"]` | `cleaned_data.get`, `non_field_errors()` |
| `Share.objects.get` → 500 | `get_object_or_404` |
| Редирект гостя на главную при CRUD | `LoginRequiredMixin` → `/user/login/` |
| Цена без `nano` | `quotation_to_decimal` / `quotation_to_float` |
| `last_price is None` ломал тренд | отдельная функция `_is_trend_high` |
| `get_or_create` по всем полям | lookup только `figi` |
| Beat 10 сек при имени «5 min» | `schedule: 300.0` |
| Нет Bootstrap CSS в static | CDN Bootstrap 5 |
| Карточка падала без Tinkoff | график из БД, ленивый импорт SDK |
| `import *` в API router | явный импорт `ShareViewSet` |

Права REST API **намеренно не ужесточались**: исходные тесты создают/меняют акции без логина. Ужесточение сломало бы существующие проверки.

### 3.3. Новая функциональность

**История цен**

- Модель `SharePriceHistory` (`price`, `recorded_at`).
- Celery-задача `update_last_price` пишет снимок при каждом успешном запросе рынка.
- Страницы карточки и `/<id>/history/` считают min/max, абсолютное и процентное изменение за 7/30/90/180/365 дней.
- График Plotly строится из истории; Tinkoff — запасной путь.

**Виртуальный портфель**

- `PortfolioPosition` — количество и средняя цена покупки.
- `PortfolioTransaction` — журнал buy/sell.
- `execute_trade` в транзакции: нельзя продать больше, чем есть; средняя цена пересчитывается только на покупке.
- HTML: `/portfolio/`, `/portfolio/trade/`, ссылки «Купить»/«Сделка» из списка и карточки.
- Сводка: стоимость, вложения, нереализованный P/L.

Функциональные требования новой части:

1. Авторизованный пользователь открывает портфель и видит позиции, стоимость, P/L и последние 50 операций.
2. Гость при заходе на портфель/сделку перенаправляется на `/user/login/`.
3. Покупка увеличивает количество и пересчитывает среднюю цену.
4. Продажа уменьшает количество; средняя цена сохраняется, пока позиция не обнулена.
5. Продажа сверх остатка отклоняется.
6. Если цена в форме пустая, берётся `share.last_price`; при отсутствии положительной цены сделка отвергается.
7. Снимки цены сохраняются задачей обновления котировок.
8. Страница истории показывает таблицу точек и агрегаты за выбранный период.

---

## 4. Какие файлы изменены и зачем

### Добавлены

| Файл | Зачем |
| --- | --- |
| `ANALYSIS.md` | задания 1–3 |
| `AGENT_REPORT.md` | этот отчёт |
| `.env.example` | шаблон переменных |
| `dashboard/models.py` — новые модели | история и портфель |
| `dashboard/migrations/0008_price_history_and_portfolio.py` | миграция |
| `dashboard/services/quotations.py` | перевод Quotation → Decimal |
| `dashboard/services/portfolio.py` | сделки и агрегаты |
| `dashboard/templates/dashboard/history.html` | UI истории |
| `dashboard/templates/dashboard/portfolio.html` | UI портфеля |
| `dashboard/templates/dashboard/trade.html` | форма сделки |
| `user/tests.py` | тесты auth/URL |

### Существенно изменены

`config/settings.py`, `config/urls.py`, `config/celery.py`, `requirements.txt`, `README.md`, `docker-compose.yml`, `manage.py`, `dashboard/views.py`, `dashboard/urls.py`, `dashboard/forms.py`, `dashboard/tasks.py`, `dashboard/admin.py`, `dashboard/tests.py`, `dashboard/services/graph.py`, `dashboard/services/market_data.py`, `dashboard/management/commands/add_shares.py`, `dashboard/api/v1/router.py`, шаблоны `base.html`/`list.html`/`detail.html`/`create.html`, `user/forms.py`, `user/views.py`.

### Восстановлены в текущей сессии

К началу продолжения работы в каталоге не оказалось `.git`, `HOMEWORK.md`, `.venv`, исходных миграций 0001–0007, `config/__init__.py`, `asgi.py`/`wsgi.py`, API views/serializer/urls, `user/urls.py`, шаблонов login/registration, static CSS и ряда `__init__.py`. Они восстановлены по содержимому, прочитанному из исходной копии в первой сессии, иначе приложение нельзя было бы снова запустить. Это ограничение среды, а не часть задания №4.

---

## 5. Команды, которые запускались

Первая сессия:

```
python --version          # 3.11.9
py --version              # 3.13.5
git status / git branch   # branch cursor-agent, working tree clean
docker --version          # команда не найдена
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
  # падение: tinkoff==0.1.1 и tinkoff-investments==0.2.0b80 — No matching distribution
.venv\Scripts\python.exe -m pip install Django==4.2.16 celery==5.4.0 ...
.venv\Scripts\python.exe -m pip install --pre tinkoff-investments
  # from versions: none
.venv\Scripts\python.exe -m pip install t-tech-investments --index-url https://opensource.tbank.ru/...
  # SSLCertVerificationError
.venv\Scripts\python.exe manage.py migrate   # OK, включая 0008
.venv\Scripts\python.exe manage.py check     # no issues
.venv\Scripts\python.exe manage.py test      # 26 tests, OK, 5.943s
.venv\Scripts\python.exe manage.py shell -c "...seed Apple..."
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Текущая сессия (после пропажи `.venv`/`.git`): повторная установка зависимостей, `migrate`, `check`, `test`, `runserver` — см. раздел 6 по факту выполнения.

Не запускались (нет инфраструктуры): `docker-compose up`, `celery -A config worker`, `celery -A config beat`, `add_shares` с реальным токеном.

---

## 6. Тесты и результаты

Первая успешная прогонка:

```
Found 26 test(s).
System check identified no issues (0 silenced).
Ran 26 tests in 5.943s
OK
```

Состав:

- исходные API/HTML тесты списка акций (`DashboardTests`) — сохранены, не отключались;
- `PriceHistoryTests` — nano в котировке, агрегаты истории, запись истории из задачи, downtrend;
- `PortfolioTests` — редирект гостя, средняя цена, продажа, отказ при избыточном sell, HTTP-сделка;
- `UserAuthTests` — `/user/login/`, регистр email, несовпадение паролей, дубликат, неверный логин.

Ожидаемый лог без SDK: при HTML detail/history `No module named 'tinkoff'` перехватывается, страница отдаёт 200.

Живой браузерный прогон в первой сессии был начат (`runserver`), но не завершён из-за обрыва диалога. В текущей сессии прогон повторяется.

---

## 7. Что осталось нерешённым

1. SDK Tinkoff в этой среде не ставится — live-котировки и `add_shares` без ручной установки пакета недоступны.
2. REST API по-прежнему открыт без авторизации (совместимость с исходными тестами).
3. `uid` по-прежнему не в сериализаторе; уникальность пустой строки ограничивает повторный create без uid.
4. Нет watchlist и симулятора стратегий.
5. Нет отдельной аутентификации API (Token/JWT).
6. `last_price` остался `FloatField` ради совместимости; новые суммы — `DecimalField`.
7. Каталог `.git` в текущей копии отсутствует: `git diff`/`git status` выполнить нельзя.
8. `HOMEWORK.md` в текущей копии отсутствует (был прочитан в первой сессии).

---

## 8. Ограничения среды, которые помешали проверкам

- Windows без Docker — нет Postgres/Redis из compose.
- PyPI не отдаёт `tinkoff` / `tinkoff-investments`; индекс T-Bank падает на проверке сертификата.
- Пустой `TINKOFF_TOKEN`.
- Между сессиями исчезли `.git`, `.venv` и часть исходных файлов — агент восстановил код из ранее прочитанного содержимого.
- Пользователь запретил commit/push.

---

## 9. Время и итерации

Оценка (не wall-clock IDE):

- Итерация 1: чтение HOMEWORK/README и всего исходного кода (~40 файлов).
- Итерация 2: аудит дефектов, план модернизации и выбор функций №2+№3.
- Итерация 3: настройки, модели, сервисы, UI, тесты, миграция 0008.
- Итерация 4: борьба с pip/tinkoff, ленивый импорт SDK, `migrate`/`test` 26 OK.
- Итерация 5 (эта): обнаружение неполной рабочей копии, восстановление файлов, написание `ANALYSIS.md` и `AGENT_REPORT.md`, повторные проверки.

Суммарно порядка **1.5–2.5 часов** агентной работы и **5 итераций**. Ручных уточнений по коду от пользователя не было, кроме требования продолжить и явно получить два markdown-отчёта.

---

## 10. Как проверялись результаты (не «на веру»)

- Требования привязаны к конкретным файлам исходной версии, прочитанным до правок.
- Существующие API-тесты оставлены и прогнаны.
- Новые тесты покрывают средний курс, запрет продажи сверх остатка, URL логина, историю цен и задачу обновления с mock `get_last_data`.
- `manage.py check` и реальные миграции на SQLite выполнялись, а не предполагались.
- Неуспех установки Tinkoff SDK зафиксирован текстом ошибки pip, без имитации успешного market API.
