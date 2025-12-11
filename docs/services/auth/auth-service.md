### Service Name: Auth

### Responsibility:
Manages user authentication, registration, and session handling. Ensures secure access to the system through JWT-based authentication.

### Data Owned:
- User credentials (hashed passwords).
- User session data.
- Chat history linked to authenticated users.

### API Endpoints:
- **[GET] /health** – Health check endpoint: verifies service and database connectivity.
- **[POST] /register** – Registers a new user with a username and password.
- **[POST] /login** – Authenticates a user and issues a JWT token.
