from datetime import datetime, timedelta
from typing import Any, Union

from jose import jwt
from argon2 import PasswordHasher

from app.core.config import settings


# Password hashing
password_hasher = PasswordHasher()


def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta = None
) -> str:

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject)
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:

    try:
        return password_hasher.verify(
            hashed_password,
            plain_password
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:

    return password_hasher.hash(password)