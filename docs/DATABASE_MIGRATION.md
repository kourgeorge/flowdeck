# Database and migrations

The backend uses **SQLite** by default. The database file is created in the backend directory (e.g. `backend/flowdeck.db`). You can override the path with the `DATABASE_URL` environment variable (e.g. in `backend/.env`).

On startup, the app runs `init_db()`, which creates any **missing** tables. It does **not** alter existing tables (e.g. add new columns to `users`). For that you need to run migrations.

---

## When to run a migration

- After **pulling code** that adds new tables or new columns to existing tables.
- When you see errors about missing columns or missing tables after an upgrade.

---

## Token economy migration

This migration adds schema required for the token economy (user balance, report creator attribution, view tracking):

- **`users`**: adds `token_balance` (default 1000) and `name` (optional) if missing.
- **`analysis_runs`**: new table (ticker, run_id, creator, earned_tokens).
- **`report_views`**: new table (ticker, run_id, viewer, viewed_at).

Existing users get `token_balance = 1000` when the column is added. Safe to run multiple times (idempotent).

### How to run

From the **repository root** (so the backend is on the Python path):

```bash
cd /path/to/flowdeck
python backend/scripts/migrate_token_economy.py
```

With a virtual environment:

```bash
cd /path/to/flowdeck
source venv/bin/activate   # or: conda activate flowdeck
python backend/scripts/migrate_token_economy.py
```

If your database is not the default `backend/flowdeck.db`, set `DATABASE_URL` before running:

```bash
export DATABASE_URL=sqlite:////opt/flowdeck/data/flowdeck.db
python backend/scripts/migrate_token_economy.py
```

### Example output

```
users.token_balance already exists
users.name already exists
Token economy migration done.
```

Or on first run:

```
Added users.token_balance (default 1000)
Added users.name
Token economy migration done.
```

---

## Production / deployment

When upgrading a deployed instance:

1. Pull the latest code.
2. Install any new Python dependencies.
3. **Run the migration** (as the user that owns the database file, so the process can write to it):

   ```bash
   cd /opt/flowdeck
   source venv/bin/activate
   python backend/scripts/migrate_token_economy.py
   ```

4. Restart the backend service.

If the backend runs as `www-data`, run the migration as `www-data` or ensure the DB file and directory are writable by the user that runs the script:

```bash
sudo -u www-data /opt/flowdeck/venv/bin/python /opt/flowdeck/backend/scripts/migrate_token_economy.py
```

(Set `DATABASE_URL` in the environment if your DB path differs.)

---

## Admin flag migration

This migration adds an `is_admin` column to the `users` table (default `false`). Optionally, set the first admin by email using the `ADMIN_EMAIL` environment variable.

### How to run

From the repository root:

```bash
python backend/scripts/migrate_admin_flag.py
```

To designate an admin user by email:

```bash
ADMIN_EMAIL=admin@example.com python backend/scripts/migrate_admin_flag.py
```

Safe to run multiple times (idempotent). If `is_admin` already exists, the column is skipped; the update for `ADMIN_EMAIL` runs each time so you can change who is admin.
