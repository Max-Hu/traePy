# TraePy API Service

Python 3.8-based backend API service providing REST and GraphQL interfaces, integrated with Oracle database and Jenkins server.

## Technology Stack

- Python 3.8
- FastAPI (REST + GraphQL)
- Oracle Database (via cx_Oracle)
- Jenkins (via requests)
- Docker, docker-compose
- pytest + coverage (unit testing)

## Directory Structure

```
api_project/
├── app/
│   ├── main.py                # Application entry point
│   ├── config.py              # Configuration file
│   ├── routes/
│   │   ├── rest.py           # REST API routes
│   │   └── graphql.py        # GraphQL schema and resolvers
│   ├── services/
│   │   ├── oracle_service.py # Oracle database logic
│   │   └── jenkins_service.py# Jenkins logic
│   └── models/
│       └── schema.py         # GraphQL schema types
├── tests/
│   ├── test_oracle.py        # Oracle service unit tests
│   └── test_jenkins.py       # Jenkins service unit tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Container Configuration

### Dockerfile

Minimal Python 3.8 image with Oracle client and FastAPI server running uvicorn.

### docker-compose.yml

Services:
- api (depends on oracle and jenkins)
- oracle (using gvenzl/oracle-xe)
- jenkins (using jenkins/jenkins:lts-jdk11)

## Testing

All business logic is covered by unit tests:

```bash
pytest --cov=app
```

## Usage Instructions

Start all services using docker-compose:

```bash
docker-compose up --build
```

API endpoints:
- REST API documentation: http://localhost:8000/docs
- GraphQL interface: http://localhost:8000/graphql

## REST API Endpoints

- `GET /api/health` - Health check (no authentication required)
- `GET /api/oracle/tables` - Get list of tables in Oracle database (authentication required)
- `GET /api/oracle/tables/{table_name}/data` - Get data from specified table (authentication required)
- `GET /api/jenkins/jobs` - Get list of jobs on Jenkins server (authentication required)
- `POST /api/jenkins/jobs/{job_name}/build` - Trigger Jenkins job build (authentication required)

## API Authentication

All API endpoints require authentication via API Token, except for the health check interface.

### REST API Authentication

Add `X-API-Token` field in request headers with the configured API Token value.

```
X-API-Token: traepy-static-token
```

### GraphQL Authentication

Similarly, add `X-API-Token` field in request headers with the configured API Token value. Health check queries do not require authentication.

```
X-API-Token: traepy-static-token
```

You can customize the Token value through the `API_TOKEN` environment variable.

## GraphQL Query Examples

Get health status:
```graphql
query {
  health
}
```

Get Oracle table list:
```graphql
query {
  oracleTables {
    name
  }
}
```

Get table data:
```graphql
query {
  tableData(tableName: "EMPLOYEES", limit: 10, offset: 0) {
    tableName
    data
  }
}
```

Trigger Jenkins job build:
```graphql
mutation {
  buildJob(jobName: "test-job", parameters: "{\"param1\": \"value1\"}") {
    buildResult {
      jobName
      buildNumber
      status
    }
  }
}
```

## Best Practices

- Use clear separation of layers (routes, services, models)
- Keep requirements.txt minimal and readable
- Centralize configuration via config.py
- Maintain test coverage for all service logic
- Follow semantic versioning and modular service definitions
- Ready for CI/CD pipeline integration
