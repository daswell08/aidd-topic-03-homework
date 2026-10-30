# Анализ приложения и восстановленные функциональные требования

## Область анализа и результаты проверки

Документ описывает исходные возможности Investing Demo и фактическую реализацию
после работ в ветке `copilot-work`. Выводы привязаны к файлам, классам, функциям
или URL-маршрутам. Реальное подключение к PostgreSQL, Redis и Tinkoff Invest API
не проверено; перечисленные ниже успешные Django-проверки выполнены в Python
3.11.9 на SQLite и не доказывают работу этих внешних сервисов.

## Назначение, структура и взаимодействие компонентов

Investing Demo — Django-приложение с каталогом акций, HTML-интерфейсом, REST API,
получением котировок и свечей через Tinkoff Invest SDK, периодической задачей
Celery, а также пользовательскими инструментами мониторинга и виртуальных
инвестиций.

- [config/settings.py](./config/settings.py): Django, REST Framework, база,
  секрет, разрешённые хосты, Tinkoff token и URL брокера настраиваются окружением.
  По умолчанию для локального запуска используется SQLite.
- [config/urls.py](./config/urls.py): подключает Django admin, приложение
  `dashboard` и пользовательские маршруты под `/user/`.
- [dashboard/models.py](./dashboard/models.py): акции, ценовая история,
  пользовательский watchlist, уведомления, портфели и стратегии.
- [dashboard/views.py](./dashboard/views.py): HTML-каталог и карточка акции,
  персональный список наблюдения, уведомления, операции портфеля и управление
  стратегиями. Персональные представления требуют входа и ограничивают данные
  текущим пользователем.
- [dashboard/api/v1/views.py](./dashboard/api/v1/views.py),
  [dashboard/api/v1/serializer.py](./dashboard/api/v1/serializer.py) и
  [dashboard/api/v1/router.py](./dashboard/api/v1/router.py): REST CRUD, фильтрация,
  сортировка и поиск акций.
- [dashboard/services/market_data.py](./dashboard/services/market_data.py):
  получает последнюю цену из Tinkoff Invest API.
- [dashboard/services/graph.py](./dashboard/services/graph.py): строит график
  сохранённых точек; если таких точек за выбранный период нет, запрашивает свечи
  через API.
- [dashboard/tasks.py](./dashboard/tasks.py) и [config/celery.py](./config/celery.py):
  обновляют котировки по расписанию, сохраняют ценовые снимки и запускают
  обработку уведомлений и стратегий.
- [dashboard/services/market_automation.py](./dashboard/services/market_automation.py):
  обрабатывает условия ценовых уведомлений и симулирует сделки стратегий.
- [dashboard/services/trading.py](./dashboard/services/trading.py): рассчитывает
  позиции, среднюю цену и P/L портфеля, а также не допускает продажу сверх позиции.
- [user/forms.py](./user/forms.py), [user/views.py](./user/views.py) и
  [user/urls.py](./user/urls.py): регистрация, вход и выход стандартных пользователей
  Django.

## Модель данных

- `Share` — инструмент с идентификаторами Tinkoff, тикером, валютой, текущей ценой
  и признаком направления цены. Цена хранится как `DecimalField`.
- `PriceHistory` — снимок цены с временной меткой; ограничение уникальности
  `share`/`recorded_at` препятствует точному дублированию точки.
- `WatchlistItem` — связь пользователя и акции; пара уникальна.
- `PriceAlert` и `PriceAlertNotification` — условие «выше/ниже или равно», состояние
  повторного срабатывания и внутренняя запись-уведомление. Идентичные правила
  пользователя уникальны; уведомление уникально для alert и временной метки.
- `Portfolio` — портфель конкретного пользователя; имя уникально для владельца.
- `PortfolioTransaction` — виртуальная покупка или продажа с количеством, ценой
  и временем; акции защищены от удаления, если уже есть операции.
- `InvestmentStrategy` — владелец, акция, buy/sell-пороги, размер виртуальной
  сделки, открытая позиция, средняя цена входа и накопленный реализованный P/L.
  Ограничение БД требует `sell_above > buy_below`.
- `StrategyTrade` — журнал симулированных сделок с ценой, количеством, временем
  и результатом продажи.

