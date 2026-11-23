# Fintech Sandbox API - Deployment & Infrastructure Guide

## 1. Local Deployment with Docker & Docker Compose

### Prerequisites
- Docker & Docker Compose installed.

### Quick Start
```bash
# 1. Clone repository
git clone <repo_url>
cd Fintech-Sandbox-API

# 2. Copy environment file
cp .env.example .env

# 3. Build and launch services (FastAPI + PostgreSQL)
docker compose up --build -d

# 4. Check container health
docker compose ps
curl http://localhost:8000/health
```

The service will be live at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`
- **Health Check:** `http://localhost:8000/health`
- **Readiness Check:** `http://localhost:8000/ready`

---

## 2. Production Cloud Deployment (Render / Railway)

The service is packaged as a standard stateless 12-factor application with PostgreSQL storage.

### Environment Variables
Configure the following in your hosting provider's dashboard:

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg://user:password@host:5432/dbname` |
| `SECRET_KEY` | 32+ character random secret for signing tokens | `super_secure_random_production_secret_key_12345` |
| `ENVIRONMENT` | Deployment environment | `production` |
| `DEBUG` | Enable debug logs | `false` |
| `HOST` | Bind host | `0.0.0.0` |
| `PORT` | Listening port (assigned by platform) | `8000` |

### Database Migrations on Cloud
During container startup, migrations automatically execute before Uvicorn starts:
```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

