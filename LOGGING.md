# TraePy Logging Feature Documentation

## Overview

The TraePy project has integrated comprehensive logging functionality, supporting multi-level logging, file rotation, and console output.

## Logging Configuration

### Configuration File Locations
- Main configuration: `app/config.py`
- Logging module: `app/logger.py`

### Configuration Parameters
```python
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = "INFO"

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Log file path
LOG_FILE = "logs/traepy.log"
```

## Logging Features

### 1. Multi-level Logging
- **DEBUG**: Detailed debugging information
- **INFO**: General information logging
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical errors

### 2. Dual Output
- **Console Output**: Real-time log viewing
- **File Output**: Persistent storage with file rotation support

### 3. File Rotation
- Maximum 10MB per log file
- Keep the latest 5 log files
- Automatic compression of old log files

## Logging Locations

### 1. HTTP Request Logs
Location: `app/main.py`
```python
# Log the start and completion of each HTTP request
logger.info(f"Request started: {method} {url}")
logger.info(f"Request completed: {method} {url} - Status: {status_code} - Time: {process_time:.4f}s")
```

### 2. Oracle Database Operation Logs
Location: `app/services/oracle_service.py`
```python
# Database connection
logger.debug("Attempting to connect to Oracle database")
logger.info("Successfully connected to Oracle database")

# Query operations
logger.info(f"Executing query: {query[:100]}...")
logger.info(f"Successfully executed query, returned {len(result)} rows")

# Error handling
logger.error(f"Database connection failed: {str(e)}")
```

### 3. Jenkins Service Operation Logs
Location: `app/services/jenkins_service.py`
```python
# Service initialization
logger.info(f"Initialized Jenkins service with URL: {self.jenkins_url}")

# Job operations
logger.info(f"Triggering build for Jenkins job: {job_name}")
logger.info(f"Successfully triggered build for job {job_name}, build number: {build_number}")

# Error handling
logger.error(f"Failed to trigger job build for {job_name}: {str(e)}")
```

### 4. GraphQL Operation Logs
Location: `app/routes/graphql.py`
```python
# Query logs
logger.info("GraphQL query: oracle_tables requested")
logger.info(f"GraphQL query: oracle_tables returned {len(tables)} tables")

# Mutation logs
logger.info(f"GraphQL mutation: build_job requested for job {input.job_name}")
logger.info(f"GraphQL mutation: build_job completed for job {input.job_name}, build_number={build_number}")
```

## Log Viewing Methods

### 1. Real-time Viewing (Docker Containers)
```bash
# View all container logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f traepy-api

# View last 100 lines of logs
docker-compose logs --tail=100 traepy-api
```

### 2. View Log Files
```bash
# Use the provided log viewing tool
python view_logs.py

# View specified number of lines
python view_logs.py -n 100

# View specified file
python view_logs.py -f logs/traepy.log -n 50
```

### 3. Direct File Viewing
```bash
# View latest logs
tail -f logs/traepy.log

# View last 100 lines
tail -n 100 logs/traepy.log

# Search for specific content
grep "ERROR" logs/traepy.log
```

## Log File Structure

```
logs/
├── traepy.log          # Current log file
├── traepy.log.1        # Rotated log file 1
├── traepy.log.2        # Rotated log file 2
├── traepy.log.3        # Rotated log file 3
└── traepy.log.4        # Rotated log file 4
```

## Log Examples

```
2025-08-05 14:27:39,695 - app.services.jenkins_service - INFO - Initialized Jenkins service with URL: http://jenkins:8080
2025-08-05 14:28:00,245 - traepy.main - INFO - Request started: GET http://localhost:8000/@vite/client
2025-08-05 14:28:00,247 - traepy.main - INFO - Request completed: GET http://localhost:8000/@vite/client - Status: 404 - Time: 0.0018s
2025-08-05 14:28:15,123 - app.routes.graphql - INFO - GraphQL query: oracle_tables requested
2025-08-05 14:28:15,456 - app.services.oracle_service - INFO - Successfully connected to Oracle database
2025-08-05 14:28:15,789 - app.routes.graphql - INFO - GraphQL query: oracle_tables returned 5 tables
```

## Development Recommendations

### 1. Log Level Usage
- **Production Environment**: Use INFO or WARNING level
- **Development Environment**: Use DEBUG level
- **Testing Environment**: Use INFO level

### 2. Log Content
- Record key business operations
- Record errors and exceptions
- Record performance-related information
- Avoid logging sensitive information (passwords, tokens, etc.)

### 3. Performance Considerations
- Use log levels appropriately
- Avoid excessive logging in loops
- Use asynchronous logging (if needed)

## Troubleshooting

### 1. Common Issues
- Log file permission problems
- Insufficient disk space
- Incorrect log level configuration

### 2. Troubleshooting Steps
1. Check log configuration
2. Verify file permissions
3. Check disk space
4. Check log rotation settings

## Extended Features

### 1. Centralized Log Management
- Can integrate ELK Stack (Elasticsearch, Logstash, Kibana)
- Can use Fluentd for log collection

### 2. Monitoring and Alerting
- Can integrate Prometheus + Grafana
- Can set up error log alerts

### 3. Structured Logging
- Can use JSON format logs
- Facilitates log analysis and processing