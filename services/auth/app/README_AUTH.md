# Authentication Service

The Authentication Service is a core component of the **MARP Guide RAG Chatbot**. It manages user authentication, registration, and chat history storage. The service interacts with a PostgreSQL database to securely store user credentials and chat history.

---

## Features

- **User Registration:** Allows new users to register with a username and password.
- **User Authentication:** Validates user credentials during login.
- **Chat History Management:** Stores, retrieves, and clears user chat history.
- **Health Monitoring:** Provides a `/health` endpoint to check service and database status.
- **Secure Password Storage:** Uses bcrypt for hashing passwords.

---

## Architecture

1. **User Registration:** Users register with a username and password, which are securely stored in the database.
2. **User Login:** Validates user credentials and returns user details upon successful authentication.
3. **Chat History Management:** Allows users to save, retrieve, and clear their chat history.
4. **Database Integration:** Interacts with a PostgreSQL database for persistent storage.

---

## Prerequisites

- **Python Version:** 3.9 or higher
- **PostgreSQL Database:** Ensure the database is running and accessible.
- **Environment Variables:** Ensure the following are set:
  - `POSTGRES_DB`: Name of the PostgreSQL database.
  - `POSTGRES_USER`: PostgreSQL username.
  - `POSTGRES_PASSWORD`: PostgreSQL password.
  - `POSTGRES_HOST`: PostgreSQL host (e.g., `localhost` or `postgres`).
  - `POSTGRES_PORT`: PostgreSQL port (default: `5432`).

---

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/saeedkabak/MARP-Guide-RAG-Chatbot.git
   cd MARP-Guide-RAG-Chatbot/services/auth
   ```

2. **Install Dependencies:**
   Use `pip` to install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Up PostgreSQL:**
   Ensure PostgreSQL is running and accessible. Update the environment variables if necessary.

4. **Configure Environment Variables:**
   Create a `.env` file or export the required variables:
   ```bash
   export POSTGRES_DB="mydb"
   export POSTGRES_USER="postgres_user"
   export POSTGRES_PASSWORD="mysecretpassword"
   export POSTGRES_HOST="localhost"
   export POSTGRES_PORT="5432"
   ```

5. **Run the Service:**
   ```bash
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## API Endpoints

### 1. **`GET /health`**
- **Description:** Health check endpoint to verify service and database connectivity.
- **Response:**
  ```json
  {
    "status": "ok",
    "service": "auth-service",
    "database": "connected",
    "version": "1.0.0"
  }
  ```

---

### 2. **`POST /register`**
- **Description:** Registers a new user with a username and password.
- **Request Body:**
  ```json
  {
    "username": "john_doe",
    "password": "securepassword"
  }
  ```
- **Response:**
  ```json
  {
    "message": "User registered successfully",
    "user_id": 1,
    "username": "john_doe"
  }
  ```

---

### 3. **`POST /login`**
- **Description:** Authenticates a user with their username and password.
- **Request Body:**
  ```json
  {
    "username": "john_doe",
    "password": "securepassword"
  }
  ```
- **Response:**
  ```json
  {
    "message": "Login successful",
    "user_id": 1,
    "username": "john_doe"
  }
  ```

---

### 4. **`GET /verify/{user_id}`**
- **Description:** Verifies if a user exists by their user ID.
- **Response:**
  ```json
  {
    "exists": true,
    "user_id": 1,
    "username": "john_doe"
  }
  ```

---

### 5. **`GET /history`**
- **Description:** Retrieves the chat history for a user.
- **Headers:**
  - `user-id`: The ID of the user whose history is being retrieved.
- **Query Parameters:**
  - `limit`: Number of messages to retrieve (default: 10).
- **Response:**
  ```json
  {
    "user_id": 1,
    "history": [
      {
        "role": "user",
        "content": "What are the university regulations?",
        "timestamp": "2024-01-15T10:30:00Z"
      },
      {
        "role": "assistant",
        "content": "The university regulations are...",
        "timestamp": "2024-01-15T10:31:00Z"
      }
    ]
  }
  ```

---

### 6. **`DELETE /history`**
- **Description:** Clears the chat history for a user.
- **Headers:**
  - `user-id`: The ID of the user whose history is being cleared.
- **Response:**
  ```json
  {
    "message": "Chat history cleared successfully"
  }
  ```

---

### 7. **`POST /save-chat`**
- **Description:** Saves a chat message for a user.
- **Headers:**
  - `user-id`: The ID of the user saving the message.
- **Request Body:**
  ```json
  {
    "query": "What are the university regulations?"
  }
  ```
- **Response:**
  ```json
  {
    "saved": true
  }
  ```

---

## Database Schema

### Users Table
| Column          | Type                | Description                  |
|------------------|---------------------|------------------------------|
| `id`            | SERIAL PRIMARY KEY  | Unique user ID               |
| `username`      | VARCHAR(50) UNIQUE  | Username                     |
| `hashed_password` | TEXT               | Bcrypt-hashed password       |
| `created_at`    | TIMESTAMP           | Account creation timestamp   |

### Chat History Table
| Column          | Type                | Description                  |
|------------------|---------------------|------------------------------|
| `id`            | SERIAL PRIMARY KEY  | Unique message ID            |
| `user_id`       | INTEGER             | Foreign key to `users` table |
| `role`          | VARCHAR(10)         | Role (`user` or `assistant`) |
| `content`       | TEXT                | Chat message content         |
| `timestamp`     | TIMESTAMP           | Message timestamp            |

---

## Common Issues

1. **Database Connection Error:**
   - Ensure PostgreSQL is running and the environment variables are correctly configured.

2. **Username Already Exists:**
   - Use a unique username during registration.

3. **Invalid Credentials:**
   - Ensure the correct username and password are provided during login.

---

## License

This service is part of the MARP-Guide-RAG-Chatbot project. See the project root for license information.
