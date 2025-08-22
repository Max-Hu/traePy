from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter
import time
import os

from app.routes import rest, monitor
from app.routes.graphql import schema
from app.routes import auth, websocket, scan
from app.config import settings
from app.middleware import GraphQLAuthMiddleware
from app.logger import setup_logger
from app.database import create_tables
from app.services.monitor_service import monitor_service

# Initialize logger
logger = setup_logger("traepy.main")

app = FastAPI(title="TraePy API", description="REST and GraphQL API service")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.warning(f"Static directory not found: {static_dir}")

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request start
    logger.info(f"Request started: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log request completion
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.test.com",
        "http://www.test.com",
        "https://test.com",
        "http://test.com",
        "http://localhost:3000",  # Development environment
        "http://localhost:8080",  # Development environment
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add GraphQL authentication middleware
app.add_middleware(GraphQLAuthMiddleware)

# Create database tables
try:
    create_tables()
except Exception as e:
    logger.error(f"Failed to create database tables: {str(e)}")

# Register REST routes
app.include_router(rest.router, prefix="/api")

# Register authentication routes
app.include_router(auth.router, prefix="/auth")

# Register WebSocket routes
app.include_router(websocket.router, prefix="/ws")

# Register scan task routes
app.include_router(scan.router, prefix="/api/scan")

# Register monitoring routes
app.include_router(monitor.router, prefix="/api/monitor")

# Register GraphQL routes
graphql_router = GraphQLRouter(schema)
app.include_router(graphql_router, prefix="/graphql")

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    await monitor_service.start_service()
    logger.info("Application startup completed")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    if monitor_service.scheduler.running:
        monitor_service.scheduler.shutdown()
    logger.info("Application shutdown completed")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to TraePy API service"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "TraePy API is running"}

if __name__ == "__main__":
    logger.info(f"Starting TraePy API server on port {settings.PORT}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)