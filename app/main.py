import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import authenticate_player, create_access_token, get_current_player, hash_password
from app.db import Base, DATABASE_URL, engine, get_db
from app.models import Player
from app.schemas import PlayerPartialUpdate, PlayerRead, PlayerRegister, PlayerUpdateFull, Token


openapi_tags = [
    {"name": "Health", "description": "Проверка работоспособности сервиса."},
    {"name": "Auth", "description": "Регистрация и получение JWT токена."},
    {"name": "Players", "description": "CRUD для игроков (требует Bearer-токен)."},
]

app = FastAPI(title="Player API", version="0.1.1", openapi_tags=openapi_tags)


@app.on_event("startup")
def on_startup() -> None:
    # Для SQLite при первом запуске создаем папку под БД.
    if DATABASE_URL.startswith("sqlite"):
        db_path = str(engine.url.database) if engine.url.database else None
        if db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

    Base.metadata.create_all(bind=engine)

    # Мини-миграция для SQLite (уровень урока): добавляем колонку password_hash,
    # если база уже была создана до урока 1.1.
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(players)")).fetchall()
            col_names = {row[1] for row in cols}  # row[1] = name
            if "password_hash" not in col_names:
                conn.execute(text("ALTER TABLE players ADD COLUMN password_hash VARCHAR(255)"))


@app.get("/health", tags=["Health"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=PlayerRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"],
    summary="Регистрация игрока",
)
def register_player(player_in: PlayerRegister, db: Session = Depends(get_db)) -> PlayerRead:
    player = Player(
        username=player_in.username,
        email=player_in.email,
        password_hash=hash_password(player_in.password),
    )
    db.add(player)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Игрок с таким username или email уже существует",
        )
    db.refresh(player)
    return player


@app.post(
    "/auth/token",
    response_model=Token,
    tags=["Auth"],
    summary="Получить JWT access token",
)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    player = authenticate_player(db, form_data.username, form_data.password)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=player.username)
    return Token(access_token=token)


@app.get("/players", response_model=List[PlayerRead], tags=["Players"])
def list_players(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Player = Depends(get_current_player),
) -> List[PlayerRead]:
    return (
        db.query(Player)
        .order_by(Player.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get("/players/{player_id}", response_model=PlayerRead, tags=["Players"])
def get_player(
    player_id: int,
    db: Session = Depends(get_db),
    _: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    return player


@app.put("/players/{player_id}", response_model=PlayerRead, tags=["Players"])
def update_player_put(
    player_id: int,
    player_in: PlayerUpdateFull,
    db: Session = Depends(get_db),
    _: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    player.username = player_in.username
    player.email = player_in.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Игрок с таким username или email уже существует",
        )
    db.refresh(player)
    return player


@app.patch("/players/{player_id}", response_model=PlayerRead, tags=["Players"])
def update_player_patch(
    player_id: int,
    player_in: PlayerPartialUpdate,
    db: Session = Depends(get_db),
    _: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    data = player_in.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in data.items():
        setattr(player, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Игрок с таким username или email уже существует",
        )

    db.refresh(player)
    return player


@app.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Players"])
def delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    _: Player = Depends(get_current_player),
) -> Response:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    db.delete(player)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

