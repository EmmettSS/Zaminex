# Zaminex Real Estate CRM

A simple real estate CRM: **Django** backend, **React** frontend, **PostgreSQL** database.
The whole interface is Persian (RTL).

---

## Contents

1. [Quick guide: which situation am I in?](#1-quick-guide-which-situation-am-i-in)
2. [Requirements](#2-requirements)
3. [Install PostgreSQL](#3-install-postgresql)
4. [Create the database user and database (once)](#4-create-the-database-user-and-database-once)
5. [Default accounts](#5-default-accounts)
6. [`zaminex_backup.sql` and `seed_data.json`](#6-zaminex_backupsql-and-seed_datajson)
7. [Situation 1: you got the project for the first time](#7-situation-1-you-got-the-project-for-the-first-time)
8. [Situation 2: you worked on the project and want to save it](#8-situation-2-you-worked-on-the-project-and-want-to-save-it)
9. [Situation 3: you have the project and receive a new version of the code](#9-situation-3-you-have-the-project-and-receive-a-new-version-of-the-code)
10. [Restore a backup (moving to a new computer or server)](#10-restore-a-backup-moving-to-a-new-computer-or-server)
11. [The `resync_sequences` command — why and when](#11-the-resync_sequences-command--why-and-when)
12. [Build the frontend (only if you edit React)](#12-build-the-frontend-only-if-you-edit-react)
13. [Run the project](#13-run-the-project)
14. [If something goes wrong](#14-if-something-goes-wrong)
15. [Final checklist](#15-final-checklist)

---

## 1. Quick guide: which situation am I in?

| Your situation | Go to | What you do, in one sentence |
|---|---|---|
| I just received the project | [Situation 1](#7-situation-1-you-got-the-project-for-the-first-time) | Install Python and PostgreSQL, then start the project |
| The project works and I have entered real data | [Situation 2](#8-situation-2-you-worked-on-the-project-and-want-to-save-it) | Make one backup file called `zaminex_backup.sql` |
| I received a new version of the code | [Situation 3](#9-situation-3-you-have-the-project-and-receive-a-new-version-of-the-code) | Back up first, then replace the code and run `migrate` |
| I want to continue on another computer or server | [Restore a backup](#10-restore-a-backup-moving-to-a-new-computer-or-server) | Run 5 commands, one after another |
| I see `duplicate key value violates unique constraint` | [`resync_sequences`](#11-the-resync_sequences-command--why-and-when) | Run one command and the problem is fixed |
| `migrate` stops with `relation "…" already exists` | [`repair_migrations`](#error-relation--already-exists-when-running-migrate) | Run one command and the problem is fixed |

---

## 2. Requirements

- **Python 3.11** or newer
- **PostgreSQL 18** or newer
- **Node.js 18** or newer — *only* if you want to change the look of the project (React). It is not needed to run the project.

---

## 3. Install PostgreSQL

### Windows

1. Download the installer from:
   https://sbp.enterprisedb.com/getfile.jsp?fileid=1260302
2. Run the installer. When it asks for a password, use **`zaminex`**.
3. At the end of the installation, **uncheck** the **StackBuilder** checkbox.
4. To make the `psql` command available everywhere, open **PowerShell as Administrator** and run:
   ```powershell
   setx PATH "$env:PATH;C:\Program Files\PostgreSQL\18\bin" /M
   ```
   Close PowerShell, open it again and check:
   ```powershell
   psql --version
   ```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

To make the `psql` command available everywhere:

```bash
echo 'export PATH=$PATH:/usr/lib/postgresql/18/bin' >> ~/.bashrc
source ~/.bashrc
psql --version
```

If you did not set a password during the installation, this sets it to `zaminex`:

```bash
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'zaminex';"
```

### Mac

1. Download the installer: https://sbp.enterprisedb.com/getfile.jsp?fileid=1260319
2. Run the installer. Set the password to **`zaminex`** and uncheck the StackBuilder checkbox.
3. To make the `psql` command available everywhere:
   ```bash
   echo 'export PATH=$PATH:/Library/PostgreSQL/18/bin' >> ~/.zshrc
   source ~/.zshrc
   psql --version
   ```

---

## 4. Create the database user and database (once)

If you have just installed everything, run these two commands **once**. If they already exist, do not run them again.

```bash
psql -U postgres -c "CREATE USER zaminex WITH PASSWORD 'zaminex';"
psql -U postgres -c "CREATE DATABASE zaminex OWNER zaminex;"
```

> If Windows asks for a password, it is the one you chose while installing PostgreSQL (`zaminex`).

---

## 5. Default accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | `ZaminexAdmin` | `SSASAZPT4` |
| Consultant | `consultant` | `123456789` |

---

## 6. `zaminex_backup.sql` and `seed_data.json`

These two files look similar but do completely different jobs:

| File | What is inside | When to use it |
|---|---|---|
| `zaminex_backup.sql` | **All your real data**: properties, consultants, tasks, tickets, settings, and more | Moving your data to another computer/server, or bringing it back after a crash |
| `ZaminexB/fixtures/seed_data.json` | Only the **basic reference data**: property types, usages, provinces/cities/districts, company settings (234 items) | Only when the database is **empty** and you have no backup |

Three golden rules:

- **First time:** if you have `zaminex_backup.sql`, restore it (best option). Only if you have no backup and start from nothing, use `seed_data.json`.
- **Never replace `seed_data.json` with real data.** That file must stay basic data only.
- **When you get a new version of the project, do not load `seed_data.json` again.** Your database stays as it is; you only need `migrate`.

---

## 7. Situation 1: you got the project for the first time

### Route A (recommended): you have `zaminex_backup.sql`

Create the user and database first ([section 4](#4-create-the-database-user-and-database-once)), then run **exactly** these commands, in this order:

```bash
cd ZaminexB
pip install -r requirements.txt
```

```bash
psql -U postgres -c "DROP DATABASE IF EXISTS zaminex WITH (FORCE);"
psql -U postgres -c "CREATE DATABASE zaminex OWNER zaminex;"
psql -U postgres -d zaminex -v ON_ERROR_STOP=1 -f ../zaminex_backup.sql
python manage.py resync_sequences
python manage.py migrate
```

```bash
python manage.py runserver
```

Then open http://localhost:8000/ in your browser.

> **Why `resync_sequences` before `migrate`?** Restoring a backup file can move the database's id
> counters backwards, which later causes `duplicate key value violates unique constraint` errors.
> This command puts the counters back in line with your data. Full explanation in
> [section 11](#11-the-resync_sequences-command--why-and-when).

### Route B: you have no backup and start with an empty database

```bash
cd ZaminexB
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata fixtures/seed_data.json
python manage.py seed_basics
python manage.py runserver
```

Then open http://localhost:8000/ and log in with the accounts from [section 5](#5-default-accounts).

---

## 8. Situation 2: you worked on the project and want to save it

### A) If you changed the models in the code

```bash
cd ZaminexB
python manage.py makemigrations
python manage.py migrate
```

### B) After entering real data, take a backup immediately

```bash
# Plain text backup (readable, recommended for moving data)
pg_dump -U postgres -d zaminex -h localhost -p 5432 -f zaminex_backup.sql

# Or the compressed format
pg_dump -U postgres -d zaminex -h localhost -p 5432 --format=custom -f zaminex_backup.dump
```

This file is **your real data**. Keep it somewhere safe.

> Do not overwrite `seed_data.json` with real data; that file must stay basic data only.

---

## 9. Situation 3: you have the project and receive a new version of the code

```bash
# 1) Back up your current database first
pg_dump -U postgres -d zaminex -h localhost -p 5432 -f zaminex_backup_before_update.sql

# 2) Replace the project files with the new version
#    (keep your own zaminex_backup.sql file)
```

```bash
# 3) Inside the ZaminexB folder
cd ZaminexB
pip install -r requirements.txt
python manage.py migrate
```

```bash
# 4) If the frontend changed, build it once - see section 12
# 5) Run
python manage.py runserver
```

**Your data stays in place.** There is no need to load `seed_data.json` again.

> If `migrate` stops with `relation "…" already exists`, your database and the
> migration list are out of step. One command fixes it - see
> [`repair_migrations`](#error-relation--already-exists-when-running-migrate).

---

## 10. Restore a backup (moving to a new computer or server)

To bring your data back on another computer or server, run these five commands **in this order**:

```bash
cd ZaminexB
pip install -r requirements.txt
```

```bash
psql -U postgres -c "DROP DATABASE IF EXISTS zaminex WITH (FORCE);"
psql -U postgres -c "CREATE DATABASE zaminex OWNER zaminex;"
psql -U postgres -d zaminex -v ON_ERROR_STOP=1 -f ../zaminex_backup.sql
python manage.py resync_sequences
python manage.py migrate
```

```bash
python manage.py runserver
```

What each line does:

1. `DROP DATABASE ... WITH (FORCE)` — deletes the previous database completely. **If it holds important data, take a backup of it first.**
2. `CREATE DATABASE ... OWNER zaminex` — creates a new, empty database.
3. `psql -v ON_ERROR_STOP=1 -f ...` — loads the backup file into the empty database. `ON_ERROR_STOP=1` means: if any line fails, stop right there instead of continuing.
4. `python manage.py resync_sequences` — brings the id counters back in line with the data ([section 11](#11-the-resync_sequences-command--why-and-when)).
5. `python manage.py migrate` — finishes any remaining database structure changes.

> Note: if `psql` asks for a username or cannot connect, add `-U postgres -h localhost` to the same command.

---

## 11. The `resync_sequences` command — why and when

### In plain words

Every table in the database has an **id counter**: each new row gets the next number.
When you restore a backup file (`zaminex_backup.sql`), the counter of some tables can end up
**behind the data**, meaning the counter is about to hand out a number that is already used.
The result is this error:

```
duplicate key value violates unique constraint "common_notification_pkey"
```

`resync_sequences` looks at every table, moves the counters that are behind **up to the highest id
that exists**, and fixes the problem for good. It never moves a counter backwards, so an id is never
handed out twice.

### When to run it

- **Always** right after restoring a backup ([section 10](#10-restore-a-backup-moving-to-a-new-computer-or-server)), that is, between `psql -f zaminex_backup.sql` and `migrate`.
- Any time you import or restore data with `psql` or another tool.

### The main command

```bash
cd ZaminexB
python manage.py resync_sequences
```

### Check-only mode (changes nothing)

```bash
python manage.py resync_sequences --dry-run
```

- If everything is fine, the output says `هماهنگ است` (in line) and the program ends with code 0.
- If some table is behind, it lists them and ends with code 1 — meaning "something needs attention".

### Other options

```bash
# Check/repair only one table
python manage.py resync_sequences --table properties_property

# More detail: also list the healthy tables
python manage.py resync_sequences -v 2
```

Example output:

```
بررسی دنباله‌های شماره‌گذاری (resync_sequences)
  پایگاه داده       : zaminex
  اسکیما            : public
  حالت              : اصلاح — دنباله‌های عقب‌مانده جابه‌جا می‌شوند

2 دنباله با دادهٔ جدولش تلاقی می‌کند:
  table                                     next id       max id   status
  common_notification                        14 → 34           33   FIXED
  properties_property                        17 → 24           23   FIXED

  FIXED  : دنباله به بیشینهٔ جدول منتقل شد؛ شناسهٔ بعدی حالا max + 1 است.
```

Reading the table: `next id` is the number the counter was about to give out, `max id` is the
highest number already used in that table. `FIXED` means the counter was moved forward.

---

## 12. Build the frontend (only if you edit React)

You do not need this to run the project; the ready-made frontend files are already inside the project.

If you changed files in `ZaminexF/src/`, do this once:

```bash
cd ZaminexF
npm install
npm run build
```

The build writes straight into `ZaminexB/static/frontend/` (replacing the old bundle automatically),
and `base.html` reads the new file names from the Vite manifest — no copying, no deleting old files,
no editing `base.html`.

After building, run the server as usual:

```bash
cd ZaminexB
python manage.py runserver
```

---

## 13. Run the project

```bash
cd ZaminexB
python manage.py runserver
```

Then open http://localhost:8000/

---

## 14. If something goes wrong

### The server starts but prints nothing and no page opens

This is not the code — **PostgreSQL is not answering.** While running its system checks, the
application connects to the database; when the server accepts the connection but never replies, the
process waits there and prints nothing more.

That wait is now bounded (`DATABASE_CONNECT_TIMEOUT`, 5 seconds by default), so instead of waiting
forever you get a message like:

```
ERRORS:
?: (database.E001) Cannot reach the PostgreSQL server at localhost:5432
   (database 'zaminex', user 'zaminex'): ... timeout expired
```

**Check the causes in this order:**

1. **Is the PostgreSQL service running?**
   - Windows: `Win+R` → `services.msc` → find `postgresql-x64-18` → right-click → **Start**.
     Also set *Startup type* to **Automatic**, or it stops again after every reboot.
   - Windows (PowerShell as Administrator): `net start postgresql-x64-18`
   - Linux: `sudo systemctl start postgresql`
2. **Can you reach it by hand?**
   ```powershell
   psql -U postgres -h localhost -p 5432 -c "SELECT 1"
   ```
   - It prints `1` → the server is fine, go to step 3.
   - `Connection refused` → the service is not running (step 1).
   - **It hangs with no output** → something that is not PostgreSQL holds port 5432 (a stopped
     Docker/WSL container that published it, a `netsh portproxy` rule, a second installation).
     Find it:
     ```powershell
     netstat -ano | findstr :5432
     tasklist /FI "PID eq <PID from above>"
     ```
     Stop that program, or move PostgreSQL to another port and set `DATABASE_PORT` in
     `ZaminexB/config/settings.py` to match.
3. **Do the values in `ZaminexB/config/settings.py` match your server?**
   `DATABASE_HOST` / `DATABASE_PORT` / `DATABASE_NAME` / `DATABASE_USER` / `DATABASE_PASSWORD`
   (defaults: `localhost` / `5432` / `zaminex` / `zaminex` / `zaminex`).
   If a `DATABASE_URL` environment variable exists it overrides all of them — check it with
   `echo $env:DATABASE_URL` and clear it with `Remove-Item Env:DATABASE_URL` when it points at
   some other project.
4. **Do the user and the database exist?**
   ```bash
   psql -U postgres -c "CREATE USER zaminex WITH PASSWORD 'zaminex';"
   psql -U postgres -c "CREATE DATABASE zaminex OWNER zaminex;"
   ```

If your database is genuinely far away and slow to reach, raise the bound instead of removing it:
`DATABASE_CONNECT_TIMEOUT=30`.

### Error `duplicate key value violates unique constraint "…_pkey"`

The id counter of that table is behind its data. One command is enough:

```bash
cd ZaminexB
python manage.py resync_sequences
```

Full explanation in [section 11](#11-the-resync_sequences-command--why-and-when).

### Error `relation "…" already exists` when running `migrate`

**In plain words.** Django keeps its own list of the migrations it has run (the
`django_migrations` table) and compares it with the migration files in the project. When the two
disagree - after a backup restored by hand, or after a migration was run from another copy of the
project - Django tries to create something that is already there and stops:

```
django.db.utils.ProgrammingError: relation "accounts_loginsettings" already exists
```

**Do not fix this with `migrate --fake`.** That marks migrations as done without looking at the
database, so a half-finished database can stay half-finished and the next error is even harder to
read.

`repair_migrations` looks at every migration that Django believes is missing, compares it with what
is really in the database, and then:

- records the migrations whose tables, columns and indexes are already there - nothing is run twice;
- applies only the parts that are genuinely missing.

```bash
cd ZaminexB
python manage.py repair_migrations --dry-run   # look first, changes nothing
python manage.py repair_migrations             # repair
python manage.py migrate                       # now says: No migrations to apply
```

### Warning `pg_trgm.W001` after restoring `zaminex_backup.sql`

The backup file records the migration `common.0006_pg_trgm_extension` as already applied but does not
contain the extension itself, so fuzzy search runs on a much slower path. Fix it once, as a superuser:

```bash
psql -U postgres -d zaminex -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
```

The warning disappears on the next `runserver`.

### Blank page at http://localhost:8000/ with warning `vite_assets.W001`

The built frontend files are not kept in Git (see [section 12](#12-build-the-frontend-only-if-you-edit-react)). Build them once:

```bash
cd ZaminexF
npm ci
npm run build
```

---

## 15. Final checklist

- [ ] PostgreSQL is installed, password `zaminex`, PATH set permanently
- [ ] The PostgreSQL **service is running** (`services.msc` → `postgresql-x64-18`)
- [ ] The `zaminex` user and the `zaminex` database exist
- [ ] `pip install -r requirements.txt` has been run
- [ ] The `zaminex_backup.sql` backup was restored **and `python manage.py resync_sequences` was run
      right after it** — or the database was created empty with `seed_data.json`
- [ ] `python manage.py migrate` finished without errors
- [ ] If `migrate` complained about a relation that already exists, `python manage.py
      repair_migrations` was run first and `migrate` was run again afterwards
- [ ] `python manage.py runserver` runs and http://localhost:8000/ opens
- [ ] After entering real data, you immediately took a `pg_dump` backup
