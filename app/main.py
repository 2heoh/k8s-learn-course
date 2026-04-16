import os
from typing import List

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional

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

def _ensure_admin_or_self(current: Player, target: Player) -> None:
    if current.role == "admin":
        return
    if current.id != target.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")


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

    # Мини-миграции для SQLite (уровень урока): добавляем недостающие колонки,
    # если база уже была создана до новых уроков.
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as conn:
            cols = conn.execute(text("PRAGMA table_info(players)")).fetchall()
            col_names = {row[1] for row in cols}  # row[1] = name
            if "password_hash" not in col_names:
                conn.execute(text("ALTER TABLE players ADD COLUMN password_hash VARCHAR(255)"))
            if "role" not in col_names:
                conn.execute(text("ALTER TABLE players ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))


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
        role="user",
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
    "/auth/register-admin",
    response_model=PlayerRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"],
    summary="Создать admin (bootstrap)",
)
def register_admin_player(
    player_in: PlayerRegister,
    db: Session = Depends(get_db),
    x_bootstrap_key: Optional[str] = Header(default=None, alias="X-Bootstrap-Key"),
) -> PlayerRead:
    expected = os.getenv("BOOTSTRAP_ADMIN_KEY")
    if not expected:
        # Не раскрываем, что эндпоинт существует, если bootstrap не настроен.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not x_bootstrap_key or x_bootstrap_key != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    player = Player(
        username=player_in.username,
        email=player_in.email,
        password_hash=hash_password(player_in.password),
        role="admin",
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
    current: Player = Depends(get_current_player),
) -> List[PlayerRead]:
    # Authorization:
    # - admin: видит всех
    # - user: видит только себя
    q = db.query(Player).order_by(Player.id.asc())
    if current.role != "admin":
        q = q.filter(Player.id == current.id)
    return q.offset(skip).limit(limit).all()


@app.get("/players/{player_id}", response_model=PlayerRead, tags=["Players"])
def get_player(
    player_id: int,
    db: Session = Depends(get_db),
    current: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    _ensure_admin_or_self(current=current, target=player)
    return player


@app.put("/players/{player_id}", response_model=PlayerRead, tags=["Players"])
def update_player_put(
    player_id: int,
    player_in: PlayerUpdateFull,
    db: Session = Depends(get_db),
    current: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    _ensure_admin_or_self(current=current, target=player)

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
    current: Player = Depends(get_current_player),
) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    _ensure_admin_or_self(current=current, target=player)

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
    current: Player = Depends(get_current_player),
) -> Response:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    # Authorization:
    # - admin: может удалять любого
    # - user: удаление запрещено
    if current.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    db.delete(player)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

