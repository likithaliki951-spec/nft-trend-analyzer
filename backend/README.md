# NFT Trend Analyzer - FastAPI Backend API

Enterprise REST API providing analytical endpoints, predictive machine learning, and multi-tenant workspace persistence for the NFT Trend Analyzer platform.

## Production Start Command

For production deployment on platforms such as Render, Railway, or containerized hosts, the backend must be executed with **exactly one worker process**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

> **Architecture Note**: The backend utilizes in-memory session caching (`_USER_ACTIVE_DF`) for fast multi-step analytical querying (time-series, regression training, PCA dimensionality reduction, and valuation classification). Running with a single worker ensures that session datasets remain consistent across sequential API calls without introducing paid Redis infrastructure.

## Local Development Startup

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Running Automated Tests

```bash
cd backend
python -m pytest tests/test_backend_api.py -v
```
