# Alembic Guide — Finance RAG Backend

This guide explains Alembic in the context of **this** project: FastAPI + SQLModel + Neon Postgres.

---

## 1. What is Alembic?

**Alembic** is a database migration tool for SQLAlchemy (and therefore SQLModel).

Think of it like **Git for your database schema**:

| Git | Alembic |
|-----|---------|
| Tracks code changes | Tracks table/column changes |
| Commits | Migration revision files |
| `git push` | `alembic upgrade head` |
| `git log` | `alembic history` |
| Roll back a commit | `alembic downgrade -1` |

Each time you change models (new table, new column, rename, drop), Alembic:

1. Compares your Python models to the live database
2. Writes a **migration script** under `alembic/versions/`
3. Applies that script to the database when you run `upgrade`

Those scripts are versioned in Git, so every environment (local, staging, Neon) can reach the same schema safely.

---

## 2. Why we use Alembic?

Without Alembic you might call something like:

```python
SQLModel.metadata.create_all(engine)
```

That can create missing tables once, but it does **not**:

- Track schema history
- Alter existing columns safely
- Let teammates replay the same changes
- Support clean rollbacks

**We use Alembic because:**

1. **Safety** — schema changes are explicit scripts you can review before applying
2. **History** — every change is recorded (`alembic/versions/*.py`)
3. **Team sync** — anyone can run `alembic upgrade head` and match Neon
4. **Production-ready** — Neon / cloud DBs should never rely on silent `create_all`
5. **Rollback** — you can undo a bad migration with `downgrade`

In this repo, prefer Alembic over `init_db()` / `create_all` for schema changes.

---

## 3. Installation & Alembic Setup

### Install

Alembic is already in `pyproject.toml`:

```toml
"alembic>=1.18.5"
```

With the project venv active:

```powershell
# from backend/
uv sync
# or: pip install alembic
```

### Initialize (already done in this project)

One-time scaffold:

```powershell
alembic init alembic
```

That creates:

```text
backend/
├── alembic.ini              # Alembic config (DB URL, paths, logging)
└── alembic/
    ├── env.py               # Runtime hook — loads models + metadata
    ├── script.py.mako       # Template for new migration files
    ├── README
    └── versions/            # Generated migration scripts live here
```

### Important files in this project

| File | Role |
|------|------|
| `alembic.ini` | `script_location`, `sqlalchemy.url` (Neon connection) |
| `alembic/env.py` | Imports models, sets `target_metadata = SQLModel.metadata` |
| `alembic/script.py.mako` | Includes `import sqlmodel` so autogenerate types work |
| `alembic/versions/` | Actual migration history |

### Activate venv before running commands

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
```

Useful commands:

```powershell
alembic current    # revision currently applied on DB
alembic heads      # latest local revision(s)
alembic history    # full migration history
alembic check      # compare metadata vs DB (if supported)
```

---

## 4. Integration: SQLModel with Alembic

SQLModel stores table definitions on **`SQLModel.metadata`**. Alembic must:

1. Import every model that has `table=True` (so tables register on metadata)
2. Point `target_metadata` at that same metadata object

### Our `alembic/env.py` pattern

```python
from sqlmodel import SQLModel
from app.db.models.user import User
# later: from app.db.models.chat import Chat
# later: from app.db.models.docs import Docs

from alembic import context

config = context.config
# ... logging setup ...

target_metadata = SQLModel.metadata
```

Also export models from `app/db/models/__init__.py` so they register in one place:

```python
from app.db.models.user import User

__all__ = ["User"]
```

### How autogenerate works

```text
SQLModel classes (Python)
        ↓  metadata
Alembic compares vs live Neon schema
        ↓
Writes alembic/versions/<rev>_message.py
        ↓
alembic upgrade head
        ↓
Neon tables updated
```

### SQLModel tip (this project)

Autogenerate may emit `sqlmodel.sql.sqltypes.AutoString()`. Our `script.py.mako` already has:

```python
import sqlmodel
```

If a migration still fails on types, you can replace `AutoString()` with `sa.String()` in the revision file before upgrading.

---

## 5. Create SQLModels, generate migration, push to DB

This is the workflow you already used for the **`users`** table.

### Step A — Define the model

Example: `app/db/models/user.py`

```python
from uuid import UUID
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default=None, primary_key=True, nullable=False)
    email: str = Field(unique=True, index=True, nullable=False)
    full_name: Optional[str] = Field(default=None, nullable=True)
    role: str = Field(default="user", nullable=False)
