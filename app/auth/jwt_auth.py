from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import settings
from app.models.database import User
from app.database import get_db
from app.logger import setup_logger

logger = setup_logger(__name__)

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        bool: True if password matches, False otherwise
        
    Raises:
        ValueError: If either parameter is empty or None
    """
    if not plain_password or not hashed_password:
        logger.error("Password verification failed: empty password or hash")
        raise ValueError("Password and hash cannot be empty")
    
    try:
        result = pwd_context.verify(plain_password, hashed_password)
        logger.debug(f"Password verification result: {result}")
        return result
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False

def get_password_hash(password: str) -> str:
    """Generate password hash
    
    Args:
        password: Plain text password to hash
        
    Returns:
        str: Hashed password
        
    Raises:
        ValueError: If password is empty or too weak
    """
    if not password:
        logger.error("Cannot hash empty password")
        raise ValueError("Password cannot be empty")
    
    if len(password) < 6:
        logger.warning("Weak password detected (less than 6 characters)")
    
    try:
        hashed = pwd_context.hash(password)
        logger.debug("Password successfully hashed")
        return hashed
    except Exception as e:
        logger.error(f"Password hashing failed: {str(e)}")
        raise ValueError(f"Failed to hash password: {str(e)}")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token
    
    Args:
        data: Dictionary containing token payload data
        expires_delta: Optional custom expiration time delta
        
    Returns:
        str: Encoded JWT token
        
    Raises:
        ValueError: If data is empty or invalid
    """
    if not data:
        logger.error("Cannot create token with empty data")
        raise ValueError("Token data cannot be empty")
    
    if "sub" not in data:
        logger.warning("Token created without 'sub' claim, this may cause authentication issues")
    
    to_encode = data.copy()
    
    # Handle token expiration - this is the logic at line 33
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
        logger.debug(f"Creating token with custom expiration: {expire}")
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.debug(f"Creating token with default expiration: {expire}")
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        logger.debug(f"Successfully created JWT token for subject: {data.get('sub', 'unknown')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to encode JWT token: {str(e)}")
        raise ValueError(f"Failed to create token: {str(e)}")

def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token
    
    Args:
        token: JWT token string to verify
        
    Returns:
        Dict[str, Any]: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid, expired, or malformed
        ValueError: If token is empty
    """
    if not token or not token.strip():
        logger.error("Token verification failed: empty token")
        raise ValueError("Token cannot be empty")
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        logger.debug(f"Successfully verified token for subject: {payload.get('sub', 'unknown')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token verification failed: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.JWSError, jwt.JWTClaimsError) as e:
        logger.error(f"Token verification failed: invalid token - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """获取当前用户"""
    try:
        payload = verify_token(credentials.credentials)
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password
    
    Args:
        db: Database session
        username: Username to authenticate
        password: Plain text password
        
    Returns:
        Optional[User]: User object if authentication successful, None otherwise
        
    Raises:
        ValueError: If username or password is empty
    """
    if not username or not username.strip():
        logger.error("Authentication failed: empty username")
        raise ValueError("Username cannot be empty")
    
    if not password:
        logger.error("Authentication failed: empty password")
        raise ValueError("Password cannot be empty")
    
    try:
        user = db.query(User).filter(User.username == username.strip()).first()
        if not user:
            logger.info(f"Authentication failed: user '{username}' not found")
            return None
        
        if not user.is_active:
            logger.info(f"Authentication failed: user '{username}' is inactive")
            return None
        
        if not verify_password(password, user.hashed_password):
            logger.info(f"Authentication failed: invalid password for user '{username}'")
            return None
        
        logger.info(f"User '{username}' authenticated successfully")
        return user
    except Exception as e:
        logger.error(f"Authentication error for user '{username}': {str(e)}")
        return None