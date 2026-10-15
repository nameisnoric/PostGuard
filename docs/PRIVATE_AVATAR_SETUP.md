# Private Profile Avatar Setup

PostGuard stores profile photos in a private Supabase Storage bucket. Desktop
clients never receive a Supabase key or a public object URL. Every upload and
download goes through the authenticated FastAPI backend.

## One-time Supabase setup

1. Open the Supabase SQL editor for the PostGuard project.
2. Run `backend/scripts/sql/setup_private_avatar_storage.sql` to create or correct the
   private `avatars` bucket.
3. Copy `backend/.env.example` values into `backend/.env` and set:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_AVATAR_BUCKET=avatars`
4. Never add the service-role key to the desktop environment or Git.

## Database migration

Run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

This adds nullable `users.avatar_path`. The database stores only the private
object path; image bytes stay in Storage.

## Request flow

- `PUT /users/me/avatar` accepts an authenticated JPG/PNG request body up to
  5 MB, verifies the actual image, center-crops it, removes metadata and stores
  a 400x400 WebP object under `users/{user_id}/{uuid}.webp`.
- `GET /users/me/avatar` proxies only the current user's object and returns it
  with a private cache header.
- `DELETE /users/me/avatar` removes the current user's reference and object.
- Replacing an avatar writes the new object first, commits its path, and then
  removes the previous object.
