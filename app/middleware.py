from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from app.config import settings

class GraphQLAuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for GraphQL interface
    
    Verifies if X-API-Token in request header matches configured API_TOKEN
    Only validates /graphql path, health check interface does not require verification
    """
    
    async def dispatch(self, request: Request, call_next):
        # Get request path
        path = request.url.path
        
        # If it's a GraphQL request, verify token (except for health check)
        if path.startswith("/graphql"):
            # Check if request body contains health check query
            is_health_query = False
            
            # Try to parse request body and check if it's a health check query
            if request.method == "POST":
                try:
                    # Read the body without consuming it
                    body_bytes = await request.body()
                    if body_bytes:
                        import json
                        body = json.loads(body_bytes.decode('utf-8'))
                        query = body.get("query", "")
                        # Simple check if it's a health check query
                        if "health" in query and not any(op in query for op in ["oracle", "jenkins", "table", "build"]):
                            is_health_query = True
                        
                        # Recreate the request with the body for downstream processing
                        from starlette.requests import Request as StarletteRequest
                        from starlette.datastructures import Headers
                        
                        # Create a new request with the body data
                        scope = request.scope.copy()
                        
                        async def receive():
                            return {
                                "type": "http.request",
                                "body": body_bytes,
                                "more_body": False,
                            }
                        
                        request = StarletteRequest(scope, receive)
                except:
                    pass
            
            # If not a health check query, verify token
            if not is_health_query:
                token = request.headers.get("X-API-Token")
                if token != settings.API_TOKEN:
                    return JSONResponse(
                        status_code=HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid API Token"},
                    )
        
        # Continue processing request
        response = await call_next(request)
        return response