from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter

from app.routes import rest
from app.routes.graphql import schema
from app.config import settings
from app.middleware import GraphQLAuthMiddleware

app = FastAPI(title="TraePy API", description="REST and GraphQL API service")

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
    return {"message": "Welcome to TraePy API service"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)