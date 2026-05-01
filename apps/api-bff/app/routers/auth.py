"""BFF router: Authentication with local JWT."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import base64
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Request, Cookie
from pydantic import BaseModel
from opspilot_schema.envelope import make_success, make_error

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET", "opspilot-dev-secret-key-change-in-prod")
JWT_EXPIRY_SECONDS = int(os.environ.get("JWT_EXPIRY_SECONDS", "86400"))
COOKIE_NAME = "opspilot_token"

MOCK_USERS = {
    "admin": {"password": "admin123", "display_name": "管理员", "role": "admin", "avatar": "A"},
    "zhangsan": {"password": "ops123", "display_name": "张三", "role": "operator", "avatar": "张"},
    "lisi": {"password": "ops123", "display_name": "李四", "role": "operator", "avatar": "李"},
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _sign_jwt(payload: dict) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    sig_input = f"{header}.{body}".encode()
    sig = _b64url_encode(hmac.new(JWT_SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def _verify_jwt(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        sig_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = _b64url_encode(hmac.new(JWT_SECRET.encode(), sig_input, hashlib.sha256).digest())
        if not hmac.compare_digest(expected_sig, parts[2]):
            return None
        payload = json.loads(_b64url_decode(parts[1]))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        return None
    return _verify_jwt(token)


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginBody, response: Response):
    user_record = MOCK_USERS.get(body.username)
    if not user_record or user_record["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    payload = {
        "sub": body.username,
        "display_name": user_record["display_name"],
        "role": user_record["role"],
        "avatar": user_record["avatar"],
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY_SECONDS,
    }
    token = _sign_jwt(payload)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=JWT_EXPIRY_SECONDS,
        path="/",
    )
    return make_success({
        "username": body.username,
        "display_name": user_record["display_name"],
        "role": user_record["role"],
        "avatar": user_record["avatar"],
        "token": token,
    })


@router.get("/me")
async def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return make_success({
        "username": user["sub"],
        "display_name": user["display_name"],
        "role": user["role"],
        "avatar": user["avatar"],
    })


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return make_success({"message": "Logged out"})
