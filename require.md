API Technical Specification Document

1. Project Overview

Python 3.8-based backend API service offering both REST and GraphQL interfaces. Integrates with Oracle databases and Jenkins servers. Fully containerized using Docker and docker-compose for local development.

2. Technology Stack

Python 3.8

FastAPI (REST + GraphQL)

Oracle Database (via cx_Oracle)

Jenkins (via jenkinsapi / requests)

Docker, docker-compose

pytest + coverage (unit testing)

3. Directory Structure

api_project/
├── app/
│   ├── main.py                # Application entry point
│   ├── config.py              # Configuration file
│   ├── routes/
│   │   ├── rest.py           # REST API routes
│   │   └── graphql.py        # GraphQL schema and resolvers
│   ├── services/
│   │   ├── oracle_service.py # Oracle DB logic
│   │   └── jenkins_service.py# Jenkins logic
│   └── models/
│       └── schema.py         # GraphQL schema types
├── tests/
│   └── test_oracle.py        # Unit test
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md

4. Container Configuration

Dockerfile

Minimal Python image with FastAPI server running uvicorn.

docker-compose.yml

Services:

api (depends on oracle and jenkins)

oracle (using gvenzl/oracle-xe)

jenkins (using jenkins/jenkins:lts-jdk11)

5. Testing

All business logic should be covered by unit tests

Run tests with pytest --cov=app

6. Usage Instructions

Use docker-compose up --build to start all services.

API endpoints:

REST: /docs

GraphQL: /graphql

7. Best Practices

Use clear separation of layers (routes, services, models)

Minimal and readable requirements.txt

Centralized configuration via config.py

Keep test coverage for all service logic

Follow semantic versioning and modular service definitions

Ready for CI/CD pipeline integration