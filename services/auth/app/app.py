import psycopg2
import bcrypt
import os
from typing import Optional, Annotated, Union 
from fastapi import FastAPI, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware # <<< ADDED: CORS Import
from pydantic import BaseModel
import logging
import sys

# --- Configuration & Logging ---
DB_NAME = os.environ.get("POSTGRES_DB", "mydb")
DB_USER = os.environ.get("POSTGRES_USER", "postgres_user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "mysecretpassword")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger('auth')

# --- FastAPI Setup ---
app = FastAPI(title="MARP Authentication Service", version="1.0.0")

# *** CORS CONFIGURATION (Fixes "Network Error: Could not connect to the API" from local HTML file) ***
origins = [
    "http://localhost",
    "http://localhost:8006", # Must match the port Docker exposes
    "http://localhost:8080",  # <<< NEW: Allows connections from the local web server
    "null", # CRITICAL: Allows local files (file:///) to connect to the API
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "User-Id"], # Allows the custom User-Id header from the frontend
)
# ---------------------------------------------------------------------------------------------------

db_manager = None # Global variable to hold the database connection

# Pydantic Models for Request Body Validation
class UserAuth(BaseModel):
    username: str
    password: str

# Pydantic Model for Chat Request Body
class ChatQuery(BaseModel):
    query: str


# --- Database Manager (Cleaned and Updated) ---
class DatabaseManager:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
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
        """Creates the users and chat_history tables."""
        if not self.cursor: return
        try:
            # 1. Users Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL
                );
            """)
            
            # 2. Chat History Table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(10) NOT NULL, -- 'user' or 'assistant'
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("Tables 'users' and 'chat_history' ensured to exist.")
        except Exception as e:
            logger.error(f"Error creating table: {e}")

    def get_user(self, username: str) -> Optional[tuple]:
        if not self.cursor: return None
        try:
            self.cursor.execute(
                "SELECT id, username, hashed_password FROM users WHERE username = %s;",
                (username,)
            )
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Error fetching user: {e}")
            return None

    def insert_user(self, username: str, hashed_password: bytes) -> bool:
        if not self.cursor: return False
        try:
            # Store hash as string
            self.cursor.execute(
                "INSERT INTO users (username, hashed_password) VALUES (%s, %s);",
                (username, hashed_password.decode('utf-8'))
            )
            return True
        except psycopg2.errors.UniqueViolation:
            return False
        except Exception as e:
            logger.error(f"Error inserting user: {e}")
            return False

    def save_message(self, user_id: int, role: str, content: str) -> bool:
        """Saves a message (query or response) to the history."""
        if not self.cursor: return False
        try:
            self.cursor.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (%s, %s, %s);",
                (user_id, role, content)
            )
            return True
        except Exception as e:
            logger.error(f"Error saving chat message for user {user_id}: {e}")
            return False

    def get_history(self, user_id: int, limit: int = 10) -> list[tuple]:
        """Retrieves the last 'limit' messages for a user."""
        if not self.cursor: return []
        try:
            self.cursor.execute(
                """
                SELECT role, content FROM chat_history
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT %s;
                """,
                (user_id, limit)
            )
            # Reverse the list so the conversation is chronological
            return self.cursor.fetchall()[::-1]
        except Exception as e:
            logger.error(f"Error fetching chat history for user {user_id}: {e}")
            return []
    
    def get_user_by_id(self, user_id: int) -> Optional[tuple]:
        if not self.cursor: return None
        try:
            self.cursor.execute(
                "SELECT id, username FROM users WHERE id = %s;",
                (user_id,)
            )
            return self.cursor.fetchone()
        except Exception as e:
            logger.error(f"Error fetching user by ID: {e}")
            return None

# --- FastAPI Events (Database connection management) ---

@app.on_event("startup")
def startup_event():
    """Initializes the database connection manager."""
    global db_manager
    db_manager = DatabaseManager()

@app.on_event("shutdown")
def shutdown_event():
    """Closes the database connection gracefully."""
    if db_manager:
        db_manager.close()

# --- API Endpoints ---

@app.get("/health")
def health_check():
    """Checks the application status and database connection."""
    if db_manager and db_manager.cursor:
        return {"status": "ok", "database": "connected"}
    
    # Returning a 503 for Service Unavailable if the database is down
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                        detail="Database not available")


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register_endpoint(user: UserAuth):
    """Registers a new user."""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")
    
    # Hash password
    salt = bcrypt.gensalt(12)
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), salt)

    if db_manager.insert_user(user.username, hashed_password):
        return {"message": "User registered successfully"}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration failed. Username might exist.")

@app.post("/login")
def login_endpoint(user: UserAuth):
    """Authenticates a user."""
    if not db_manager or not db_manager.cursor:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")

    user_data = db_manager.get_user(user.username)
    if not user_data:
        # Generic error message for security
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    user_id, stored_username, stored_hash_text = user_data
    
    # Verify password
    if bcrypt.checkpw(user.password.encode('utf-8'), stored_hash_text.encode('utf-8')):
        return {"message": "Login successful", "user_id": user_id}
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    
# --- Chat History Endpoint ---

@app.post("/chat")
async def chat_endpoint(
    request: ChatQuery,
    # Reads the custom header 'user-id' from the request
    user_id_header: Annotated[Union[str, None], Header(alias="user-id")] = None 
):
    """
    Handles a chat query, retrieves user history, and saves the new message.
    """
    if not db_manager or not db_manager.cursor:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not available")
    
    # 1. READ AND VALIDATE USER ID
    try:
        user_id = int(user_id_header)
    except (TypeError, ValueError):
        # Return 401 if the user ID is missing or not a valid number
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid 'User-Id' header.")
        
    user_query = request.query
    
    # 2. RETRIEVE HISTORY (last 5 messages)
    history = db_manager.get_history(user_id, limit=5)
    
    # 3. CONSTRUCT CONTEXT for LLM
    # The frontend is sending the ID, but we should quickly check if the user exists
    if not db_manager.get_user_by_id(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
        
    context_messages = [f"{role.capitalize()}: {content}" for role, content in history]
    context = "\n".join(context_messages)
    
    # This is the full prompt your actual LLM/RAG system would use
    llm_prompt = f"Previous conversation context:\n{context}\n\nUser's new question: {user_query}"

    # 4. SIMULATE LLM RESPONSE (***REPLACE THIS WITH YOUR ACTUAL LLM/RAG CALL***)
    bot_response = f"Response for user {user_id}. You asked: '{user_query}'. History used: {len(history)} messages."
    
    # 5. SAVE NEW INTERACTION
    db_manager.save_message(user_id, "user", user_query)
    db_manager.save_message(user_id, "assistant", bot_response)

    return {"response": bot_response}
