import sqlite3
import datetime
from typing import Optional
from fastapi import Request, HTTPException, status
import bcrypt
from jose import jwt, JWTError

# Config de sécurité
SECRET_KEY = "CHANGE_MOI_PAR_UNE_CLE_SECRETE_TRES_LONGUE_ET_ALEATOIRE"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# Hachage des mots de passe


def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crée la table des utilisateurs si elle n'existe pas déjà."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    # bcrypt attend des bytes et un sel unique
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hashed_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request) -> Optional[dict]:
    """Récupère l'utilisateur connecté depuis le cookie de session JWT."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None

def require_user(request: Request) -> dict:
    """Dépendance à utiliser sur les routes privées."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Accès non autorisé. Veuillez vous connecter."
        )
    return user