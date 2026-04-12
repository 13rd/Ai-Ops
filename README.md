# Server Monitor Backend - Sprint 1

Backend для системы мониторинга серверов. Реализован на FastAPI с использованием PostgreSQL.

## Возможности Sprint 1

- ✅ Аутентификация (JWT tokens)
- ✅ Управление серверами (CRUD)
- ✅ Тестирование SSH подключений
- ✅ Автоматический сбор метрик (CPU, RAM, Disk, Network, Uptime)
- ✅ Сбор информации о Docker контейнерах
- ✅ Статусы серверов (online, offline, degraded)
- ✅ Планировщик для периодического сбора данных
- ✅ REST API для frontend

## Технологический стек

- **FastAPI** - веб-фреймворк
- **SQLAlchemy 2.0** - ORM с async поддержкой
- **PostgreSQL** - база данных
- **Alembic** - миграции БД
- **Paramiko** - SSH подключения
- **JWT** - аутентификация
- **Docker** - контейнеризация

## Быстрый старт

### Вариант 1: Docker Compose (рекомендуется)

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить логи
docker-compose logs -f backend

# API будет доступен на http://localhost:8000
# Документация: http://localhost:8000/docs
```

### Вариант 2: Локальный запуск (SQLite)

#### Требования

- Python 3.10+
- uv (менеджер пакетов)

#### Установка

```bash
# Быстрый старт (использует SQLite)
./run_local.sh

# Или вручную:
uv sync
uv run alembic upgrade head
uv run python scripts/seed_db.py
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

По умолчанию используется SQLite. Для PostgreSQL измените `DATABASE_URL` в `.env`.

## API Endpoints

### Аутентификация

- `POST /api/v1/auth/login` - Вход в систему
- `GET /api/v1/auth/me` - Получить текущего пользователя

### Серверы

- `POST /api/v1/servers` - Создать сервер (admin)
- `GET /api/v1/servers` - Список серверов
- `GET /api/v1/servers/{id}` - Детали сервера
- `PUT /api/v1/servers/{id}` - Обновить сервер (admin)
- `DELETE /api/v1/servers/{id}` - Удалить сервер (admin)

### Подключения

- `POST /api/v1/connections/test/{server_id}` - Тест подключения

### Метрики

- `GET /api/v1/servers/{id}/metrics/latest` - Последние метрики
- `GET /api/v1/servers/{id}/metrics/history` - История метрик
- `GET /api/v1/servers/{id}/containers` - Список контейнеров

## Тестовые пользователи

После выполнения seed скрипта доступны:

**Admin:**
- Username: `admin`
- Password: `admin123`

**Operator:**
- Username: `operator`
- Password: `operator123`

## Структура проекта

```
app/
├── api/v1/
│   ├── endpoints/      # API endpoints
│   └── api.py          # Router aggregation
├── core/
│   ├── config.py       # Настройки
│   ├── deps.py         # Dependencies
│   └── security.py     # JWT и хеширование
├── db/
│   └── base.py         # Database setup
├── models/             # SQLAlchemy модели
├── schemas/            # Pydantic схемы
├── services/
│   ├── auth/           # Аутентификация
│   ├── servers/        # Управление серверами
│   ├── collectors/     # Сбор метрик и контейнеров
│   └── scheduler/      # Планировщик
└── main.py             # Точка входа
```

## Конфигурация

Основные настройки в `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/server_monitor

# Security
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# SSH
SSH_TIMEOUT=10
SSH_CONNECTION_RETRIES=3

# Metrics
METRICS_COLLECTION_INTERVAL=60  # секунды
```

## Архитектурные решения

### Модульность

Код разделен на четкие модули:
- `auth` - аутентификация
- `servers` - управление серверами
- `collectors` - сбор данных
- `scheduler` - планирование задач

### Абстракция подключений

`SSHConnectionService` абстрагирует логику подключения, что позволит легко добавить другие типы подключений (агенты, API) в будущем.

### Разделение concerns

- Controllers (endpoints) - только HTTP логика
- Services - бизнес-логика
- Models - данные
- Schemas - валидация и сериализация

### TODO для следующих спринтов

- [ ] Vault интеграция для хранения credentials
- [ ] Time-series оптимизация для метрик
- [ ] Более гранулярный RBAC
- [ ] WebSocket для real-time обновлений
- [ ] Уведомления (email, Slack, etc.)
- [ ] AI/anomaly detection
- [ ] Веб-консоль для серверов

## Разработка

### Создание миграции

```bash
uv run alembic revision --autogenerate -m "Description"
```

### Применение миграций

```bash
uv run alembic upgrade head
```

### Откат миграции

```bash
uv run alembic downgrade -1
```

### Линтинг

```bash
uv run ruff check .
uv run ruff format .
```

## Troubleshooting

### База данных не подключается

Проверьте что PostgreSQL запущен и доступен:
```bash
psql -U postgres -h localhost
```

### Ошибки SSH подключения

- Проверьте что SSH сервер доступен
- Проверьте credentials
- Проверьте firewall правила

### Scheduler не собирает метрики

- Проверьте логи: `docker-compose logs -f backend`
- Проверьте что серверы добавлены в систему
- Проверьте `METRICS_COLLECTION_INTERVAL` в настройках

## Лицензия

MIT

## Контакты

Для вопросов и предложений создавайте issues в репозитории.
