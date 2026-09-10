from fastapi import FastAPI
from sqlalchemy import text

from app.database.database import engine
from app.routers import auth

app = FastAPI()

app.include_router(auth.router)

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