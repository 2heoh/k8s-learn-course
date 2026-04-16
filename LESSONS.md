# LESSONS

## Урок 1

### Задание

Сделать минимальный сервис и подготовить его к запуску в Kubernetes (kind).

### Требования

- **REST API (FastAPI)**: реализовать CRUD для сущности **Игрок**.
- **Хранилище**: использовать SQLite (локальная БД в файле).
- **Docker**: собрать Docker-образ приложения.
- **Kubernetes (kind)**: создать/запустить локальный кластер kind и подготовить манифесты для деплоя.

### Результат (что должно получиться)

- **Код сервиса** находится в `app/`, запуск локально через `uvicorn app.main:app`.
- **Docker-образ** собирается командой `docker build -t player-api:<tag> .` (лучше не использовать `latest`).
- **Манифесты Kubernetes** лежат в `k8s/` и применяются через `kubectl apply -f k8s/`.
- После запуска доступен `GET /health`, который возвращает `{"status":"ok"}`.

### Полезные команды (k8s)

- **Проверить контекст kubectl** (важно, если есть и `docker-desktop`, и `kind`):
  - `kubectl config current-context`
  - `kubectl config get-contexts`
  - `kubectl config use-context kind-kind`

## Урок 1.1

### Задание: Authentication (JWT)

Добавить в сервис базовую аутентификацию, чтобы CRUD-эндпоинты были доступны только авторизованным пользователям.

### Требования

- **Регистрация**: `POST /auth/register` принимает `username`, `email`, `password` и создаёт игрока.
- **Логин**: `POST /auth/token` выдаёт `access_token` (JWT, Bearer).
- **Защита API**: эндпоинты `/players` должны требовать заголовок `Authorization: Bearer <token>`.
- **Секрет**: ключ подписи JWT задаётся через переменную окружения `SECRET_KEY` (в k8s — через env/Secret).

### Результат (что должно получиться)

- Можно зарегистрироваться, получить токен и затем выполнить запросы к `/players` с Bearer‑токеном.

### Полезные команды (Swagger/OpenAPI)

- **Посмотреть OpenAPI**: `curl http://localhost:8000/openapi.json`
- **Быстро проверить наличие auth-путей**:
  - `curl -s http://localhost:8000/openapi.json | grep -Eo '"/auth/[^"]+' | head`

### Полезные команды (релиз в kind “по‑правильному”)

Идея: используем **immutable tag** и обновляем `Deployment` на конкретную версию.

```bash
export TAG="v1.1.1"
docker build -t player-api:$TAG .
kind load docker-image player-api:$TAG --name kind

kubectl config use-context kind-kind
kubectl set image deployment/player-api player-api=player-api:$TAG
kubectl rollout status deployment/player-api
```

## Урок 1.2

### Тема: Authorization (права доступа)

Цель: научиться отличать **authentication** (кто ты) от **authorization** (что тебе можно) и реализовать простую модель прав.

### Задание (практика)

Реализуй роли и правила доступа к API.

#### Роли

- **admin**: может управлять всеми игроками
- **user**: может читать/менять только “себя”

#### Требования к данным

- Добавить игроку поле **role** (например: `admin` | `user`)
- Определить, как назначается роль при регистрации:
  - по умолчанию `user`
  - (опционально) отдельный способ сделать первого админом через env (например `BOOTSTRAP_ADMIN_USERNAME`)

#### Правила доступа (обязательно)

- **GET /players**
  - `admin`: видит всех
  - `user`: видит только себя (или вернуть 403 — выбери один вариант)
- **GET /players/{id}**
  - `admin`: доступ к любому `id`
  - `user`: доступ только к своему `id`
- **PUT/PATCH /players/{id}**
  - `admin`: может менять `username/email` любого игрока
  - `user`: может менять только свои `username/email`
- **DELETE /players/{id}**
  - `admin`: может удалять любого
  - `user`: запрещено (403) либо разрешено только “себя” (выбери и зафиксируй)

#### Ограничения безопасности

- Запретить пользователю менять роль через публичные эндпоинты.
- При ошибке прав возвращать **403 Forbidden**.

### Что должно получиться (критерии готовности)

- В Swagger понятно, какие эндпоинты требуют токен.
- Можно зарегистрировать двух пользователей: `admin` и `user`, получить токены и проверить, что правила выше реально работают.
- Покрыть минимум ручными проверками через `curl`:
  - `user` не может читать чужого игрока
  - `user` не может удалять чужого игрока (и в зависимости от правила — даже себя)
  - `admin` может читать/обновлять/удалять любого

### Acceptance tests (обязательно)

Добавить acceptance tests для кейса `admin` vs `user`.

- **Локально (in-memory)**:
  - `pip install -r requirements-dev.txt`
  - `pytest -q`
- **E2E против кластера** (через `kubectl port-forward` на `http://localhost:8000`):
  - `kubectl port-forward svc/player-api 8000:80`
  - `BASE_URL="http://localhost:8000" BOOTSTRAP_ADMIN_KEY="<key>" pytest -q -m e2e`

## Урок 1.3

### Тема: Authentication/Authorization на Ingress (NGINX Ingress Controller)

Цель: вынести **проверку “входа”** (наличие/валидность токена) на уровень k8s через Ingress NGINX, чтобы неавторизованные запросы отсеивались до приложения.

Важно: “authorization по данным” (например, user может читать только себя) обычно остаётся в сервисе.

### Задание (практика)

- Установить **NGINX Ingress Controller** в kind.
- Добавить `Ingress` для `player-api`.
- Настроить проверку авторизации на уровне Ingress:
  - **вариант A (минимальный)**: `nginx.ingress.kubernetes.io/auth-url` + отдельный эндпоинт проверки токена
  - **вариант B (расширенный)**: oauth2-proxy + OIDC (например GitHub/Google/Keycloak)

### Минимальные требования

- `GET /health` доступен без авторизации.
- Все запросы к `/players` требуют авторизации на уровне Ingress:
  - без `Authorization: Bearer ...` должно возвращаться **401/403** от Ingress
  - с токеном — запрос проходит до приложения

### Что должно получиться (критерии готовности)

- В кластере есть ресурсы Ingress Controller и `Ingress` для сервиса.
- Проверка через `curl`:
  - `/health` → 200 без токена
  - `/players` → 401/403 без токена (ответ сформирован Ingress)
  - `/players` → 200 с токеном



