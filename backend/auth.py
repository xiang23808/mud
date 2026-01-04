from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
import hashlib
from backend.config import settings

def hash_password(password: str) -> str:
    """使用SHA256哈希密码(替代bcrypt以避免长度限制问题)"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    return hash_password(plain) == hashed

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload.get("sub"))
    except:
        return None