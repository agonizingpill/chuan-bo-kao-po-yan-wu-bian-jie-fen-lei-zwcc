import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import Session, setting
from .models import User

bearer = HTTPBearer(auto_error=False)
secret = setting('JWT_SECRET', 'private-demo-berth-local-1074-for-development')


def password_hash(password):
    salt = secrets.token_hex(16)
    return f'{salt}:{_derive(password, salt)}'


def _derive(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 250_000).hex()


def valid_password(password, encoded):
    salt, expected = encoded.split(':')
    return hmac.compare_digest(_derive(password, salt), expected)


def token_for(user):
    now = datetime.now(UTC)
    return jwt.encode({'sub': user.username, 'role': user.role, 'iat': now, 'exp': now + timedelta(hours=8)}, secret, algorithm='HS256')


def current_user(request: Request, token: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not token:
        raise HTTPException(401, '请先登录', {'WWW-Authenticate': 'Bearer'})
    try:
        claims = jwt.decode(token.credentials, secret, algorithms=['HS256'], options={'require': ['sub', 'exp']})
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, '会话无效，请重新登录', {'WWW-Authenticate': 'Bearer'}) from exc
    with Session() as session:
        user = session.get(User, claims['sub'])
        if not user or user.role != claims.get('role'):
            raise HTTPException(401, '账号权限已更新，请重新登录')
        request.state.actor = user.username
        return user


def permitted(*roles):
    def dependency(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, '当前岗位没有此操作权限')
        return user
    return dependency
