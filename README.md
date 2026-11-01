# investing

# Локальный запуск без Docker (SQLite по умолчанию)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver

# PostgreSQL (Docker)
# В .env укажите USE_SQLITE=0
docker-compose -f docker-compose.yml up

# Tinkoff Invest API
# TINKOFF_TOKEN указывается в .env или в переменных окружения

# Первоначальная загрузка списка акций
python manage.py add_shares

# Celery Beat
celery -A config beat

# Celery Worker
celery -A config worker -l info

# Celery Worker для Windows (Eventlet)
pip install eventlet cryptography
celery -A config worker -l info -P eventlet

# API
# /api/v1/shares — работа с акциями
