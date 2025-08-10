# Docker 测试指南

## 问题说明
由于网络连接问题，无法从Docker Hub拉取Python镜像。以下提供几种解决方案：

## 方案1：使用离线Docker镜像
如果您有本地Python镜像，可以修改Dockerfile第一行：
```dockerfile
# 将这行
FROM python:3.9-slim
# 改为您本地的镜像
FROM your-local-python-image
```

## 方案2：使用Docker Desktop内置镜像
```bash
# 查看本地可用镜像
docker images

# 如果有Python镜像，修改Dockerfile使用它
```

## 方案3：完整的Docker测试命令
```bash
# 1. 构建镜像（需要网络连接）
docker-compose build

# 2. 启动服务
docker-compose up -d

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs app

# 5. 进入容器运行测试
docker-compose exec app python -m pytest tests/ -v

# 6. 访问应用
# 前端页面: http://localhost:8000/static/index.html
# API文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health

# 7. 停止服务
docker-compose down
```

## 方案4：使用run_tests.py脚本（推荐）
如果Docker无法使用，可以运行我创建的测试脚本：
```bash
python run_tests.py
```

该脚本会：
1. 设置测试环境变量
2. 安装最小依赖包
3. 运行单元测试
4. 启动演示服务器

## 功能验证清单

### 1. 用户认证功能
- [ ] 用户注册 (POST /api/auth/register)
- [ ] 用户登录 (POST /api/auth/login)
- [ ] 获取用户信息 (GET /api/auth/me)
- [ ] 用户登出 (POST /api/auth/logout)

### 2. WebSocket功能
- [ ] WebSocket连接 (ws://localhost:8000/ws)
- [ ] JWT认证验证
- [ ] 心跳机制
- [ ] 实时消息推送

### 3. 扫描任务功能
- [ ] 触发扫描任务 (POST /api/scan/trigger)
- [ ] 获取任务列表 (GET /api/scan/tasks)
- [ ] 获取任务详情 (GET /api/scan/tasks/{task_id})
- [ ] 获取Jenkins任务 (GET /api/scan/jobs)

### 4. 前端演示页面
- [ ] 用户注册/登录界面
- [ ] WebSocket连接状态显示
- [ ] 任务触发和状态显示
- [ ] 实时消息接收

## 数据库说明
- 使用SQLite数据库（文件存储在./data/app.db）
- 支持用户、扫描任务、WebSocket连接三个表
- 自动创建表结构

## 环境变量配置
```env
DATABASE_URL=sqlite:///./data/app.db
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```