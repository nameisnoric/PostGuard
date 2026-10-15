-- Run once in the Supabase SQL editor.
-- The bucket is private. Desktop clients never receive the service-role key.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'avatars',
    'avatars',
    false,
    5242880,
    array['image/webp']
)
on conflict (id) do update set
    public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