```

### Step B — Register imports for Alembic

In `alembic/env.py`:

```python
from app.db.models.user import User
```

In `app/db/models/__init__.py`:

```python
from app.db.models.user import User
__all__ = ["User"]
```

### Step C — Generate the migration

```powershell
alembic revision --autogenerate -m "create users table"
```

Alembic writes something like:

`alembic/versions/37dee862b8d6_create_users_table.py`

### Step D — Safety check (always do this)

Open the new file and inspect `upgrade()`:

- ✅ Should contain `op.create_table('users', ...)` (or alter/drop ops you expect)
- ❌ If it only has `pass`, Alembic did **not** see your model — fix imports and regenerate

Also check `downgrade()` undoes the change (e.g. `op.drop_table('users')`).

### Step E — Push to Neon

```powershell
alembic upgrade head
```

Refresh Neon Console — the `users` table should appear.

You already completed this successfully:

```text
Running upgrade  -> 37dee862b8d6, create users table
```

---

## 6. How to add further models (Chat, Docs) → migration → DB

Use this exact workflow whenever you add tables like `chats` and `docs`.

### Step 1 — Create the models

Create files under `app/db/models/` (recommended: `chat.py` and `docs.py`).

**`app/db/models/chat.py`**

```python
from uuid import UUID
from typing import Optional
import datetime
from sqlmodel import SQLModel, Field

class Chat(SQLModel, table=True):
    __tablename__ = "chats"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    message: str
    created_at: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow
    )
```

**`app/db/models/docs.py`**

```python
from uuid import UUID
from typing import Optional
from sqlmodel import SQLModel, Field

class Docs(SQLModel, table=True):
    __tablename__ = "docs"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    content: str
    user_id: UUID = Field(foreign_key="users.id")
```

### Step 2 — Register models so Alembic can see them

Update **`alembic/env.py`**:

```python
from sqlmodel import SQLModel
from app.db.models.user import User
from app.db.models.chat import Chat
from app.db.models.docs import Docs

target_metadata = SQLModel.metadata
```

Update **`app/db/models/__init__.py`**:

```python
from app.db.models.user import User
from app.db.models.chat import Chat
from app.db.models.docs import Docs

__all__ = ["User", "Chat", "Docs"]
```

> **Critical:** If Python never imports `Chat` / `Docs`, they are not on `SQLModel.metadata`, and autogenerate will produce an empty migration.

### Step 3 — Generate the migration

```powershell
alembic revision --autogenerate -m "add chat and docs models"
```

### Step 4 — Safety check

Open the new file in `alembic/versions/` and confirm `upgrade()` contains:

- `op.create_table('chats', ...)`
- `op.create_table('docs', ...)`

If `upgrade()` is only `pass`:

1. Fix imports in `env.py` / `__init__.py`
2. Delete the empty revision file (or write a corrected one)
3. Run autogenerate again

### Step 5 — Push to Neon

```powershell
alembic upgrade head
```

Refresh Neon Console — you should see `chats` and `docs` beside `users`.

### Later changes (columns, indexes, renames)

Same loop every time:

1. Edit the SQLModel class(es)
2. Ensure the model is imported in `env.py` (already registered models stay)
3. `alembic revision --autogenerate -m "describe the change"`
4. Review `upgrade()` / `downgrade()`
5. `alembic upgrade head`

### Handy commands cheat sheet

```powershell
# New migration from model diffs
alembic revision --autogenerate -m "your message"

# Apply all pending migrations
alembic upgrade head

# Undo the last migration
alembic downgrade -1

# See what’s applied
alembic current

# See all revisions
alembic history
```

### Optional: SQLModel relationships

Foreign keys alone link rows in Postgres. For nicer Python navigation, you can add `Relationship()` later, for example:

```python
from typing import Optional, List
from sqlmodel import Relationship

class User(SQLModel, table=True):
    # ... fields ...
    chats: List["Chat"] = Relationship(back_populates="user")
    docs: List["Docs"] = Relationship(back_populates="user")

class Chat(SQLModel, table=True):
    # ... fields including user_id ...
    user: Optional[User] = Relationship(back_populates="chats")
```

Relationships are app-layer convenience; Alembic still cares mainly about tables, columns, and FKs.

---

## 7. Final Thoughts

1. **Alembic = schema version control.** Treat migrations like code reviews.
2. **Always import new models** in `alembic/env.py` (and `__init__.py`) or autogenerate will miss them.
3. **Never skip the safety check** — empty `upgrade()` means Alembic saw no changes.
4. Prefer **`alembic upgrade head`** over `create_all` for Neon / shared environments.
5. Keep DB URLs out of Git when possible (load from `.env` / settings in `env.py` rather than hardcoding secrets in `alembic.ini`).
6. Workflow to memorize:

```text
Edit SQLModel → Import for Alembic → autogenerate → review → upgrade head
```

That’s the full loop for this Finance RAG backend: from first `users` table to adding `chats`, `docs`, and every future model.