Схему отражают [dashboard/migrations/0001_add_share.py](./dashboard/migrations/0001_add_share.py),
последующие миграции акций, [dashboard/migrations/0008_price_history.py](./dashboard/migrations/0008_price_history.py),
[dashboard/migrations/0009_alter_share_last_price_investmentstrategy_portfolio_and_more.py](./dashboard/migrations/0009_alter_share_last_price_investmentstrategy_portfolio_and_more.py)
и [dashboard/migrations/0010_investmentstrategy_strategy_sell_above_buy.py](./dashboard/migrations/0010_investmentstrategy_strategy_sell_above_buy.py),
[dashboard/migrations/0011_pricealert_unique_user_price_alert.py](./dashboard/migrations/0011_pricealert_unique_user_price_alert.py).

## Восстановленные требования и реализация

| ID | Требование | Подтверждение в коде | Статус |
|---|---|---|---|
| FR-1 | Посетитель просматривает каталог акций, отсортированный по названию, и листает страницы. | `ShareListView` в [dashboard/views.py](./dashboard/views.py), шаблон [list.html](./dashboard/templates/dashboard/list.html). | Реализовано; покрыто тестом списка. |
| FR-2 | Пользователь открывает карточку инструмента, смотрит текущую цену и график динамики за выбранный период. | `ShareDetailView`, `PRICE_HISTORY_PERIODS`, `get_history_graph`, `get_graph`; маршрут `/<int:pk>` и [detail.html](./dashboard/templates/dashboard/detail.html). | Реализовано; при отсутствии сохранённых точек карточка сохраняет график дневных свечей API. |
| FR-3 | Аутентифицированный пользователь выполняет HTML CRUD операций с акциями. | `ShareCreateView`, `ShareUpdateView`, `ShareDeleteView` и `IsUserAuthenticatedMixin` в [dashboard/views.py](./dashboard/views.py); формы в [dashboard/forms.py](./dashboard/forms.py). | Реализовано в коде; тесты этих HTML-операций отсутствуют. |
| FR-4 | Пользователь регистрируется, входит и выходит; некорректные данные возвращают форму с ошибками. | `RegistrationView`, `AuthView`, `LogoutView` в [user/views.py](./user/views.py), формы и шаблоны `user`. | Реализовано; проверено тестами регистрации, case-insensitive email, входа, выхода и обработки пустых/неверных полей. |
| FR-5 | API предоставляет CRUD для акций. | `ShareViewSet` в [dashboard/api/v1/views.py](./dashboard/api/v1/views.py), сериализатор и router. | Реализовано; CRUD API-тесты проходят. Права на запись API публичны — это существующее ограничение. |
| FR-6 | API фильтрует инструменты по названию/тикеру, сортирует по названию/тикеру и ищет по названию. | `ShareFilter`, `filter_backends`, `ordering_fields`, `search_fields` в [dashboard/api/v1/views.py](./dashboard/api/v1/views.py). | Реализовано в коде; отдельного покрытия этих параметров нет. |
| FR-7 | Приложение загружает каталог инструментов из Tinkoff Invest API. | Команда `add_shares` в [dashboard/management/commands/add_shares.py](./dashboard/management/commands/add_shares.py). | Код присутствует; требуется токен и внешнее соединение, реальный запрос не запускался. |
| FR-8 | Задача обновляет текущие цены, индикатор тренда и сохраняет снимки без дублей каждые пять минут. | `update_last_price` в [dashboard/tasks.py](./dashboard/tasks.py), `get_last_data`, `app.conf.beat_schedule` в [config/celery.py](./config/celery.py). | Реализовано; тест подтверждает расписание 300 секунд, повторный запуск и автоматическое уведомление, но внешний API/worker не проверены. |
| FR-9 | Пользователь создаёт персональный список наблюдения, добавляя и удаляя акции. | `WatchlistItem`, `watchlist`, `add_to_watchlist`, `remove_from_watchlist`; маршруты и [watchlist.html](./dashboard/templates/dashboard/watchlist.html). | Реализовано; добавление идемпотентно, удаление ограничено владельцем. |
| FR-10 | Пользователь задаёт порог цены и получает in-app уведомление при достижении условия без повторов на каждом обновлении. | `PriceAlert`, `process_price_alerts`, `PriceAlertNotification`, маршруты `alerts/` и `notifications/`; форма на странице акции. Повторное срабатывание разрешается после выхода цены из условия. | Реализовано; протестированы подавление дублей, повторный trigger после re-arm и интеграция с задачей обновления цены. Email/SMS не реализованы. |
| FR-11 | Пользователь формирует виртуальный портфель, моделирует покупки/продажи, видит среднюю цену, стоимость, P/L и журнал операций. | `Portfolio`, `PortfolioTransaction`, `get_portfolio_positions`, `record_portfolio_transaction`, `portfolio_detail`; [portfolio_detail.html](./dashboard/templates/dashboard/portfolio_detail.html). Продажа сверх имеющейся позиции отвергается. | Реализовано; тесты расчёта средней цены, реализованного/нереализованного P/L, запрета oversell и приватности проходят. |
| FR-12 | Пользователь создаёт стратегию с условиями покупки/продажи, автоматически получает виртуальные сделки в журнале и оценивает результат. | `InvestmentStrategy`, `StrategyTrade`, `process_investment_strategies`, `strategy_list`, `strategy_detail`; страницы strategies. | Реализовано; обработка котировок вызывает сервис стратегий, пороги ограничены, повторные прогоны не создают одинаковые сделки. Тестируется на мокированных котировках, не на реальном Celery/Redis. |
| FR-13 | Система сохраняет рыночные цены, показывает график и считает абсолютное/процентное изменение. | `PriceHistory`, `update_last_price`, `ShareDetailView`, `get_history_graph`, [detail.html](./dashboard/templates/dashboard/detail.html). | Реализовано; история, периоды, проценты, нулевая начальная цена и API fallback покрыты тестами. |
| FR-14 | Администратор управляет данными через Django admin. | `admin.site.urls` в [config/urls.py](./config/urls.py), регистрация моделей в [dashboard/admin.py](./dashboard/admin.py). | Реализовано в коде; отдельный вход администратора не проверялся. |

