from fastapi import Depends, HTTPException, status, Header
from typing import Optional

from app.config import settings

async def verify_token(x_api_token: Optional[str] = Header(None)):
    """
    Dependency function to verify API Token
    
    Args:
        x_api_token: X-API-Token value in request header
        
    Raises:
        HTTPException: 401 Unauthorized exception when token is invalid or not provided
        
    Returns:
        None: No return value when verification passes
    """
    if x_api_token is None or x_api_token != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None