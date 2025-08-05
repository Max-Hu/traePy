from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter
import time

from app.routes import rest
from app.routes.graphql import schema
from app.config import settings
from app.middleware import GraphQLAuthMiddleware
from app.logger import setup_logger

# 初始化日志器
logger = setup_logger("traepy.main")

app = FastAPI(title="TraePy API", description="REST and GraphQL API service")

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 记录请求开始
    logger.info(f"Request started: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # 记录请求完成
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GraphQL authentication middleware
app.add_middleware(GraphQLAuthMiddleware)

# Register REST routes
app.include_router(rest.router, prefix="/api")

# Register GraphQL routes
graphql_router = GraphQLRouter(schema)
app.include_router(graphql_router, prefix="/graphql")

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to TraePy API service"}

if __name__ == "__main__":
    logger.info(f"Starting TraePy API server on port {settings.PORT}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)