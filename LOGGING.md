# TraePy 日志功能说明

## 概述

TraePy 项目已集成完整的日志记录功能，支持多级别日志记录、文件轮转和控制台输出。

## 日志配置

### 配置文件位置
- 主配置: `app/config.py`
- 日志模块: `app/logger.py`

### 配置参数
```python
# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"

# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志文件路径
LOG_FILE = "logs/traepy.log"
```

## 日志功能特性

### 1. 多级别日志记录
- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息记录
- **WARNING**: 警告信息
- **ERROR**: 错误信息
- **CRITICAL**: 严重错误

### 2. 双重输出
- **控制台输出**: 实时查看日志
- **文件输出**: 持久化存储，支持文件轮转

### 3. 文件轮转
- 单个日志文件最大 10MB
- 保留最近 5 个日志文件
- 自动压缩旧日志文件

## 日志记录位置

### 1. HTTP 请求日志
位置: `app/main.py`
```python
# 记录每个HTTP请求的开始和完成
logger.info(f"Request started: {method} {url}")
logger.info(f"Request completed: {method} {url} - Status: {status_code} - Time: {process_time:.4f}s")
```

### 2. Oracle 数据库操作日志
位置: `app/services/oracle_service.py`
```python
# 数据库连接
logger.debug("Attempting to connect to Oracle database")
logger.info("Successfully connected to Oracle database")

# 查询操作
logger.info(f"Executing query: {query[:100]}...")
logger.info(f"Successfully executed query, returned {len(result)} rows")

# 错误处理
logger.error(f"Database connection failed: {str(e)}")
```

### 3. Jenkins 服务操作日志
位置: `app/services/jenkins_service.py`
```python
# 服务初始化
logger.info(f"Initialized Jenkins service with URL: {self.jenkins_url}")

# 任务操作
logger.info(f"Triggering build for Jenkins job: {job_name}")
logger.info(f"Successfully triggered build for job {job_name}, build number: {build_number}")

# 错误处理
logger.error(f"Failed to trigger job build for {job_name}: {str(e)}")
```

### 4. GraphQL 操作日志
位置: `app/routes/graphql.py`
```python
# 查询日志
logger.info("GraphQL query: oracle_tables requested")
logger.info(f"GraphQL query: oracle_tables returned {len(tables)} tables")

# 变更日志
logger.info(f"GraphQL mutation: build_job requested for job {input.job_name}")
logger.info(f"GraphQL mutation: build_job completed for job {input.job_name}, build_number={build_number}")
```

## 日志查看方法

### 1. 实时查看 (Docker 容器)
```bash
# 查看所有容器日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f traepy-api

# 查看最近100行日志
docker-compose logs --tail=100 traepy-api
```

### 2. 查看日志文件
```bash
# 使用提供的日志查看工具
python view_logs.py

# 查看指定行数
python view_logs.py -n 100

# 查看指定文件
python view_logs.py -f logs/traepy.log -n 50
```

### 3. 直接查看文件
```bash
# 查看最新日志
tail -f logs/traepy.log

# 查看最近100行
tail -n 100 logs/traepy.log

# 搜索特定内容
grep "ERROR" logs/traepy.log
```

## 日志文件结构

```
logs/
├── traepy.log          # 当前日志文件
├── traepy.log.1        # 轮转日志文件1
├── traepy.log.2        # 轮转日志文件2
├── traepy.log.3        # 轮转日志文件3
└── traepy.log.4        # 轮转日志文件4
```

## 日志示例

```
2025-08-05 14:27:39,695 - app.services.jenkins_service - INFO - Initialized Jenkins service with URL: http://jenkins:8080
2025-08-05 14:28:00,245 - traepy.main - INFO - Request started: GET http://localhost:8000/@vite/client
2025-08-05 14:28:00,247 - traepy.main - INFO - Request completed: GET http://localhost:8000/@vite/client - Status: 404 - Time: 0.0018s
2025-08-05 14:28:15,123 - app.routes.graphql - INFO - GraphQL query: oracle_tables requested
2025-08-05 14:28:15,456 - app.services.oracle_service - INFO - Successfully connected to Oracle database
2025-08-05 14:28:15,789 - app.routes.graphql - INFO - GraphQL query: oracle_tables returned 5 tables
```

## 开发建议

### 1. 日志级别使用
- **生产环境**: 使用 INFO 或 WARNING 级别
- **开发环境**: 使用 DEBUG 级别
- **测试环境**: 使用 INFO 级别

### 2. 日志内容
- 记录关键业务操作
- 记录错误和异常
- 记录性能相关信息
- 避免记录敏感信息（密码、令牌等）

### 3. 性能考虑
- 合理使用日志级别
- 避免在循环中大量记录日志
- 使用异步日志记录（如需要）

## 故障排查

### 1. 常见问题
- 日志文件权限问题
- 磁盘空间不足
- 日志级别配置错误

### 2. 排查步骤
1. 检查日志配置
2. 验证文件权限
3. 查看磁盘空间
4. 检查日志轮转设置

## 扩展功能

### 1. 集中化日志管理
- 可集成 ELK Stack (Elasticsearch, Logstash, Kibana)
- 可使用 Fluentd 进行日志收集

### 2. 监控告警
- 可集成 Prometheus + Grafana
- 可设置错误日志告警

### 3. 结构化日志
- 可使用 JSON 格式日志
- 便于日志分析和处理