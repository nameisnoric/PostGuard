import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from sqlalchemy import text

from app.database.database import SessionLocal, engine
from app.routers import auth, health, cameras, personal_baselines, sessions, alert_events, session_summaries, users
from app.services.account_deletion import purge_due_accounts
from app.services.avatar_storage import get_avatar_storage


logger = logging.getLogger(__name__)
ACCOUNT_PURGE_INTERVAL_SECONDS = 6 * 60 * 60


def run_account_purge() -> None:
    with SessionLocal() as db:
        result = purge_due_accounts(db, get_avatar_storage())
    if result["purged_ids"] or result["deferred_ids"]:
        logger.info(
            "Account purge completed: purged=%s deferred=%s",
            len(result["purged_ids"]),
            len(result["deferred_ids"]),
        )


async def account_purge_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(run_account_purge)
        except Exception:
            logger.exception("Scheduled account purge failed; it will retry later.")
        await asyncio.sleep(ACCOUNT_PURGE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    purge_task = asyncio.create_task(account_purge_loop())
    try:
        yield
    finally:
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task


app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(cameras.router)
app.include_router(personal_baselines.router)
app.include_router(sessions.router)
app.include_router(alert_events.router)
app.include_router(session_summaries.router)
app.include_router(users.router)

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
