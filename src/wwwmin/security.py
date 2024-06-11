from datetime import timedelta
from typing import Annotated

import jwt
import argon2
from fastapi import Cookie, Header

from .util import utcnow
from .database import User

hasher = argon2.PasswordHasher()
JWT_SECRET = "correct horse battery staple"
JWT_TTL = timedelta(days=30)


class AuthenticationError(Exception):
    pass


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(hash: str, password: str) -> bool:
    try:
        return hasher.verify(hash, password)
    except argon2.exceptions.VerificationError:
        raise AuthenticationError("Password mismatch.")


def encode_token(user_id: int) -> str:
    return jwt.encode(
        {"user": user_id, "exp": utcnow() + JWT_TTL}, key=JWT_SECRET, algorithm="HS256"
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, key=JWT_SECRET, algorithms=["HS256"])["user"]
    except jwt.DecodeError:
        raise AuthenticationError("Invalid token.")


def create_user(username: str, password: str) -> User:
    password_hash = hash_password(password)
    return User.insert(username, password_hash)


def login_user(username: str, password: str) -> tuple[User, str]:
    user = User.by_name(username)
    if not user:
        raise AuthenticationError("User not found.")
    verify_password(user.password_hash, password)
    token = encode_token(user_id=user.id)
    return user, token


class LoginRequired(Exception):
    pass


async def authenticate(
    cookie: Annotated[str | None, Cookie(alias="Authorization")] = None,
    header: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User | None:
    token = cookie or header
    if token is None:
        raise LoginRequired("No authorization found.")
    try:
        user_id = decode_token(token)
        return User.get(user_id)
    except AuthenticationError:
        raise LoginRequired("Invalid authentication found.")
