import logging
import logging.handlers
import os
from pathlib import Path
from app.config import settings

def setup_logger(name: str = None) -> logging.Logger:
    """
    Set up and return a configured logger instance
    
    Args:
        name: logger name, if None then use root logger
    
    Returns:
        configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate configuration
    if logger.handlers:
        return logger
    
    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(settings.LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - decide whether to write to file based on environment and configuration
    if settings.LOG_TO_FILE and settings.ENVIRONMENT == "development":
        # Default log file path for development environment
        log_file = settings.LOG_FILE or "logs/traepy.log"
        
        # Ensure log directory exists
        log_file_path = Path(log_file)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use RotatingFileHandler to avoid log files becoming too large
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    elif settings.LOG_FILE:  # 如果明确指定了日志文件路径，则使用
        # 确保日志目录存在
        log_file_path = Path(settings.LOG_FILE)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用RotatingFileHandler避免日志文件过大
        file_handler = logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# 创建默认的应用logger
app_logger = setup_logger("traepy")