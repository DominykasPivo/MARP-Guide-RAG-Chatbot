import logging
import os
import sys
from typing import Annotated, Optional, Union

import bcrypt
import psycopg2
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Configuration & Logging ---
DB_NAME = os.environ.get("POSTGRES_DB", "mydb")
DB_USER = os.environ.get("POSTGRES_USER", "postgres_user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "mysecretpassword")
DB_HOST = os.environ.get("POSTGRES_HOST", "postgres")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("auth")

# --- FastAPI Setup ---
app = FastAPI(title="MARP Authentication Service", version="1.0.0")

# ✅ CORS MUST BE ENABLED - Browser requires it for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],  # In production, specify exact origins like ["http://localhost:8005"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_manager = None


# Pydantic Models
class UserAuth(BaseModel):
    username: str
    password: str


class ChatQuery(BaseModel):
    query: str


# --- Database Manager ---
class DatabaseManager:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT,
            )
            self.conn.autocommit = True
            self.cursor = self.conn.cursor()
            logger.info("Successfully connected to PostgreSQL.")
            self.create_tables()
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            self.cursor = None

    def close(self):
        if self.conn:
            self.conn.close()

    def create_tables(self):
        if not self.cursor:
            return
        try:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """
            )

            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_history_user_id
                ON chat_history(user_id, timestamp DESC);
            """
            )

            logger.info("Tables 'users' and 'chat_history' ensured to exist.")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def get_user(self, username: str) -> Optional[tuple]:
        if not self.cursor:
            return None
        try:
            self.cursor.execute(
                "SELECT id, username, hashed_password FROM users WHERE username = %s;",
                (username,),
            )
            result: Optional[tuple] = self.cursor.fetchone()  # Added type annotation
            return result
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[tuple]:
        if not self.cursor:
            return None
        try:
            self.cursor.execute(
                "SELECT id, username FROM users WHERE id = %s;", (user_id,)
            )
            result: Optional[tuple] = self.cursor.fetchone()  # Added type annotation
            return result
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

    def insert_user(self, username: str, hashed_password: bytes) -> Optional[int]:
        if not self.cursor:
            return None
        try:
            self.cursor.execute(
                """
                INSERT INTO users (username, hashed_password)
                VALUES (%s, %s) RETURNING id;
                """,
                (username, hashed_password.decode("utf-8")),
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except psycopg2.errors.UniqueViolation:
            logger.warning(f"Username '{username}' already exists")
            return None
        except Exception as e:
            logger.error(f"Error inserting user: {e}")
            return None

    def save_message(self, user_id: int, role: str, content: str) -> bool:
        if not self.cursor:
            return False
        try:
            self.cursor.execute(
                """
                INSERT INTO chat_history (user_id, role, content)
                VALUES (%s, %s, %s);
                """,
                (user_id, role, content),
            )
            return True
        except Exception as e:
            logger.error(f"Error saving chat message for user {user_id}: {e}")
            return False

    def get_history(self, user_id: int, limit: int = 10) -> list:
        if not self.cursor:
            return []
        try:
            self.cursor.execute(
                """
                SELECT role, content, timestamp FROM chat_history
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT %s;
                """,
                (user_id, limit),
            )
            rows: list = self.cursor.fetchall()  # Added type annotation
            return rows[::-1]
        except Exception as e:
            logger.error(f"Error fetching chat history for user {user_id}: {e}")
            return []

    def clear_history(self, user_id: int) -> bool:
        if not self.cursor:
            return False
        try:
            self.cursor.execute(
                "DELETE FROM chat_history WHERE user_id = %s;", (user_id,)
            )
            return True
        except Exception as e:
            logger.error(f"Error clearing chat history for user {user_id}: {e}")
            return False


# --- FastAPI Events ---
@app.on_event("startup")
def startup_event():
    global db_manager
    db_manager = DatabaseManager()
    logger.info("Auth service started successfully")


@app.on_event("shutdown")
def shutdown_event():
    if db_manager:
        db_manager.close()
        logger.info("Auth service shutdown complete")


# --- API Endpoints ---


@app.get("/health")
def health_check():
    if db_manager and db_manager.cursor:
        return {
            "status": "ok",
            "service": "auth-service",
            "database": "connected",
            "version": "1.0.0",
        }
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available"
    )


@app.get("/verify/{user_id}")
def verify_user_endpoint(user_id: int):
    """Verify if user exists (for other services to check)"""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    user_data = db_manager.get_user_by_id(user_id)

    if user_data:
        return {"exists": True, "user_id": user_data[0], "username": user_data[1]}
    else:
        return {"exists": False}


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_endpoint(user: UserAuth):
    """Register a new user"""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    if len(user.username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters",
        )

    if len(user.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )

    salt = bcrypt.gensalt(12)
    hashed_password = bcrypt.hashpw(user.password.encode("utf-8"), salt)

    user_id = db_manager.insert_user(user.username, hashed_password)

    if user_id:
        logger.info(f"New user registered: {user.username} (ID: {user_id})")
        return {
            "message": "User registered successfully",
            "user_id": user_id,
            "username": user.username,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed. Username already exists.",
        )


@app.post("/login")
def login_endpoint(user: UserAuth):
    """Login user - returns user_id for session management"""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    user_data = db_manager.get_user(user.username)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user_id, stored_username, stored_hash_text = user_data

    if bcrypt.checkpw(user.password.encode("utf-8"), stored_hash_text.encode("utf-8")):
        logger.info(f"User logged in: {stored_username} (ID: {user_id})")
        return {
            "message": "Login successful",
            "user_id": user_id,
            "username": stored_username,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )


@app.get("/history")
def get_history_endpoint(
    user_id_header: Annotated[Union[str, None], Header(alias="user-id")] = None,
    limit: int = 10,
):
    """Get chat history for a user (optional feature)"""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    if user_id_header is None:  # Added: explicit None check
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'User-Id' header.",
        )

    try:
        user_id = int(user_id_header)
    except ValueError:  # Changed: removed TypeError since we checked for None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 'User-Id' header.",
        )

    if not db_manager.get_user_by_id(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found."
        )

    history = db_manager.get_history(user_id, limit=limit)

    return {
        "user_id": user_id,
        "history": [
            {"role": role, "content": content, "timestamp": str(timestamp)}
            for role, content, timestamp in history
        ],
    }


@app.delete("/history")
def clear_history_endpoint(
    user_id_header: Annotated[Union[str, None], Header(alias="user-id")] = None,
):
    """Clear chat history for a user"""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    if user_id_header is None:  # Added: explicit None check
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'User-Id' header.",
        )

    try:
        user_id = int(user_id_header)
    except ValueError:  # Changed: removed TypeError
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 'User-Id' header.",
        )

    if not db_manager.get_user_by_id(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found."
        )

    if db_manager.clear_history(user_id):
        logger.info(f"Chat history cleared for user {user_id}")
        return {"message": "Chat history cleared successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear chat history",
        )


@app.post("/save-chat")
async def save_chat_endpoint(
    request: ChatQuery,
    user_id_header: Annotated[Union[str, None], Header(alias="user-id")] = None,
):
    """Save a chat message (called by chat service optionally)"""
    if not db_manager or not db_manager.cursor:
        return {"saved": False, "error": "Database not available"}

    if user_id_header is None:  # Added: explicit None check
        return {"saved": False, "error": "Missing user ID"}

    try:
        user_id = int(user_id_header)
    except ValueError:  # Changed: removed TypeError
        return {"saved": False, "error": "Invalid user ID"}

    if db_manager.save_message(user_id, "user", request.query):
        return {"saved": True}
    return {"saved": False}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
