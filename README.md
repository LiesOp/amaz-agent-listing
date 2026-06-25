# Amazon Listing Agent Backend

FastAPI backend skeleton for the V1 Amazon listing copy Agent.

## What is included

- FastAPI application setup
- Versioned API router
- Health check at `/health` and `/api/v1/health`
- Async SQLAlchemy database connection
- Admin-managed LangChain model configuration
- Basic application logging

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/init_db.py
cd src
python -m uvicorn listing_agent.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

```text
http://127.0.0.1:8000/health
```

## Configuration

The default `DATABASE_URL` uses local SQLite so the service can start without
PostgreSQL. Set `DATABASE_URL` to a PostgreSQL async URL when a real database is
available:

```text
postgresql+asyncpg://postgres:postgres@localhost:5432/listing_agent
```

Model provider settings are managed from the admin page instead of `.env`.
Open the frontend admin screen, add a model with provider, model name, API key,
optional Base URL, and then enable it. Generation, rewrite, audit, and
competitor analysis use the currently enabled model.

## Database initialization

The app creates missing V1 tables on startup. You can also initialize the local
SQLite database explicitly:

```powershell
python scripts/init_db.py
```

This creates the V1 tables from the simplified database design spec and
seeds the fixed rule source URLs.


```powershell
cd D:\project\mult-agent-listing\frontend
npm install
npm run dev
```

## Docker Compose

The Compose setup builds separate backend and frontend images. The backend
stores SQLite and generated backend files under `D:\data` on the host by
mounting it to `/data` in the container and setting:

```text
DATABASE_URL=sqlite+aiosqlite:////data/listing_agent.db
APP_DATA_DIR=/data
```

Current generated file storage under `APP_DATA_DIR` includes
`competitor_snapshots/`. Existing legacy `rule_snapshots/` data can also be
copied under `D:\data` if you need to keep it.

Start the app:

```powershell
New-Item -ItemType Directory -Force D:\data
docker compose up --build -d
```

Backend third-party Python dependencies are installed from `requirements.txt`
before application source is copied into the image. When only Python source code
changes, Docker can reuse the dependency layer and only reinstall the local
application package.

Then open:

```text
http://127.0.0.1:5173
```

If you want to reuse the existing local database, copy it before the first
container start. To keep existing generated snapshots, copy the current data
directory as well:

```powershell
Copy-Item .\listing_agent.db D:\data\listing_agent.db
Copy-Item .\data\* D:\data\ -Recurse -Force
```
