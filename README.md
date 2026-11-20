# Keitaro API Wrapper

Веб-сервис для автоматизации работы с рекламными кампаниями и потоками в трекере Keitaro через Admin API.

## Возможности

1. Авторизация по API ключу Keitaro:
   - Можно указать собственный API ключ Keitaro в форме входа.
   - Если оставить поле пустым, используется единый тестовый ключ `KEITARO_DEFAULT_API_KEY` из `.env` на сервере.
   - Ключ проверяется через запрос к Keitaro Admin API, после чего создается серверная сессия (`HttpOnly` cookie `kt_session`).
2. Создаватор кампаний:
   - Принимает название кампании (по умолчанию предзаполнен префикс `test_lukashov_`), двухбуквенный гео-код страны (ISO alpha-2, например `US`, `RU`, `DE`), ID оффера, домен, группу и источник трафика.
   - Создает кампанию в Keitaro и два потока в порядке приоритета:
     - Поток 1: фильтр по указанной стране -> прямой редирект на `https://www.google.com`.
     - Поток 2: остальной трафик (без гео-фильтра) -> выбранный оффер с весом `100%`.
3. Редактор существующей кампании:
   - `Fetch Streams` - синхронизация потоков кампании из Keitaro (потоки без офферов импортируются как заглушки без изменения их фильтров и редиректов).
   - Поиск офферов по ID или названию (`GET /api/offers?q=...`) и добавление в поток.
   - Черновики: любое локальное изменение подсвечивает поток желтым, не затрагивая Keitaro до нажатия `Push to KT`.
   - `Cancel` - откат локальных черновиков до последнего синхронизированного/опубликованного состояния.
   - Мягкое удаление (`Remove`) и восстановление (`Bring Back`): удаленный оффер остается серым в интерфейсе с весом `0%`, при публикации удаляется из Keitaro, но остается в архиве обертки. Внешнее удаление офферов в самом Keitaro при повторном `Fetch Streams` также переводит их в статус `removed`.
   - Фиксация весов (`Pin` / `Unpin`): закрепленные проценты не меняются, а остаток до `100%` равномерно распределяется между незакрепленными активными офферами.

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, httpx, Pydantic v2
- БД: PostgreSQL 16
- Frontend: React 18, TypeScript, Vite, Nginx
- Контейнеризация: Docker, Docker Compose

## Структура проекта

```text
.
├── backend/
│   ├── alembic/            # Конфигурация и миграции Alembic
│   ├── app/
│   │   ├── api/            # Роутеры FastAPI (auth, references, campaigns, editor)
│   │   ├── services/       # Клиент Keitaro API, пересчет весов, сервисы модулей
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── deps.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── tests/              # Автотесты pytest
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   └── types/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── .env.example
├── .gitignore
└── docker-compose.yml
```

## Настройка и запуск через Docker

1. Скопируйте файл переменных окружения и заполните тестовый API ключ Keitaro (ключ берется в админке Keitaro: Профиль -> API ключи):

```bash
cp .env.example .env
```

Основные переменные в `.env`:

- `DATABASE_URL` - строка подключения к PostgreSQL (`postgresql+asyncpg://postgres:postgres@db:5432/keitaro_wrapper`).
- `KEITARO_API_URL` - базовый URL Keitaro Admin API (`https://tlgk.host/admin_api/v1`).
- `KEITARO_DEFAULT_API_KEY` - общий тестовый API ключ (используется, если поле входа оставить пустым).
- `DEFAULT_CAMPAIGN_PREFIX` - префикс для названия кампаний в UI (по умолчанию `test_lukashov_`).
- `DEFAULT_DOMAIN_ID`, `DEFAULT_GROUP_ID`, `DEFAULT_TRAFFIC_SOURCE_ID` - опциональные ID по умолчанию для Создаватора.
- `BACKEND_PORT`, `FRONTEND_PORT` - внешние порты для Docker Compose (по умолчанию `8000` и `3000`).

2. Соберите и запустите контейнеры (при старте `backend` миграции Alembic применяются автоматически через `alembic upgrade head`):

```bash
docker compose up --build -d
```

3. Откройте приложение:

- Frontend (React UI): http://localhost:3000
- Backend Swagger UI: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/health

## Миграции Alembic (вручную)

Если нужно накатить или откатить миграции вручную внутри контейнера `backend`:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec backend alembic downgrade -1
```

## Запуск автотестов

Тесты проверяют алгоритм пересчета весов (включая `Pin`, `Remove`, `Bring Back` и краевые случаи), авторизацию по API ключу, Создаватор кампаний и полный цикл черновиков Редактора с моком `KeitaroClient`:

```bash
docker compose exec -T backend pytest -v
```
