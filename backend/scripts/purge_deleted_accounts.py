"""Purge accounts after their 14-day recovery period.

Run this command from the backend directory on a daily schedule:
    .\.venv\Scripts\python.exe -m scripts.purge_deleted_accounts
"""

from app.database.database import SessionLocal
from app.services.account_deletion import purge_due_accounts
from app.services.avatar_storage import get_avatar_storage


def main() -> None:
    with SessionLocal() as db:
        result = purge_due_accounts(db, get_avatar_storage())
    print(
        f"Purged {len(result['purged_ids'])} account(s); "
        f"deferred {len(result['deferred_ids'])} account(s)."
    )


if __name__ == "__main__":
    main()
