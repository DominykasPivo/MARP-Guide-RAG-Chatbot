"""
Shared authentication dependency for all microservices.
Validates user authentication by checking the User-Id header against the auth service.
"""

import logging
import os
from typing import Annotated, Optional

import httpx
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth:8006")


async def verify_user(
    user_id: Annotated[Optional[str], Header(alias="user-id")] = None,
) -> int:
    """
    Verifies user exists by calling auth service.

    Args:
        user_id: User ID from the custom 'user-id' header

    Returns:
        int: Validated user ID

    Raises:
        HTTPException: 401 if user_id is missing, invalid, or user doesn't exist
        HTTPException: 503 if auth service is unavailable
    """
    if not user_id:
        raise HTTPException(
            status_code=401, detail="Missing User-Id header. Please login first."
        )

    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid User-Id format. Must be an integer."
        )

    # Verify user exists in auth service database
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/verify/{user_id_int}", timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("exists"):
                    logger.info(f"User {user_id_int} authenticated successfully")
                    return user_id_int
                else:
                    raise HTTPException(
                        status_code=401, detail="User not found. Please login again."
                    )
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=401, detail="User not found. Please login again."
                )
            else:
                raise HTTPException(status_code=503, detail="Auth service error")

        except httpx.RequestError as e:
            logger.error(f"Auth service connection error: {e}")
            raise HTTPException(
                status_code=503,
                detail="Auth service unavailable. Please try again later.",
            )
