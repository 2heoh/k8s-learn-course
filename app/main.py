import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, DATABASE_URL, engine, get_db
from app.models import Player
from app.schemas import PlayerCreate, PlayerPartialUpdate, PlayerRead, PlayerUpdateFull


app = FastAPI(title="Player API", version="0.1.0")


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/players", response_model=PlayerRead, status_code=status.HTTP_201_CREATED)
def create_player(player_in: PlayerCreate, db: Session = Depends(get_db)) -> PlayerRead:
    player = Player(username=player_in.username, email=player_in.email)
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


@app.get("/players", response_model=List[PlayerRead])
def list_players(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[PlayerRead]:
    return (
        db.query(Player)
        .order_by(Player.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@app.get("/players/{player_id}", response_model=PlayerRead)
def get_player(player_id: int, db: Session = Depends(get_db)) -> PlayerRead:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")
    return player


@app.put("/players/{player_id}", response_model=PlayerRead)
def update_player_put(
    player_id: int,
    player_in: PlayerUpdateFull,
    db: Session = Depends(get_db),
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


@app.patch("/players/{player_id}", response_model=PlayerRead)
def update_player_patch(
    player_id: int,
    player_in: PlayerPartialUpdate,
    db: Session = Depends(get_db),
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


@app.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(player_id: int, db: Session = Depends(get_db)) -> Response:
    player = db.query(Player).filter(Player.id == player_id).first()
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Игрок не найден")

    db.delete(player)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