## Зависимости и запуск

[requirements.txt](./requirements.txt) закрепляет Django 5.2.18, Django REST
Framework 3.18.3, Celery 5.6.3, django-filter, Plotly, PostgreSQL-драйвер и
зависимости SDK. Два старых PyPI-пакета `tinkoff`/`tinkoff-investments` заменены
инструкцией установки официального архивированного SDK из закреплённого Git-коммита
в [README.md](./README.md). Импорт `Client`, `CandleInterval` и `now` прошёл
smoke-проверку. Установка зависимостей завершилась успешно, но `pip check` всё ещё
сообщает об отсутствующем metadata-пакете `tinkoff`, которого нет в доступном
индексе; SDK ставится с `--no-deps`. Код использует необходимые runtime-библиотеки,
включая protobuf, grpcio, cachetools и python-dateutil.

Проверки, фактически выполненные в Python 3.11.9:

- `pip install -r requirements.txt` — успешно.
- Установка закреплённого Tinkoff SDK из README — успешно.
- SDK import smoke — успешно.
- `manage.py check` — успешно, проблем не обнаружено.
- `manage.py makemigrations --check --dry-run` — изменений моделей вне миграций нет.
- `manage.py test` — 37 тестов завершились успешно; тестовый runner применил миграции
  к in-memory SQLite.
- `manage.py migrate --noinput` — все миграции применены к отдельной временной
  SQLite-БД; `manage.py runserver` поднялся и вернул `HTTP 200` на `/`.
- `pip check` — не чистый из-за требования SDK metadata на отсутствующий пакет
  `tinkoff`.

README описывает команды для SQLite по умолчанию и PostgreSQL по настройкам
окружения. Фактический запрос к PostgreSQL и выполнение Celery с Redis не
проверялись; проверка автоматической обработки цены вызывается напрямую в тесте с
mock API-ответом. Реальные котировки, свечи и первоначальная загрузка требуют
Tinkoff token и сетевого доступа. Существующая локальная `db.sqlite3` во время
проверки не изменялась. При отсутствии сохранённой истории страница акции делает
fallback-запрос к API: сам сервер запускается без токена, но такая карточка не
сможет показать fallback-график без Tinkoff credentials.

## Известные проблемы и пробелы

1. `ShareViewSet` не задаёт permission-классы, поэтому CRUD API остаётся доступен
   без входа; это существующее поведение и оно не менялось.
2. `pip check` не может стать полностью чистым для опубликованной metadata SDK:
   установленный из официального git-коммита `tinkoff-investments` объявляет
   зависимость `tinkoff<0.2.0,>=0.1.1`, дистрибутив которой недоступен; README
   указывает обход `--no-deps`.
3. Не проверены реальные PostgreSQL-миграции и блокировки, подключение Redis,
   выполнение Celery Beat/worker, права токена и ответы Tinkoff API.
4. Сравнение двух coding agents не может быть завершено без независимых результатов
   второго агента. Его ветка не исследовалась и не изменялась; ограничения записаны
   в [AGENT_REPORT.md](./AGENT_REPORT.md).
