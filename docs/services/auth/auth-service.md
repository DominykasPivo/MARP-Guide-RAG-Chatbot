### Responsibility:
Handles authentcation, authorization of users and services.

### Data Owned:

*   User accounts + permissions.
*   API tokens

### API Endpoints:
-   [POST] /auth/login - Authenticate user
-   [POST] /auth/logout - Revoke active session token
-   [POST] /auth/authenticate - Authenticate the users token and return user info
