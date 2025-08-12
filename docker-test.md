# Docker Testing Guide

## Problem Description
Due to network connection issues, unable to pull Python images from Docker Hub. The following provides several solutions:

## Solution 1: Use Offline Docker Images
If you have local Python images, you can modify the first line of Dockerfile:
```dockerfile
# Change this line
FROM python:3.9-slim
# To your local image
FROM your-local-python-image
```

## Solution 2: Use Docker Desktop Built-in Images
```bash
# View locally available images
docker images

# If you have Python images, modify Dockerfile to use them
```

## Solution 3: Complete Docker Testing Commands
```bash
# 1. Build image (requires network connection)
docker-compose build

# 2. Start services
docker-compose up -d

# 3. Check service status
docker-compose ps

# 4. View logs
docker-compose logs app

# 5. Enter container to run tests
docker-compose exec app python -m pytest tests/ -v

# 6. Access application
# Frontend page: http://localhost:8000/static/index.html
# API documentation: http://localhost:8000/docs
# Health check: http://localhost:8000/health

# 7. Stop services
docker-compose down
```

## Solution 4: Use run_tests.py Script (Recommended)
If Docker cannot be used, you can run the test script I created:
```bash
python run_tests.py
```

This script will:
1. Set up test environment variables
2. Install minimal dependency packages
3. Run unit tests
4. Start demo server

## Feature Verification Checklist

### 1. User Authentication Features
- [ ] User registration (POST /api/auth/register)
- [ ] User login (POST /api/auth/login)
- [ ] Get user information (GET /api/auth/me)
- [ ] User logout (POST /api/auth/logout)

### 2. WebSocket Features
- [ ] WebSocket connection (ws://localhost:8000/ws)
- [ ] JWT authentication verification
- [ ] Heartbeat mechanism
- [ ] Real-time message push

### 3. Scan Task Features
- [ ] Trigger scan task (POST /api/scan/trigger)
- [ ] Get task list (GET /api/scan/tasks)
- [ ] Get task details (GET /api/scan/tasks/{task_id})
- [ ] Get Jenkins tasks (GET /api/scan/jobs)

### 4. Frontend Demo Page
- [ ] User registration/login interface
- [ ] WebSocket connection status display
- [ ] Task trigger and status display
- [ ] Real-time message reception

## Database Description
- Uses SQLite database (file stored in ./data/app.db)
- Supports three tables: users, scan tasks, WebSocket connections
- Automatically creates table structure

## Environment Variable Configuration
```env
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```