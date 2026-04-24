# CollabDocs API

A collaborative document management platform built with Django REST Framework. Users can create workspaces, invite collaborators, write and version documents, leave threaded comments, tag documents, and control access with role-based permissions. Think of it as a simplified Notion or Google Docs — API-only, with Postman as the client.

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Setup & Installation](#setup--installation)
3. [Running the Server](#running-the-server)
4. [Applying Migrations](#applying-migrations)
5. [Data Models](#data-models)
6. [API Endpoints](#api-endpoints)
7. [Authentication](#authentication)
8. [Filtering & Search](#filtering--search)
9. [Transactions & Data Integrity](#transactions--data-integrity)
10. [Middleware](#middleware)
11. [Signals & Audit Logging](#signals--audit-logging)
12. [Query Optimizations](#query-optimizations)
13. [Postman Collection](#postman-collection)
14. [Demo Video](#demo-video)
15. [Project Structure](#project-structure)
16. [Environment Variables](#environment-variables)

---

## Tech Stack

| Layer          | Technology                             |
| -------------- | -------------------------------------- |
| Language       | Python 3.14                            |
| Framework      | Django 6.0, Django REST Framework 3.17 |
| Database       | PostgreSQL 17 (Docker)                 |
| Authentication | JWT via djangorestframework-simplejwt  |
| Filtering      | django-filter                          |

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- Docker (for PostgreSQL)
- Git
- Postman (for testing)

### 1. Clone the Repository

```bash
git clone https://github.com/utkarsh-vats/Airtribe-CollabDocs.git
cd Airtribe-CollabDocs
```

### 2. Create and Activate Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start PostgreSQL via Docker

```bash
docker run -d \
  --name collabdocs-db \
  -p 8080:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=collabdocs_db \
  -e POSTGRES_PASSWORD=your_password \
  -v collabdocs_pgdata:/var/lib/postgresql \
  postgres
```

### 5. Configure Environment Variables

```bash
cp .env.example .env.local
```

Edit `.env.local` with your database credentials. See [Environment Variables](#environment-variables) for details.

### 6. Apply Migrations

```bash
python manage.py migrate
```

### 7. Create a Superuser (optional)

```bash
python manage.py createsuperuser
```

---

## Running the Server

```bash
python manage.py runserver
```

The API is available at `http://127.0.0.1:8000/api/`.

You will see middleware logs in the terminal for every request:

```
POST    /api/users/         -   201     -   45.23ms
GET     /api/workspaces/    -   200     -   12.87ms
```

---

## Applying Migrations

All migrations are committed and apply cleanly from a fresh database.

```bash
# Apply all migrations
python manage.py migrate

# After model changes, create new migrations
python manage.py makemigrations api
python manage.py migrate
```

To verify clean migration from scratch:

```bash
# Reset database
docker exec -it collabdocs-db psql -U postgres -c "DROP DATABASE collabdocs_db;"
docker exec -it collabdocs-db psql -U postgres -c "CREATE DATABASE collabdocs_db;"

# Re-apply all migrations
python manage.py migrate
```

---

## Data Models

The application implements **8 models**. All primary keys are `UUIDField` with `uuid.uuid4` auto-generation and `editable=False`. A shared `BaseModel` provides `id`, `created_at`, and `updated_at` to all models.

### User

Extends Django's `AbstractUser` with a UUID primary key and a `phone` field. Inherits `username`, `email`, `first_name`, `last_name`, `password`, and `date_joined` from `AbstractUser`. Configured via `AUTH_USER_MODEL = 'api.User'` in settings.

### Workspace

A collaborative workspace. Fields: `name`, `owner` (FK → User, CASCADE), `is_active` (BooleanField, default=True), `created_at`, `updated_at`. On creation, the owner is automatically added as a `WorkspaceMember` with role `ADMIN` inside a single `transaction.atomic()` block.

### WorkspaceMember

Links users to workspaces with role-based access. Fields: `workspace` (FK → Workspace), `user` (FK → User), `role` (TextChoices: ADMIN, EDITOR, VIEWER), `joined_at`. Enforces a `UniqueConstraint` on `(workspace, user)` to prevent duplicate memberships. Duplicate attempts return `409 Conflict`.

### Document

A document within a workspace. Fields: `title`, `content`, `workspace` (FK → Workspace), `created_by` (FK → User), `status` (TextChoices: DRAFT, PUBLISHED, ARCHIVED). Every create and update wraps the document save and a new `DocumentVersion` inside a single `transaction.atomic()` block. A `post_save` signal automatically writes an `AuditLog` entry on every save.

### DocumentVersion

Immutable snapshot of a document at a point in time. Fields: `document` (FK → Document), `title` (snapshot), `content` (snapshot), `version_number` (computed as `document.versions.count() + 1` inside the atomic block), `saved_by` (FK → User), `saved_at`. Ordered by `-saved_at`.

### Comment

Threaded comments on documents using a self-referential ForeignKey. Fields: `document` (FK → Document), `author` (FK → User), `content`, `parent` (FK → self, null=True, blank=True, on_delete=SET_NULL, related_name='replies'). A comment with `parent=null` is top-level; replies reference their parent. The API returns top-level comments with nested replies via a recursive `SerializerMethodField`.

### Tag

Tags for categorizing documents via a `ManyToManyField`. Fields: `name` (CharField, unique). Tags can be added to documents using `doc.tags.add(tag)` or via the `/api/documents/{id}/tags/` endpoint. Documents can be filtered by tag: `Document.objects.filter(tags__name='python')`.

### AuditLog

Automatic audit trail for tracking all system actions. Fields: `actor` (FK → User, SET_NULL), `action` (TextChoices: CREATED, UPDATED, DELETED, SHARED, ARCHIVED, TAGGED, etc.), `model_name`, `object_id` (UUIDField), `changes` (JSONField, optional), `timestamp`. Written automatically via a `post_save` signal on Document and explicitly inside atomic blocks for workspace operations.

### Key Constraints

- All PKs: `UUIDField` with `uuid.uuid4`, `editable=False`
- `TextChoices` for `WorkspaceMember.Roles`, `Document.Statuses`, `AuditLog.Actions`
- `UniqueConstraint` on `WorkspaceMember(workspace, user)` with name `unique_workspace_member`
- `ManyToManyField` between `Tag` and `Document`
- Self-referential `ForeignKey` on `Comment` for threaded replies
- `Workspace.is_active`: `BooleanField` with `default=True`

---

## API Endpoints

### Users

| Method | Endpoint           | Description         | Auth     |
| ------ | ------------------ | ------------------- | -------- |
| POST   | `/api/users/`      | Register a new user | None     |
| GET    | `/api/users/`      | List all users      | Required |
| GET    | `/api/users/{id}/` | Get user detail     | Required |

### Authentication

| Method | Endpoint              | Description                          | Auth |
| ------ | --------------------- | ------------------------------------ | ---- |
| POST   | `/api/token/`         | Obtain JWT access and refresh tokens | None |
| POST   | `/api/token/refresh/` | Refresh an expired access token      | None |

### Workspaces

| Method | Endpoint                        | Description                                            | Auth     |
| ------ | ------------------------------- | ------------------------------------------------------ | -------- |
| POST   | `/api/workspaces/`              | Create workspace (owner auto-added as ADMIN)           | Required |
| GET    | `/api/workspaces/`              | List all workspaces                                    | Required |
| GET    | `/api/workspaces/{id}/`         | Get workspace detail                                   | Required |
| PUT    | `/api/workspaces/{id}/`         | Update workspace                                       | Required |
| GET    | `/api/workspaces/{id}/stats/`   | Aggregate stats (documents, members, status breakdown) | Required |
| GET    | `/api/workspaces/{id}/members/` | List workspace members                                 | Required |
| POST   | `/api/workspaces/{id}/members/` | Add member (returns 409 on duplicate)                  | Required |

### Documents

| Method | Endpoint                        | Description                                           | Auth     |
| ------ | ------------------------------- | ----------------------------------------------------- | -------- |
| POST   | `/api/documents/`               | Create document (auto-creates version 1)              | Required |
| GET    | `/api/documents/`               | List documents (supports filtering and search)        | Required |
| GET    | `/api/documents/{id}/`          | Get document detail                                   | Required |
| PUT    | `/api/documents/{id}/`          | Full update (creates new version)                     | Required |
| PATCH  | `/api/documents/{id}/`          | Partial update (creates new version)                  | Required |
| GET    | `/api/documents/{id}/versions/` | List all versions of a document                       | Required |
| GET    | `/api/documents/{id}/stats/`    | Per-document stats (versions, comments, contributors) | Required |
| POST   | `/api/documents/{id}/tags/`     | Add tags to a document                                | Required |
| GET    | `/api/documents/summary/`       | Global document summary (aggregate counts by status)  | Required |

### Comments

| Method | Endpoint                       | Description                                 | Auth     |
| ------ | ------------------------------ | ------------------------------------------- | -------- |
| POST   | `/api/comments/`               | Create a comment or reply                   | Required |
| GET    | `/api/comments/?document={id}` | List top-level comments with nested replies | Required |

### Tags

| Method | Endpoint                  | Description                        | Auth     |
| ------ | ------------------------- | ---------------------------------- | -------- |
| POST   | `/api/tags/`              | Create a tag                       | Required |
| GET    | `/api/tags/`              | List all tags with document counts | Required |
| GET    | `/api/tags/?name={query}` | Filter tags by name                | Required |

### Audit Logs

| Method | Endpoint                          | Description                | Auth     |
| ------ | --------------------------------- | -------------------------- | -------- |
| GET    | `/api/audit-logs/`                | List all audit logs        | Required |
| GET    | `/api/audit-logs/?object_id={id}` | Filter logs by object      | Required |
| GET    | `/api/audit-logs/?action=CREATED` | Filter logs by action type | Required |

---

## Authentication

Authentication is handled via JWT (JSON Web Tokens) using `djangorestframework-simplejwt`.

### Obtaining Tokens

```bash
POST /api/token/
{
    "username": "your_username",
    "password": "your_password"
}
```

Response:

```json
{
    "access": "eyJ0eXAiOiJKV1Qi...",
    "refresh": "eyJ0eXAiOiJKV1Qi..."
}
```

### Using Tokens

Add the access token to every authenticated request as a header:

```
Authorization: Bearer <access_token>
```

### Token Lifetimes

| Token   | Development | Production |
| ------- | ----------- | ---------- |
| Access  | 1 day       | 15 minutes |
| Refresh | 3 days      | 3 days     |

### Refreshing Tokens

```bash
POST /api/token/refresh/
{
    "refresh": "<refresh_token>"
}
```

### Public Endpoints (no auth required)

- `POST /api/users/` — user registration
- `POST /api/token/` — obtain tokens
- `POST /api/token/refresh/` — refresh tokens

All other endpoints require authentication.

---

## Filtering & Search

### Document Filters

| Parameter        | Lookup                                                 | Example                      |
| ---------------- | ------------------------------------------------------ | ---------------------------- |
| `search`         | `title__icontains` OR `content__icontains` (Q objects) | `?search=hello`              |
| `status`         | exact match                                            | `?status=DRAFT`              |
| `workspace`      | exact match on workspace_id                            | `?workspace=<uuid>`          |
| `created_after`  | `created_at__gte`                                      | `?created_after=2026-04-01`  |
| `created_before` | `created_at__lte`                                      | `?created_before=2026-05-01` |

Filters can be combined: `?search=guide&status=PUBLISHED`

The `search` parameter uses Django's `Q` objects for OR filtering across title and content fields.

### Tag Filters

| Parameter | Lookup            | Example    |
| --------- | ----------------- | ---------- |
| `name`    | `name__icontains` | `?name=py` |

### Audit Log Filters

| Parameter   | Lookup      | Example             |
| ----------- | ----------- | ------------------- |
| `object_id` | exact match | `?object_id=<uuid>` |
| `action`    | exact match | `?action=CREATED`   |

---

## Transactions & Data Integrity

### Workspace Creation

Workspace creation, member addition, and audit log writing are wrapped in a single `transaction.atomic()` block. If any step fails, all changes roll back:

```python
with transaction.atomic():
    workspace = serializer.save(owner=request.user)
    WorkspaceMember.objects.create(workspace=workspace, user=request.user, role='ADMIN')
    AuditLog.objects.create(actor=request.user, action='CREATED', model_name='Workspace', object_id=workspace.id)
```

### Document Save + Version

Every document create and update wraps the document save and version creation in a single `transaction.atomic()` block:

```python
with transaction.atomic():
    document = serializer.save(created_by=request.user)
    DocumentVersion.objects.create(
        document=document, title=document.title, content=document.content,
        version_number=document.versions.count() + 1, saved_by=document.created_by
    )
```

### Duplicate Member Handling

`IntegrityError` is caught explicitly when adding a workspace member. Duplicate attempts return `409 Conflict` instead of a generic 500:

```python
try:
    serializer.save(workspace=workspace)
except IntegrityError:
    return Response({'error': 'User is already a member of this workspace.'}, status=409)
```

---

## Middleware

A custom `RequestLoggingMiddleware` logs every request to the console with the HTTP method, endpoint path, response status code, and time taken in milliseconds.

Registered at the top of the `MIDDLEWARE` list in `settings.py`.

### Sample Output

```
POST    /api/users/         -   201     -   45.23ms
GET     /api/workspaces/    -   200     -   12.87ms
POST    /api/token/         -   200     -   89.41ms
GET     /api/documents/?search=hello    -   200     -   8.54ms
DELETE  /api/users/abc123/  -   405     -   2.11ms
```

---

## Signals & Audit Logging

A `post_save` signal on the `Document` model automatically creates an `AuditLog` entry whenever a document is created or updated.

- **Signal file:** `api/signals.py`
- **Connected in:** `ApiConfig.ready()` in `api/apps.py`
- **Detection:** Uses the `created` kwarg from Django's `post_save` signal
- **Records:** `actor` (created_by), `action` ('CREATED' or 'UPDATED'), `model_name` ('Document'), `object_id`

Workspace-related audit logs are written explicitly inside the `transaction.atomic()` block in the view.

---

## Query Optimizations

### select_related (FK joins)

Used on every endpoint returning nested user, workspace, or document data to avoid N+1 queries:

- `Workspace.objects.select_related('owner')`
- `Document.objects.select_related('created_by', 'workspace')`
- `Comment.objects.select_related('author', 'document')`
- `AuditLog.objects.select_related('actor')`
- `workspace.members.select_related('user')`
- `document.versions.select_related('saved_by')`

### prefetch_related (M2M)

- `Document.objects.prefetch_related('tags')`

### aggregate() / annotate() with Count

Used in 4+ endpoints:

1. **Workspace stats** — `workspace.documents.values('status').annotate(count=Count('id'))`
2. **Document summary** — `Document.objects.aggregate(total=Count('id'), drafts=Count(...), ...)`
3. **Document stats** — `document.versions.values('saved_by').distinct().count()`
4. **Tag list** — `Tag.objects.annotate(document_count=Count('documents'))`

### Q Objects (OR filtering)

Used on the document list endpoint for search across title and content:

```python
queryset.filter(Q(title__icontains=search) | Q(content__icontains=search))
```

### values_list()

Used in the tag assignment response:

```python
list(tags.values_list('name', flat=True))
```

### Filter Lookups

- `__icontains` — case-insensitive text search
- `__gte` / `__lte` — date range filtering
- `__in` — bulk tag lookup by IDs

---

## Postman Collection

The Postman collection `CollabDocs_postman_collection.json` is committed to the repository root. It contains all API endpoints organized into folders:

- **Users** — registration, list, detail
- **Workspaces** — CRUD, stats, members
- **Documents** — CRUD, filtering, versions, tags, stats, summary
- **Comments** — create, reply, list with threading
- **Tags** — create, list, filter
- **Audit Logs** — list, filter by object, filter by action
- **Edge Cases** — duplicate email, weak password, duplicate member (409), not found (404), unauthorized (401), method not allowed (405)

### Setup in Postman

1. Import `CollabDocs_postman_collection.json` into Postman
2. Set collection variable `base_url` = `http://127.0.0.1:8000/api`
3. Register a user via `POST /api/users/`
4. Get a token via `POST /api/token/`
5. Set collection variable `access_token` with the returned access token
6. Set `Authorization` at the collection level to `Bearer Token` → `{{access_token}}`
7. Run requests in order, saving returned UUIDs as collection variables

---

## Demo Video

**[Demo Video Link]()**

The demo covers:

1. **Middleware logging** — terminal output showing method, path, status code, and duration for every request
2. **Atomic transaction with rollback** — demonstrating that workspace creation rolls back if member creation fails
3. **Aggregation endpoints** — workspace stats and document summary showing counts by status
4. **AuditLog via signal** — creating and updating a document, then verifying AuditLog entries were automatically written by the post_save signal

---

## Project Structure

```
collabdocs-api/
├── api/
│   ├── migrations/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py              # AppConfig with signal connection in ready()
│   ├── middleware.py         # RequestLoggingMiddleware
│   ├── models.py             # 8 models: User, Workspace, WorkspaceMember,
│   │                         #   Document, DocumentVersion, Comment, Tag, AuditLog
│   ├── serializers.py        # All serializers with SerializerMethodFields
│   │                         #   and custom validations
│   ├── signals.py            # post_save signal on Document → AuditLog
│   ├── urls.py               # Router + JWT endpoints
│   └── views.py              # 6 ViewSets with @action decorators
├── collabdocs/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py           # PostgreSQL, JWT, middleware config
│   ├── urls.py               # Root URL config
│   └── wsgi.py
├── .env.example
├── .gitignore
├── CollabDocs_postman_collection.json
├── manage.py
├── README.md
└── requirements.txt
```

---

## Environment Variables

Create a `.env.local` file in the project root (see `.env.example`):

| Variable      | Description              | Example                     |
| ------------- | ------------------------ | --------------------------- |
| `SECRET_KEY`  | Django secret key        | `django-insecure-abc123...` |
| `DEBUG`       | Debug mode (True/False)  | `True`                      |
| `DB_NAME`     | PostgreSQL database name | `collabdocs_db`             |
| `DB_USER`     | PostgreSQL username      | `postgres`                  |
| `DB_PASSWORD` | PostgreSQL password      | `your_password`             |
| `DB_HOST`     | Database host            | `localhost`                 |
| `DB_PORT`     | Database port            | `8080`                      |

> **Note:** `.env.local` is listed in `.gitignore` and is never committed. Use `.env.example` as a template.