from fastapi import FastAPI
from sqlalchemy import text

from app.database.database import engine
from app.routers import auth, health, cameras, personal_baselines, sessions, alert_events, session_summaries

app = FastAPI()

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(cameras.router)
app.include_router(personal_baselines.router)
app.include_router(sessions.router)
app.include_router(alert_events.router)
app.include_router(session_summaries.router)

@app.get("/")
def root():
    return {"message": "PostGuard API is running"}

@app.get("/db-test")
def db_test():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            value = result.scalar()

        return {
            "status": "success",
            "database": "PostgreSQL",
            "result": value
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }