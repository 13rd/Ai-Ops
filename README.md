# Server Monitor

Система мониторинга серверной инфраструктуры с обнаружением аномалий гибридными
нейросетевыми моделями и генерацией рекомендаций по устранению через LLM.

Собирает метрики по SSH, определяет тип аномалии (LSTM-автоэнкодер + CNN-LSTM
классификатор), объясняет решение через SHAP, формирует диагностическую команду
через локальную LLM (Ollama) и доставляет уведомления в интерфейс и Telegram.

---

## Содержание

- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Стек технологий](#стек-технологий)
- [Быстрый старт](#быстрый-старт)
- [Полный запуск через Docker](#полный-запуск-через-docker)
- [Демо-стенд](#демо-стенд)
- [Структура проекта](#структура-проекта)
- [API](#api)
- [Подсистема обнаружения аномалий](#подсистема-обнаружения-аномалий)
- [LLM-рекомендации и фильтрация команд](#llm-рекомендации-и-фильтрация-команд)
- [Генерация обучающих данных](#генерация-обучающих-данных)
- [Фронтенд](#фронтенд)
- [Безопасность и RBAC](#безопасность-и-rbac)
- [Схема базы данных](#схема-базы-данных)
- [Конфигурация](#конфигурация)
- [Тесты и линтеры](#тесты-и-линтеры)
- [Известные ограничения](#известные-ограничения)

---

## Возможности

### Мониторинг

- **Сбор метрик по SSH** каждые 15 секунд: CPU, load average 1/5/15 мин, память
  (включая swap), диск, сетевой трафик, дисковый I/O, процессы, активные
  соединения, uptime, доля запущенных контейнеров.
- **Сбор состояния Docker-контейнеров**: статус, CPU, память, рестарты,
  health-check, порты, образ.
- **Статусы серверов**: `online` / `degraded` / `offline` с автоматическим
  пересчётом по результатам последнего цикла сбора.
- **Исторические агрегаты** поминутно: `min` / `max` / `avg` / `last` + счётчик
  сэмплов, для 8 типов метрик.
- **Пороговые алерты** с анти-дубликацией: CPU > 80 %, RAM > 85 %, диск > 90 %,
  load 1m > 4, контейнер упал, сервер не виден > 5 минут.

### Обнаружение аномалий

- **LSTM-автоэнкодер** (`60 × 10`) — детектор: аномалия-скор = MSE реконструкции.
- **CNN-LSTM классификатор** — определение типа из 7 классов.
- **Per-server StandardScaler** и **per-feature пороги** вместо одного
  глобального порога — устойчивость к разным профилям нагрузки.
- **Автоматическая калибровка** скалера и порогов на «чистых» окнах
  (180 сэмплов, CPU/RAM/диск < 90 %) с уведомлением «ML detection ready».
- **Корроборация сырыми метриками** — подавление ложных срабатываний.
- **Дедупликация и автозакрытие** аномалий с grace-периодом.
- **Rule-based fallback** (пороги 90/95 %), если модели или скалеры не обучены.

### Рекомендации

- Генерация диагностической команды через **локальную LLM (Ollama)**.
- **Двухуровневая фильтрация безопасности**: deny-list опасных паттернов +
  allow-list бинарников; при отказе — детерминированный шаблон.
- Workflow одобрения: `pending → approved / rejected`, копирование команды в
  буфер и переход в консоль сервера.

### Управление

- **SSH-консоль в браузере** (xterm.js + WebSocket), режим `read-only` для
  операторов без прав записи.
- **Управление контейнерами**: start / stop / restart / remove / логи
  (REST-снимок и WebSocket-стрим с режимом «следить»).
- **RBAC**: 2 роли (`admin`, `operator`) + пораздача доступа к серверам с
  гранулярностью `read` / `write`.
- **Журнал аудита** из 19 типов действий с IP, user-agent и экспортом в CSV.
- **Уведомления**: in-app (Redis Pub/Sub) + Telegram.

---

## Архитектура

```
                    ┌──────────────┐
                    │   React SPA  │  Vite + MUI + TanStack Query
                    └──────┬───────┘
             REST /api/v1  │  WS /ws
                    ┌──────▼───────┐
                    │    nginx     │  :80/:443, SPA + proxy
                    └──────┬───────┘
                    ┌──────▼────────────────────────────────┐
                    │            FastAPI backend             │
                    │  ┌──────────────────────────────────┐  │
                    │  │ auth / RBAC / audit / secrets     │  │
                    │  ├──────────────────────────────────┤  │
                    │  │ CollectorScheduler   (15 c)       │  │
                    │  │   SSH → metrics + containers      │  │
                    │  ├──────────────────────────────────┤  │
                    │  │ AlertEngine          (в цикле)   │  │
                    │  ├──────────────────────────────────┤  │
                    │  │ MLAnalysisJob        (60 c)       │  │
                    │  │   AE → threshold → CNN-LSTM      │  │
                    │  │   → SHAP → Ollama → notify       │  │
                    │  ├──────────────────────────────────┤  │
                    │  │ WebSocket: консоль + логи         │  │
                    │  └──────────────────────────────────┘  │
                    └───┬──────────┬──────────┬─────────┬──┘
                        │          │          │         │
                 ┌──────▼───┐ ┌────▼────┐ ┌───▼────┐ ┌──▼────────┐
                 │PostgreSQL│ │  Redis  │ │ Ollama │ │ SSH-цели  │
                 │   :5432  │ │  :6379  │ │ :11434 │ │ (Paramiko)│
                 └──────────┘ └─────────┘ └────────┘ └───────────┘
                                        │
                                 ┌──────▼──────────┐
                                 │ stress-target   │
                                 │ + net-peer      │
                                 └─────────────────┘
```

Поток данных: SSH-коллектор → `metric_snapshots` → окно 60 точек (15 минут) →
нормализация per-server скалером → LSTM-AE (скор) → per-feature порог →
CNN-LSTM (тип) или эвристика по реконструкции → SHAP (вклад признаков) →
Ollama (команда) → фильтр безопасности → `anomalies` + `recommendations` +
уведомления.

---

## Стек технологий

### Backend

| Компонент | Технология |
|---|---|
| Язык | Python 3.11 (`uv`, lock-файл `uv.lock`) |
| Web | FastAPI + Uvicorn, async |
| ORM | SQLAlchemy 2.0 (async) |
| БД | PostgreSQL 15 (asyncpg), SQLite для dev |
| Миграции | Alembic (10 ревизий) |
| Auth | JWT (python-jose, HS256) + bcrypt (passlib), refresh в HttpOnly-cookie |
| SSH | Paramiko 3 |
| Шифрование | cryptography.fernet |
| Очереди/кэш | Redis (Pub/Sub для уведомлений), asyncio-планировщики |
| Уведомления | httpx → Telegram Bot API |
| ML | TensorFlow 2.16, scikit-learn, SHAP, Ollama |
| Линтинг | Ruff (line-length 100, `E,F,I,N,W`) |

### Frontend

| Компонент | Версия |
|---|---|
| React | 19.2 |
| Vite | 8.0 |
| TypeScript | 6.0 (strict) |
| Material UI | 9.0 + Emotion |
| TanStack Query | 5.100 |
| React Router | 7.15 |
| Recharts | 3.8 |
| xterm.js | 6.0 |
| react-hook-form + zod | 7.76 / 4.4 |
| notistack, dayjs, axios | 3.0 / 1.11 / 1.16 |

### Инфраструктура

PostgreSQL 15, Redis 7, nginx (SPA + reverse proxy), Ollama, Docker Compose.

---

## Быстрый старт

### Локальный запуск (SQLite)

Требования: Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
# 1. Зависимости
uv sync

# 2. Конфигурация
cp .env.example .env
# SECRET_KEY и SSH_ENCRYPTION_KEY обязательно заменить (см. раздел Конфигурация)

# 3. Схема БД + демо-данные
uv run alembic upgrade head
uv run python scripts/seed_db.py

# 4. Запуск
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Или одной командой: `./run_local.sh`.

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health-check: http://localhost:8000/health

По умолчанию используется SQLite (`sqlite+aiosqlite:///./server_monitor.db`).
Для PostgreSQL укажите `DATABASE_URL` в `.env`.

### Фронтенд

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

Прокси Vite настроен на `:8000` для `/api` и `/ws` (CORS на backend также разрешён).

### Тестовые пользователи

`scripts/seed_db.py` (идемпотентен, выполняется автоматически при старте
контейнера backend):

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin123` | admin |
| `operator` | `operator123` | operator |

> Демо-пароли предназначены только для локальной разработки.

---

## Полный запуск через Docker

```bash
cp .env.example .env      # задать SECRET_KEY, SSH_ENCRYPTION_KEY, пароль БД

docker compose up -d
docker compose logs -f backend
```

Поднимаются сервисы:

| Сервис | Порт | Назначение |
|---|---|---|
| `postgres` | 5432 | Основная БД |
| `redis` | 6379 | Pub/Sub уведомлений |
| `backend` | 8000 | FastAPI (миграции + seed выполняются при старте) |
| `nginx` | 80 | SPA + reverse proxy |
| `ollama` | 11434 | Локальная LLM |
| `ollama-init` | — | `ollama pull qwen2.5:3b` при первом запуске |
| `stress-target` | 127.0.0.1:2224 | SSH-цель для демо |
| `net-peer` | — | iperf3-пир для сценария `network_storm` |

Backend монтирует `/var/run/docker.sock` и запускает
`alembic upgrade head && python scripts/seed_db.py && uvicorn ... --workers 2`.

Остановить: `docker compose down`.

### Команды Makefile

```bash
make help            # список целей
make install         # uv sync
make migrate         # alembic upgrade head
make seed            # scripts/seed_db.py
make run             # uvicorn --reload
make docker-up       # docker compose up -d
make docker-down     # docker compose down
make test            # pytest
make clean           # очистка __pycache__ / .pyc
```

---

## Демо-стенд

Полный сценарий «инъекция аномалии на реальном сервере → детекция ML → рекомендация».

```bash
# 1. Поднять стек с demo-оверлеем (DEMO_MODE=true, ML-инференс каждые 30 с)
make demo-up

# 2. Зарегистрировать SSH-цель (stress-target) в БД
make demo-bootstrap

# 3. Посеять историю аномалий для страницы /anomalies
make demo-seed SERVER=stress-target

# 4. Инъекция аномалии (SSH-команда на целевом сервере)
make demo-trigger TYPE=cpu_spike SERVER_ID=1
#   TYPE ∈ cpu_spike | memory_leak | disk_fill | network_storm |
#         service_down | container_crash

# 5. Дождаться накопления окна (60 × 15 с = 15 мин) либо форсировать прогон
sleep 35
make demo-run-ml SERVER_ID=1

# 6. Остановить инъекцию
make demo-stop SERVER_ID=1

# 7. Статус окружения / остановка
make demo-status
make demo-down
```

Для `demo-status`, `demo-trigger`, `demo-stop`, `demo-run-ml` нужен access-токен:

```bash
curl -sX POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])" \
  > /tmp/demo_token
```

При `DEMO_MODE=true` в UI появляется пункт меню **Demo Panel**
(включается переменной `VITE_DEMO_MODE=true` в `frontend/.env`).

### Автономный стенд (без основной системы)

```bash
make target-up
docker exec server-monitor-stress-target /usr/local/bin/demo_anomaly.sh cpu 120
docker exec server-monitor-stress-target /usr/local/bin/demo_anomaly.sh mem 120
docker exec server-monitor-stress-target /usr/local/bin/demo_anomaly.sh net 120
docker exec server-monitor-stress-target /usr/local/bin/demo_anomaly.sh disk 120
make target-down
```

Подключить локальный backend к этому стенду:
`STRESS_TARGET_HOST=127.0.0.1 STRESS_TARGET_PORT=2224 uv run python scripts/bootstrap_stress_target.py`
(логин `demo` / пароль `demopass`).

### Полностью синтетический сценарий (без SSH)

```bash
uv run python scripts/bootstrap_demo.py                # admin + сервер demo-1 + 60 снапшотов + калибровка
uv run uvicorn app.main:app --reload                  # в отдельном терминале
uv run python data_gen/scripts/run_live_simulator.py --server demo-1
```

Серверы с `ssh_username = "sim"` помечаются синтетическими: SSH-инжекция для них
заблокирована, но ML-конвейер работает полностью.

Подробный сценарий демонстрации — `docs/DEMO_PLAYBOOK.md`.

---

## Структура проекта

```
.
├── app/                          # Backend (FastAPI)
│   ├── api/v1/
│   │   ├── endpoints/            # REST: auth, users, servers, connections,
│   │   │                         #   metrics, containers, alerts, anomalies,
│   │   │                         #   recommendations, notifications, console,
│   │   │                         #   audit, llm_settings, demo
│   │   ├── websocket/            # консоль + стрим логов контейнеров
│   │   └── api.py                # агрегация роутеров
│   ├── core/                     # config, deps (RBAC), security (JWT),
│   │                             #   secrets (Fernet), responses, exceptions
│   ├── db/                       # async engine, session factory, base
│   ├── models/                   # 17 SQLAlchemy моделей
│   ├── schemas/                  # Pydantic-схемы запросов/ответов
│   ├── services/
│   │   ├── auth/  users/         # аутентификация, пользователи
│   │   ├── servers/              # CRUD серверов, SSH-подключения
│   │   ├── collectors/           # SSH-сбор метрик и контейнеров
│   │   ├── metrics/              # снапшоты, исторические агрегаты
│   │   ├── containers/           # управление контейнерами
│   │   ├── alerts/               # правила и движок пороговых алертов
│   │   ├── anomalies/            # (в ml/pipeline.py)
│   │   ├── ml/                   # pipeline, detector, classifier,
│   │   │                         #   explainer, recommender, registry,
│   │   │                         #   scaler_calibration, llm_settings
│   │   ├── notifications/        # dispatcher, inapp, telegram
│   │   ├── console/              # REST-сессии консоли
│   │   ├── audit/                # журнал аудита
│   │   ├── cache/                # Redis-клиент (no-op при недоступности)
│   │   └── scheduler/            # CollectorScheduler, MLAnalysisJob
│   └── main.py                   # lifespan, middleware, обработчики ошибок
│
├── ml/                           # Офлайн-обучение (вне FastAPI)
│   ├── config.py                 # CLASSES, FEATURE_COLS, WINDOW_SIZE
│   ├── features.py               # extract_features(): скорости + log1p
│   ├── windows.py                # build_windows(), разметка по хвосту
│   ├── registry.py               # ModelRegistry: загрузка артефактов
│   ├── calibration.py            # CLI-калибровка скалера по БД
│   ├── models/
│   │   ├── lstm_autoencoder.py
│   │   └── cnn_lstm_classifier.py
│   └── train/
│       ├── prepare_dataset.py
│       ├── train_lstm_ae.py
│       ├── calibrate_threshold.py
│       ├── train_classifier.py
│       └── evaluate.py
│
├── data_gen/                     # Генерация и сбор данных
│   ├── generators/               # SSH-сценарии: normal, cpu_spike,
│   │                             #   memory_leak, container_crash, service_down
│   ├── collectors/               # SSH-коллектор (свой, для data_gen)
│   ├── scripts/                  # CLI: generate_*, export_dataset,
│   │                             #   inject_anomalies, run_collector,
│   │                             #   run_scenario, register_server,
│   │                             #   run_live_simulator
│   ├── simulator/                # Симулятор (API-режим + standalone JSONL),
│   │                             #   9 конфигов, движок аномалий
│   ├── scheduler/                # Ротация сценариев
│   ├── testbeds/                 # docker-compose стенды, Terraform/Proxmox
│   ├── trainbed/                 # 6 профилей → отдельная PG-БД «trainbed»
│   └── export/                   # CSV-экспорт (rows / windows)
│
├── models/                       # Артефакты моделей (в репозитории)
│   ├── lstm_ae.keras
│   ├── classifier.keras
│   ├── threshold.json
│   ├── background.npy            # SHAP-фон (100 × 60 × 10)
│   ├── eval_report.json
│   └── scalers/                  # per-server StandardScaler + пороги
│
├── scripts/                      # seed_db, bootstrap_demo, bootstrap_stress_target,
│                                 #   demo_seed_target, import_labeled_jsonl,
│                                 #   encrypt_existing_secrets,
│                                 #   resolve_open_anomalies, test_recommender,
│                                 #   setup_target_server, demo_anomaly.sh
│
├── frontend/                     # React SPA (см. раздел Фронтенд)
├── tests/                        # pytest: tests/ml (20), tests/integration (2)
├── alembic/versions/             # 10 миграций
├── docs/                         # Проектная документация (00–07, playbook,
│                                 #   SRS IEEE 830, ТЗ ГОСТ 34)
├── docker-compose.yml            # Основной стек
├── docker-compose.demo.yml       # Оверлей DEMO_MODE
├── docker-compose.target.yml     # Автономный стенд
├── Makefile
└── pyproject.toml / uv.lock
```

---

## API

Базовый префикс — `/api/v1`. Единый формат ответа для всех хендлеров:

```json
{ "success": true, "data": {...}, "message": "OK", "error": null }
{ "success": false, "data": null, "message": "Server not found", "error": "server_not_found" }
```

Авторизация — `Authorization: Bearer <access_token>`. Списки поддерживают
`offset` / `limit` и возвращают метаданные пагинации.

### Аутентификация — `/auth`

| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| POST | `/auth/login` | публичный | Вход, возвращает `access_token` + refresh-cookie |
| POST | `/auth/refresh` | cookie | Ротация пары токенов |
| POST | `/auth/logout` | авторизован | Отзыв refresh-токена, очистка cookie |
| GET | `/auth/me` | авторизован | Текущий пользователь |

### Пользователи — `/users` (admin)

`GET /users` · `POST /users` · `GET /users/{id}` · `PUT /users/{id}` ·
`DELETE /users/{id}` · `GET /users/me/servers` ·
`GET /users/{id}/servers` · `PUT /users/{id}/servers` (выдача `read`/`write`)

### Серверы — `/servers`

| Метод | Путь | Доступ |
|---|---|---|
| POST | `/servers` | admin |
| GET | `/servers` | все (+ фильтр по доступу) |
| GET | `/servers/{id}` | read |
| PUT | `/servers/{id}` | admin |
| DELETE | `/servers/{id}` | admin |
| GET | `/servers/{id}/my-access` | авторизован |
| POST | `/connections/test/{server_id}` | read |

### Метрики

| Метод | Путь |
|---|---|
| GET | `/servers/{id}/metrics/latest` · `/metrics/{id}/latest` |
| GET | `/servers/{id}/metrics/history?hours=&aggregation=` · `/metrics/{id}/history` |
| GET | `/servers/{id}/metrics/historical/{metric_type}` · `/metrics/{id}/historical/{type}` |
| GET | `/servers/{id}/metrics/available-aggregations` · `/metrics/{id}/available-aggregations` |
| GET | `/servers/{id}/containers` · `/containers/{id}` |

`metric_type` ∈ `cpu_percent`, `memory_percent`, `disk_percent`,
`load_average_1m`, `network_in`, `network_out`, `disk_read`, `disk_write`.
`aggregation` ∈ `minute`, `hour`, `day`.

### Алерты — `/alerts`

`GET /alerts?status=&severity=&server_id=` · `GET /alerts/count` ·
`GET /alerts/{id}` · `POST /alerts/{id}/acknowledge` · `POST /alerts/{id}/resolve`

### Аномалии и рекомендации

| Метод | Путь | Доступ |
|---|---|---|
| GET | `/anomalies?server_id=&type=&severity=&status=&date_from=&date_to=` | read |
| GET | `/anomalies/{id}` | read |
| PATCH | `/anomalies/{id}/status` (`open`/`investigating`/`resolved`) | read |
| GET | `/servers/{id}/anomalies` | read |
| GET | `/anomalies/{id}/recommendations` | read |
| POST | `/recommendations/{id}/approve` | read |
| POST | `/recommendations/{id}/reject` | read |

Ответ аномалии содержит `reconstruction_error`, `threshold`,
`metrics_snapshot` (снимок на момент обнаружения) и `shap_explanation` —
массив `{metric, impact_percent, ae_contribution, shap_contribution}`.

### Контейнеры — write-доступ обязателен

| Метод | Путь |
|---|---|
| POST | `/servers/{sid}/containers/{cid}/start` |
| POST | `/servers/{sid}/containers/{cid}/stop` |
| POST | `/servers/{sid}/containers/{cid}/restart` |
| DELETE | `/servers/{sid}/containers/{cid}?force=` |
| GET | `/servers/{sid}/containers/{cid}` |
| GET | `/servers/{sid}/containers/{cid}/logs?tail=&timestamps=` |

### Уведомления — `/notifications`

`GET /notifications?is_read=` · `POST /notifications/{id}/read` ·
`GET /notifications/channels` · `POST /notifications/channels` (upsert) ·
`PATCH /notifications/channels/{id}` · `DELETE /notifications/channels/{id}`

Каналы: `inapp`, `telegram` (в `config` — `{"chat_id": "..."}`).

### Аудит и настройки LLM

| Метод | Путь | Доступ |
|---|---|---|
| GET | `/audit-log?user_id=&action=&resource_type=&date_from=&date_to=` | admin |
| GET | `/llm-settings` | admin |
| PUT | `/llm-settings` | admin |

`/llm-settings` — синглтон: `enabled`, `model`, `timeout_sec`, `keep_alive`,
`prompt_template`. Пустые поля откатываются на env-значения.

### Консоль (REST) — `/console`

`POST /console/start-session/{server_id}` · `GET /console/session-info/{token}` ·
`POST /console/terminate-session/{token}`

### WebSocket

| Путь | Назначение |
|---|---|
| `WS /ws/servers/{server_id}/console?token=` | Интерактивная SSH-консоль |
| `WS /ws/servers/{server_id}/containers/{container_id}/logs?token=&tail=` | Стрим `docker logs --follow` |

Протокол консоли: клиент шлёт `{type:"input"|"resize", ...}`, сервер —
`ready` / `output` / `error` / `closed`. Коды закрытия: `4401` (токен),
`4403` (нет доступа), `4404` (сервер не найден), `4500` (ошибка SSH/PTY).

### Демо (при `DEMO_MODE=true`) — `/demo`

`POST /demo/trigger/{anomaly_type}?server_id=` · `POST /demo/stop?server_id=` ·
`POST /demo/run-ml?server_id=` · `GET /demo/status`

### Служебные

`GET /health` → `{"status":"healthy","app":...,"version":...}`
`GET /docs` · `GET /openapi.json`

---

## Подсистема обнаружения аномалий

### Признаки (10)

`cpu_percent`, `load_avg_1m`, `mem_percent`, `swap_used_mb`, `disk_percent`,
`disk_read_bps`, `disk_write_bps`, `net_in_bps`, `net_out_bps`,
`containers_running_ratio`.

Четыре скоростных признака считаются как `diff(счётчик) / Δt` с реальных
таймстемпов и с `log1p`. Окно — **60 точек × 15 с = 15 минут**.

### Модели

**LSTM-автоэнкодер** (`ml/models/lstm_autoencoder.py`) — вход `(60, 10)`:

```
LSTM(32) → LSTM(16) → RepeatVector(60) → LSTM(16) → LSTM(32) → TimeDistributed(Dense(10))
```

Обучается только на окнах с меткой `normal`. Аномалия-скор = MSE реконструкции.

**CNN-LSTM классификатор** (`ml/models/cnn_lstm_classifier.py`) — 7 классов
(`normal`, `cpu_spike`, `memory_leak`, `disk_fill`, `network_storm`,
`container_crash`, `service_down`):

```
Conv1D(32, k=5) → MaxPool → Conv1D(64, k=3) → MaxPool → LSTM(32) → Dropout
→ Dense(32) → Dropout → Dense(7, softmax)
```

### Конвейер инференса

1. **Прогрев моделей** при старте приложения (`ml_warmup()`), синглтон-реестр.
2. Если моделей или per-server скалера нет / сэмплов < 60 → **rule-based**
   (пороги 90 %, critical 95 %).
3. Нормализация per-server `StandardScaler` (`models/scalers/{server}.pkl`).
4. Скор = MSE реконструкции AE.
5. **Per-feature пороги** (`{server}_threshold.json`): если нормированная ошибка
   по всем признакам ≤ 1.0 и общий скор ≤ глобального порога — аномалии нет.
   Иначе `z = max_excess - 1`.
6. **Severity** из z: `<1` low, `<2` medium, `<3` high, `≥3` critical.
7. **Классификация типа**: CNN-LSTM; если сработал per-feature триггер или
   классификатор вернул `normal` — эвристика по вкладу реконструкции.
8. **Корроборация** сырыми метриками: для `cpu_spike` / `memory_leak` /
   `disk_fill` соответствующее поле последнего снапшота должно быть ≥
   `ML_CORROBORATION_MIN_PERCENT` (80 %). Иначе аномалия подавляется.
9. **SHAP-объяснение**: `0.2 × вклад_AE + 0.8 × вклад_SHAP` по последним 20
   шагам, топ-признаки с `impact_percent`.
10. **Дедупликация**: тип пропускается, если аномалия того же типа `open` или
    закрыта менее `ML_ANOMALY_DEDUP_GRACE_MIN` (5 мин) назад.
11. **Автозакрытие**: при отсутствии аномалии все `open` → `resolved`;
    аномалии старше `ML_ANOMALY_MAX_OPEN_MIN` (30 мин) → `resolved`.
12. **Сохранение**: `anomalies` + `recommendations`, рассылка уведомлений.

### Обучение

```bash
# 1. Датасет из БД → npz (сплит per-server 60/20/20, скалер на train-normal)
uv run python -m ml.train.prepare_dataset --out data/processed \
    [--holdout-servers anomaly-testbed-1]

# 2. LSTM-автоэнкодер
uv run python -m ml.train.train_lstm_ae \
    --data data/processed/dataset.npz --out models/lstm_ae.keras \
    --epochs 100 --batch 64

# 3. Порог + SHAP-фон
uv run python -m ml.train.calibrate_threshold \
    --model models/lstm_ae.keras --data data/processed/dataset.npz \
    --out models/threshold.json --background-size 100

# 4. CNN-LSTM классификатор
uv run python -m ml.train.train_classifier \
    --data data/processed/dataset.npz --out models/classifier.keras \
    --epochs 150 --batch 32

# 5. Метрики
uv run python -m ml.train.evaluate \
    --models models --data data/processed/dataset.npz --out models/eval_report.json

# 6. Per-server калибровка скайлера по БД
uv run python -m ml.calibration <server_name> --min-rows 60
```

Артефакты: `models/lstm_ae.keras`, `models/classifier.keras`,
`models/threshold.json`, `models/background.npy`,
`models/scalers/{server}.pkl`, `models/scalers/{server}_threshold.json`.

Метрики из `models/eval_report.json` (2823 тестовых окна):

| Метрика | Значение |
|---|---|
| `classifier_macro_f1` | 0.994 |
| `classifier_normal_accuracy` | 0.998 |
| `ae_recall` | 0.777 |
| `ae_precision` | 0.509 |

Автокалибровка выполняется в рантайме: после 180 «чистых» сэмплов
(CPU/RAM/диск < 90 %) скалер обучается, порог считается как
`max(mean + 3·std, глобальный порог)`, отправляется уведомление
«ML detection ready».

Документация: `docs/05_ML_MODELS.md`, `docs/ml_training_guide.md`,
`docs/ml_retraining_plan.md`.

---

## LLM-рекомендации и фильтрация команд

Транспорт — локальный **Ollama** (`POST {OLLAMA_BASE_URL}/api/generate`),
модель по умолчанию `qwen2.5:3b`, `keep_alive=30m`, timeout 60 с.
Параметры переопределяются через `/llm-settings` (таблица `llm_settings`).

Промпт формируется в `MLPipeline._build_prompt_context()` и содержит тип
аномалии, серьёзность, имя и окружение сервера, текущие значения метрик, SHAP-вклад
признаков и число похожих случаев за 7 дней. Ответ ожидается строго в двух
блоках:

```
EXPLANATION: <одно предложение по инциденту>
COMMAND: <одна команда только для чтения>
```

### Фильтрация безопасности (`is_command_safe`)

Два уровня:

1. **Deny-list** — 16 регулярных выражений: `rm -rf`, `dd if=`, `mkfs`,
   fork-bomb, `shutdown`, `reboot`, `halt`, `poweroff`, `chmod 777 /`,
   `chown ... /`, `nc ... | sh`, запись в `/dev/sd*` и `/etc/*`,
   `curl|sh`, `wget|sh`.
2. **Allow-list бинарников** — ~45 утилит диагностики (`ps`, `top`, `free`,
   `df`, `du`, `ss`, `netstat`, `iostat`, `docker`, `journalctl`, `systemctl`,
   `dmesg`, …). Команда разбивается по `;`, `|`, `&&`, `||`, и **все** сегменты
   должны быть разрешены.

При отказе LLM-команда заменяется детерминированным read-only шаблоном по типу
аномалии; если и он не проходит фильтр — команда подавляется полностью.

Сырой ответ LLM сохраняется в `recommendations.llm_raw_output`, прошедшая
проверку команда — в `filtered_command`.

Проверка фильтра изолированно:

```bash
uv run python scripts/test_recommender.py
```

---

## Генерация обучающих данных

### Классы аномалий

`cpu_spike`, `memory_leak`, `disk_fill`, `network_storm`, `container_crash`,
`service_down` (+ `normal`).

### Симулятор

```bash
# API-режим (по умолчанию), конфиги s1_normal … s8_anomaly
make sim
uv run python -m data_gen.simulator --config data_gen/simulator/s4_anomaly.yml -v

# Standalone → JSONL
make sim-standalone
uv run python -m data_gen.simulator --standalone \
    --output /tmp/metrics.jsonl --duration 3600 -v
```

Симулятор моделирует 33 поля метрик, профили сервисов (`web`, `database`,
`worker`, `cache`), суточную/недельную сезонность и движок аномалий. HTTP-режим
поднимает REST + Prometheus-эндпоинт на порту 8100–8108.

### Импорт размеченных JSONL

```bash
uv run python -m scripts.import_labeled_jsonl tmp/ready/clean_dataset.jsonl
```

Ожидаемый формат — одна JSON-строка на сэмпл с полями `timestamp`,
`server_name`, `anomaly_active`, `anomaly_type` и набором метрик. Импортёр
создаёт сервер при необходимости, дедуплицирует по `collected_at`, пишет
`extra_data` (`containers_running_ratio`, `swap_used_mb`) и формирует
`anomaly_events` (ground truth) по смене типа аномалии.

### Генерация датасета

```bash
# Чистый датасет для обучения: 6 серверов × 24 ч → JSONL
uv run python data_gen/scripts/generate_clean_dataset.py \
    --out tmp/ready/clean_dataset.jsonl --servers 6 --hours 24

# Синтетика нормального режима напрямую в БД
uv run python data_gen/scripts/generate_synthetic.py --all-servers --hours 24

# CSV-экспорт из БД
uv run python data_gen/scripts/export_dataset.py \
    --all-servers --mode windows --output data_gen/output
```

Один вызов `bash scripts/gen_synthetic_data.sh` выполняет связку
«генерация → импорт».

### Реальные стенды

| Стенд | Файл | Описание |
|---|---|---|
| Docker (3 сервера) | `data_gen/testbeds/docker-compose.testbed.yml` | Ubuntu + sshd, порты 2221–2223, `root`/`testbed123` |
| Удалённый стенд | `data_gen/testbeds/anomaly_testbed/` | цель + 4 victim-контейнера, `demo`-пользователь |
| Proxmox / Terraform | `data_gen/testbeds/terraform/` | 4 VM с cloud-init |
| Trainbed | `data_gen/trainbed/` | 6 профилей (web, database, storage, worker, monitoring, lb) в отдельную PG-БД, ускорение ×3600 |

Регистрация сервера и сбор:

```bash
uv run python data_gen/scripts/register_server.py \
    --name testbed-server-a --host localhost --port 2221 \
    --username root --password '***' --environment dev

uv run python data_gen/scripts/run_collector.py \
    --config data_gen/testbeds/servers.json --interval 15

uv run python data_gen/scripts/inject_anomalies.py \
    --config data_gen/testbeds/servers.json --episodes 5 --duration 120 --pause 60
```

Документация: `docs/04_DATA_GENERATION.md`.

---

## Фронтенд

Стек и версии — в таблице [Стек технологий](#стек-технологий).

```bash
cd frontend
npm install
npm run dev        # dev-сервер :5173
npm run build      # tsc -b && vite build → frontend/dist
npm run lint       # eslint
npm run format     # prettier
npm run gen:api    # генерация типов из OpenAPI
```

Переменные окружения (`frontend/.env`):

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/api/v1
VITE_DEMO_MODE=false      # включает Demo Panel
```

### Архитектура

Feature-based структура: `pages → widgets → features → entities → shared`.
Провайдеры: `ColorModeProvider → SnackbarProvider → QueryProvider → AuthProvider`.
Серверное состояние — TanStack Query (`staleTime` 30 с, авто-обновление
метрик/контейнеров каждые 15 с, аномалий и уведомлений — 30 с). Глобального
стора нет. Access-токен хранится **только в памяти** (не в `localStorage`),
refresh-cookie — HttpOnly; при `401` срабатывает single-flight refresh с
повтором запроса.

### Страницы

| Маршрут | Страница | Доступ |
|---|---|---|
| `/login` | Логин | публичный |
| `/` | Дашборд: стат-карточки, список серверов, последние аномалии | все |
| `/servers` | Сетка карточек, фильтры (окружение/статус/сортировка), пагинация | все |
| `/servers/:id` | Метаданные, вкладки «Обзор / Аномалии / Аудит», графики, контейнеры | все |
| `/servers/:id/console` | SSH-консоль (xterm.js) | все |
| `/anomalies` | Таблица с фильтрами и пагинацией | все |
| `/anomalies/:id` | SHAP-график, метрики на момент обнаружения, рекомендации | все |
| `/notifications` | Список, фильтр по прочитанному | все |
| `/profile` | Профиль, каналы уведомлений (in-app, Telegram) | все |
| `/users` | Пользователи, роли, пораздача доступа | admin |
| `/audit-log` | Журнал аудита + экспорт CSV | admin |
| `/llm-settings` | Настройки LLM и промпта | admin |
| `/demo` | Demo Control Panel | `VITE_DEMO_MODE=true` |

### Ключевые элементы

- **Графики метрик** (`MetricChart`): CPU, память, диск, сеть; диапазоны
  1 ч / 24 ч / 7 д / 30 д; пороговые линии (CPU 90 %, RAM 90 %, диск 85 %).
- **SHAP-график**: топ-12 признаков, красный — повышает оценку, зелёный —
  понижает; поддерживает и объектный, и списочный формат payload.
- **Карточка аномалии**: ошибка реконструкции, порог, коэффициент превышения,
  снимок метрик, workflow одобрения рекомендации (admin).
- **Консоль**: тёмная тема, авто-fit, обработка кодов закрытия, индикатор
  режима `read_only` (приходит с backend).
- **Логи контейнеров**: Drawer с выбором `tail` (50/100/200/500) и переключателем
  «следить», переключающим REST-снимок на WebSocket-стрим.
- **Тема**: светлая/тёмная, сохраняется в `localStorage`, начальный режим из
  `prefers-color-scheme`.
- Интерфейс полностью на русском языке.

### Права в UI

`ProtectedRoute` + `AdminRoute` на маршрутах; условный рендеринг в меню и на
страницах. Управление контейнерами доступно при `isAdmin || permission == "write"`
(эндпоинт `GET /servers/{id}/my-access`); при `read` колонка действий не
рендерится вовсе.

---

## Безопасность и RBAC

### Аутентификация

- Access-токен — JWT HS256, `sub`/`exp`/`type`, TTL `ACCESS_TOKEN_EXPIRE_MINUTES`
  (по умолчанию 1440 = 24 ч). Возвращается в теле ответа.
- Refresh-токен — JWT с уникальным `jti`, хранится в БД (`refresh_tokens`) для
  серверного отзыва. Отдаётся **только** в HttpOnly-cookie со `path=/api/v1/auth`,
  `samesite=lax`, `secure` по настройке, TTL 7 дней.
- Ротация при каждом `POST /auth/refresh`: старый `jti` отзывается.
- Пароли — bcrypt через passlib. Код подтверждает `type`-claim: access-токен
  не принимается там, где нужен refresh, и наоборот.

### Роли и доступ

| Роль | Возможности |
|---|---|
| `admin` | Полный доступ ко всем серверам, пользователям, аудиту, настройкам LLM; одобрение/отклонение рекомендаций |
| `operator` | Доступ только к выделенным серверам; severity по праву: `read` — чтение и консоль с вводом, `write` — управление контейнерами и логами |

Детализация доступа — таблица `user_server_access` `(user_id, server_id,
permission, granted_at)`. Фильтр применяется и к спискам (`WHERE id IN (...)`),
и к точечным запросам (`assert_server_read_access`), и к операциям записи
(`require_server_write_access`).

### Шифрование секретов

Пароли и приватные ключи SSH шифруются **Fernet** перед записью в БД
(`SSH_ENCRYPTION_KEY`), читаются лениво через `Server.get_decrypted_password()`.
Ключ нормализуется в 32 байта через SHA-256, если он не соответствует формату.
Идемпотентная миграция существующих записей:

```bash
uv run python scripts/encrypt_existing_secrets.py
```

Секреты никогда не возвращаются в API-схемах.

### Аудит

19 типов действий: `login`, `login_failed`, `logout`, `token_refreshed`,
`user_created`, `user_updated`, `user_deactivated`, `server_access_assigned`,
`server_created`, `server_updated`, `server_deleted`, `console_opened`,
`console_command`, `console_closed`, `container_action`,
`recommendation_approved`, `recommendation_rejected`, `anomaly_status_changed`,
`llm_settings_updated`.

Каждая запись содержит пользователя, ресурс, JSON-детали, IP и user-agent.
Сбой аудита не прерывает бизнес-операцию (обёрнут в `try/except` + `rollback`).
Ввод в консоли обрезается до 512 символов. Просмотр журнала — только для admin.

### Прочее

- CORS: при `BACKEND_CORS_ORIGINS="*"` реально подставляется `FRONTEND_URL`.
- Единый обработчик ошибок: `AppException`, HTTP, валидация (422), необработанные
  (500) — всегда в формате `{success, data, message, error}`.
- Иерархия исключений: `NotFoundError` 404, `ConflictError` 409,
  `ValidationError` 400, `AuthenticationError` 401, `PermissionDeniedError` 403,
  `SSHConnectionError` 502.

Подробнее — `docs/03_SECURITY_AND_RBAC.md`.

---

## Схема базы данных

17 таблиц (`app/models/`), 10 миграций Alembic.

### Пользователи и доступ

| Таблица | Ключевые поля |
|---|---|
| `users` | `username`, `email` (unique), `hashed_password`, `role`, `is_active` |
| `refresh_tokens` | `jti` (PK), `user_id`, `expires_at`, `revoked`, `revoked_at` |
| `user_server_access` | PK `(user_id, server_id)`, `permission` (`read`/`write`), `granted_at` |

### Серверы, метрики, контейнеры

| Таблица | Ключевые поля |
|---|---|
| `servers` | `name`, `host`, `port`, `environment`, `tags`, `status`, `last_seen`, `ssh_username`, `ssh_password` ⚿, `ssh_private_key` ⚿ |
| `metric_snapshots` | `server_id`, `collected_at`, 19 полей метрик, `extra_data` |
| `historical_metrics` | `metric_type`, `aggregation_level`, `timestamp`, `value_min/max/avg/last`, `sample_count` |
| `container_snapshots` | `container_id`, `container_name`, `image`, `status`, `extra_data`, `collected_at` |

⚿ — зашифровано Fernet.

### Алерты, аномалии, рекомендации

| Таблица | Ключевые поля |
|---|---|
| `alerts` | `title`, `status`, `severity`, `rule_type`, `server_id`, `metric_type`, `threshold_value`, `acknowledged_*`, `resolved_at` |
| `alert_rules` | `name`, `rule_type`, `is_enabled`, `severity`, `config`, `server_ids` (модель объявлена, движок использует хардкод-пороги) |
| `anomalies` | `server_id`, `detected_at`, `anomaly_type`, `severity`, `reconstruction_error`, `threshold`, `shap_explanation`, `metrics_snapshot`, `status`, `resolved_at` |
| `anomaly_events` | `server_id`, `scenario_type`, `start_ts`, `end_ts`, `parameters` — ground truth разметка |
| `recommendations` | `anomaly_id`, `llm_raw_output`, `filtered_command`, `explanation`, `status`, `approved_by`, `execution_result` |
| `llm_settings` | синглтон: `enabled`, `model`, `timeout_sec`, `keep_alive`, `prompt_template` |

### Уведомления, консоль, аудит

| Таблица | Ключевые поля |
|---|---|
| `notifications` | `user_id`, `anomaly_id`, `title`, `body`, `severity`, `is_read`, `sent_at`, `channels_sent` |
| `notification_channels` | `user_id`, `channel_type` (`inapp`/`telegram`), `config`, `enabled` |
| `console_sessions` | `session_token` (unique), `user_id`, `server_id`, `status`, `started_at`, `ended_at`, `termination_reason` |
| `audit_logs` | `user_id`, `action`, `resource_type`, `resource_id`, `details`, `ip_address`, `user_agent` |

---

## Конфигурация

Все настройки — через `.env` (`app/core/config.py`, pydantic-settings).

### Обязательное для продакшена

```bash
# Генерация SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"

# Генерация ключа Fernet для SSH-секретов
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```env
SECRET_KEY=<случайная строка>
SSH_ENCRYPTION_KEY=<Fernet-ключ>
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/server_monitor
```

### Основные параметры

```env
# Приложение
APP_NAME=Server Monitor Backend
APP_VERSION=0.1.0
DEBUG=False

# Безопасность
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440     # 24 ч
JWT_REFRESH_EXPIRE_DAYS=7
COOKIE_SECURE=False                  # True за HTTPS
COOKIE_SAMESITE=lax

# SSH
SSH_TIMEOUT=30
SSH_CONNECTION_RETRIES=3

# Сбор метрик
METRICS_INTERVAL_SEC=15              # фактический такт планировщика
METRICS_RETENTION_DAYS=30

# ML
ML_MODELS_DIR=models
ML_INFERENCE_INTERVAL_SEC=60         # период ML-анализа
ML_WINDOW_SIZE=60
ML_ANOMALY_MAX_OPEN_MIN=30           # автозакрытие «зависших»
ML_ANOMALY_DEDUP_GRACE_MIN=5         # grace для дедупликации
ML_CORROBORATION_MIN_PERCENT=80.0
ML_DEMO_DISABLE_DEDUP=false

# LLM (Ollama)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SEC=60
OLLAMA_KEEP_ALIVE=30m

# Уведомления
TELEGRAM_BOT_TOKEN=
REDIS_URL=redis://redis:6379/0

# Фронтенд / CORS
FRONTEND_URL=http://localhost:5173
BACKEND_CORS_ORIGINS=http://localhost:5173

# Демо
DEMO_MODE=false

# Аудит
AUDIT_LOG_RETENTION_DAYS=180
```

> Параметры `ML_INTERVAL_MIN`, `ML_BACKGROUND_SET_SIZE`, `METRICS_COLLECTION_INTERVAL`
> и `SSH_CONNECTION_RETRIES` объявлены, но в текущей версии не читаются кодом.

### Миграции

```bash
uv run alembic revision --autogenerate -m "Описание"
uv run alembic upgrade head
uv run alembic downgrade -1
```

---

## Тесты и линтеры

```bash
make test                # uv run pytest
uv run pytest tests/ml -v
uv run pytest tests/integration -v
```

`asyncio_mode = "auto"` — async-тесты не требуют декораторов.

| Файл | Тестов | Покрытие |
|---|---|---|
| `tests/ml/test_config.py` | 4 | Порядок `CLASSES`, число признаков, маппинг меток, константы окон |
| `tests/ml/test_features.py` | 6 | `extract_features` на синтетических данных, скорости, `log1p` |
| `tests/ml/test_windows.py` | 5 | Форма окон, stride, разметка по хвосту (`min_tail=10`) |
| `tests/ml/test_lstm_ae_smoke.py` | 2 | Форма входа/выхода AE, сходимость на одном образце |
| `tests/ml/test_classifier_smoke.py` | 1 | Форма выхода `(N, 7)`, нормировка softmax |
| `tests/ml/test_registry.py` | 2 | Загрузка артефактов `ModelRegistry` |
| `tests/integration/test_import_jsonl.py` | 2 | Импорт JSONL, дедупликация снапшотов |

Линтинг и форматирование:

```bash
uv run ruff check .
uv run ruff format .
cd frontend && npm run lint && npm run format
```

---

## Известные ограничения

Текущее состояние проекта, важное при эксплуатации и доработке:

- **Пороги алертов зашиты в код** (`AlertEngine`). Модель `AlertRule` и её
  конфигурация в БД объявлены, но не используются — изменение порогов требует
  правки кода.
- **Авторазрешение алертов не реализовано**: открытые алерты живут до ручного
  `acknowledge` / `resolve`. Уведомления отправляются только по ML-аномалиям.
- **`precision` автоэнкодера (0.51) ниже целевого (0.80)** — компенсируется
  корроборацией сырыми метриками, дедупликацией и per-feature порогами.
  Подробный план доработки — `docs/ml_retraining_plan.md`.
- **Джоб очистки данных не запущен.** `MetricsAggregationService` и функции
  очистки исторических метрик реализованы, но не вызываются планировщиком;
  hourly/day агрегация не выполняется (заполняется только `minute`).
- **`container_id` не валидируется** перед подстановкой в SSH-команду —
  потенциальный вектор инъекции для пользователя с правом `write`.
- **Проверка SSH host-ключей отключена** (`paramiko.AutoAddPolicy`).
- **Полный `container_snapshots`** хранит только последнее состояние (запись
  удаляет предыдущие строки) — истории контейнеров нет.
- **UI алертов отсутствует**: API работает, но экрана и меню для алертов нет.
- **Фронтенд-тесты не настроены** (Vitest не установлен, скрипта `test` нет).
- **nginx монтирует корень `frontend/`**, а не `frontend/dist`. Для продакшена
  содержимое сборки нужно скопировать в корень `frontend/` (или поправить
  volume в `docker-compose.yml`). TLS-сертификаты в `nginx.conf` не настроены —
  фактически работает только HTTP:80.
- **`schema.ts` фронтенда — заглушка**: скрипт `gen:api` не генерировал типы из
  OpenAPI, типы в `entities/*` написаны вручную.
- **Сбор метрик последователен**: при N серверах цикл занимает не менее
  N × (2 SSH-сессии). Для масштабирования нужен параллелизм или агенты.
- **Модель `AlertRule`, `AnomalyEvent` как ground truth, часть настроек**
  (см. выше) объявлены, но не задействованы в основном потоке.

---

## Документация

| Файл | Содержание |
|---|---|
| `docs/00_PROJECT_OVERVIEW.md` | Обзор проекта |
| `docs/01_REQUIREMENTS.md` | Требования |
| `docs/02_ARCHITECTURE.md`, `docs/ARCHITECTURE.md` | Архитектура |
| `docs/03_SECURITY_AND_RBAC.md` | Модель безопасности |
| `docs/04_DATA_GENERATION.md` | Генерация данных |
| `docs/05_ML_MODELS.md` | Архитектура и обучение ML-моделей |
| `docs/06_BACKEND.md` | Backend |
| `docs/07_FRONTEND.md` | Frontend |
| `docs/DEMO_PLAYBOOK.md` | Сценарий демонстрации |
| `docs/ml_training_guide.md` | Руководство по обучению |
| `docs/ml_retraining_plan.md` | План доработки моделей |
| `docs/SRS_IEEE830_*.md`, `docs/ТЗ_ГОСТ34_*.md` | ТЗ и спецификация требований |
| `CLAUDE.md` | Настройки проекта для ИИ-агентов |
| `CONTRIBUTING.md` | Правила участия |

---

## Лицензия

MIT — см. [LICENSE](LICENSE).