# Investing Demo

## Установка (Windows PowerShell, Python 3.11 и Git)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps "tinkoff-investments @ git+https://github.com/Tinkoff/invest-python.git@1cc84950266d62cd0bc7a43ad764dddfd4252630"
```

Tinkoff SDK installs from the pinned commit of its archived official repository.
The old package metadata declares an unavailable `tinkoff` dependency, so `--no-deps`
is required; the SDK runtime dependencies used by this project are in
`requirements.txt`. `pip check` may still report that unavailable SDK metadata
dependency. The SDK import and methods used by the app were smoke-tested separately.

## Configuration and start

SQLite is used by default for local development; PostgreSQL can be selected with
environment variables. Set a private Django secret before deployment. The fallback
secret is only for local development.

```powershell
$env:DJANGO_SECRET_KEY = "replace-with-a-private-random-secret"
$env:TINKOFF_TOKEN = "your-tinkoff-invest-api-token"
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

The market-data update task and API history fallback require a Tinkoff API token and
internet access. The web app can start without the token, but external market-data
requests cannot. `TINKOFF_TOKEN` is read from the environment, not source code.

To use the included PostgreSQL Docker service instead of SQLite:

```powershell
docker-compose -f docker-compose.yml up -d
$env:DB_ENGINE = "django.db.backends.postgresql"
$env:DB_NAME = "investing"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "postgres"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
.\.venv\Scripts\python.exe manage.py migrate
```

Celery periodic updates additionally require a reachable Redis broker. Start Redis,
then run these commands in separate terminals:

```powershell
.\.venv\Scripts\celery.exe -A config beat
.\.venv\Scripts\celery.exe -A config worker -l info -P solo
```

To initially load shares, with the API token configured:

```powershell
.\.venv\Scripts\python.exe manage.py add_shares
```

The share API is available at `/api/v1/shares/`. Authenticated users can use the
personal watchlist and price alerts, virtual portfolios, and strategy simulator.
