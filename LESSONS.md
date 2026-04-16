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



