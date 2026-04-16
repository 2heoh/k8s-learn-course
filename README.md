# Player API (FastAPI)

RESTful API для работы с сущностью `Игрок` (CRUD).

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Важно: запускай `uvicorn` именно из `venv` (если запустить системный `uvicorn`, можно получить ошибки вида `ModuleNotFoundError: sqlalchemy`).
Проверить, что используется venv:
```bash
which python
which uvicorn
```

Swagger/OpenAPI:
`http://localhost:8000/docs`

## Настройка БД

По умолчанию используется SQLite в файле `data/app.db`.

Можно задать переменную окружения:
`DATABASE_URL=sqlite:///./data/app.db`

## Эндпоинты

`GET /health`

`POST /players` (создать игрока)
```bash
curl -X POST http://localhost:8000/players \
  -H "Content-Type: application/json" \
  -d '{"username":"player1","email":"player1@example.com"}'
```

`GET /players?skip=0&limit=20` (список)

`GET /players/{player_id}` (получить по id)

`PUT /players/{player_id}` (полное обновление)
```bash
curl -X PUT http://localhost:8000/players/1 \
  -H "Content-Type: application/json" \
  -d '{"username":"player1_new","email":"new@example.com"}'
```

`PATCH /players/{player_id}` (частичное обновление)

`DELETE /players/{player_id}` (удалить)

## Kubernetes (k8s)

Нужно собрать Docker-образ и задеплоить его как `Deployment` + `Service`.

### 1) Собрать образ

```bash
docker build -t player-api:latest .
```

Если деплоишь в “удалённый” кластер (не local kind/minikube), перетегируй и запушь в реестр:
```bash
docker tag player-api:latest <registry>/<namespace>/player-api:latest
docker push <registry>/<namespace>/player-api:latest
```
И затем замени `image:` в `k8s/deployment.yaml`.

### 2) Применить манифесты

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 3) Доступ с локальной машины

```bash
kubectl port-forward svc/player-api 8000:80
curl http://127.0.0.1:8000/health
```

