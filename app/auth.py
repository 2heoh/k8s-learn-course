from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Player


# Для учебного проекта выбираем PBKDF2 (встроено в passlib, без внешнего bcrypt).
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def _secret_key() -> str:
    # В проде обязательно задавай SECRET_KEY через env/Secret.
    return os.getenv("SECRET_KEY", "change-me-in-prod")


def _algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def _expires_minutes() -> int:
    try:
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    except ValueError:
        return 60


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_expires_minutes())
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, _secret_key(), algorithm=_algorithm())


def get_player_by_username(db: Session, username: str) -> Optional[Player]:
    return db.query(Player).filter(Player.username == username).first()


def authenticate_player(db: Session, username: str, password: str) -> Optional[Player]:
    player = get_player_by_username(db, username)
    if not player or not player.password_hash:
        return None
    if not verify_password(password, player.password_hash):
        return None
    return player


def get_current_player(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Player:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный токен авторизации",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[_algorithm()])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    player = get_player_by_username(db, username)
    if player is None:
        raise credentials_exception
    return player

