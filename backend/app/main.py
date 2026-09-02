from fastapi import FastAPI
from sqlalchemy import text

from app.database.database import engine


app = FastAPI()


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