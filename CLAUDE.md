# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
**ScoreMateServer** - Django REST API backend for ScoreMate sheet music management system
- **Stack**: Python 3.9, Django 5.2.5, Django REST Framework, PostgreSQL, Redis, Celery, MinIO/S3
- **Architecture**: Multi-container Docker Compose setup with separate web, worker, database, cache, and storage services
- **Purpose**: Manage user accounts, PDF sheet music storage, library metadata, setlists, background processing (thumbnails, PDF info), and quota management

## Development Commands

### Initial Setup
```bash
# Copy environment variables
cp .env.example .env

# Start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser for admin access
docker-compose exec web python manage.py createsuperuser

# Collect static files (for production)
docker-compose exec web python manage.py collectstatic --noinput
```

### Common Development Tasks
```bash
# Run development server (if not using docker-compose)
python manage.py runserver

# Make and apply migrations
python manage.py makemigrations
python manage.py migrate

# Run tests (recommended: use pytest with coverage)
docker-compose exec web python -m pytest tests/ -v --tb=short --cov=. --cov-report=term-missing

# Alternative: Django test runner
python manage.py test

# Access Django shell
python manage.py shell

# Start Celery worker (for background tasks)
celery -A scoremateserver worker -l info

# Monitor Celery tasks
celery -A scoremateserver flower
```

### Docker Commands
```bash
# View logs
docker-compose logs -f web
docker-compose logs -f worker

# Restart services
docker-compose restart web worker

# Access service shells
docker-compose exec web bash
docker-compose exec db psql -U scoremate -d scoremate

# Rebuild after requirements change
docker-compose build web worker
docker-compose up -d
```

## High-Level Architecture

### Service Layout
- **Django API** (`/app`): REST endpoints, JWT auth, presigned URL generation
- **Celery Workers**: Background tasks for PDF processing, thumbnail generation
- **PostgreSQL**: Main database for users, scores, setlists, tasks
- **Redis**: Celery broker and caching layer
- **MinIO/S3**: Object storage for PDF files and thumbnails
- **Nginx**: Reverse proxy for TLS, rate limiting, static files

### Key Design Decisions
1. **Presigned URLs**: All file uploads/downloads use S3 presigned URLs - server never streams files directly
2. **Background Processing**: PDF info extraction and thumbnail generation run as Celery tasks
3. **Private by Default**: No public sharing; all resources require authentication
4. **Quota Management**: Track `used_quota_mb` on file operations; enforce limits
5. **No Realtime Sync**: Page-turn synchronization is client-side only (no WebSocket)

### Data Flow Patterns
```
Upload: Client → Django (presigned URL) → Direct to S3 → Celery task (process)
Download: Client → Django (presigned URL) → Direct from S3
Background: Upload trigger → Celery task → Update database → Store results in S3
```

## Development Process

### Phase-based Development
ScoreMateServer follows a structured phase-based development approach:

1. **Phase Planning**: Create detailed implementation plan and timeline
2. **Phase Implementation**: Code development with regular commits  
3. **Phase Testing**: Comprehensive testing with factory_boy and pytest
4. **Phase Review**: Code review and documentation update
5. **Phase Completion**: Final evaluation and next phase preparation

### Documentation Standards

#### devlog/ Directory Structure
All development progress is documented in `devlog/` with consistent naming:
```
devlog/
├── YYYYMMDD_###_<title_in_korean>.md
├── 20250819_001_프로젝트_초기_설정.md
├── 20250819_008_phase1_테스트_구현_완료.md
├── 20250819_009_factory_boy_마이그레이션_완료.md
└── ...
```

#### Document Types per Phase
- **Planning Document**: Implementation plan and architecture decisions
- **Progress Reports**: Regular development updates and issue resolutions  
- **Testing Report**: Test implementation, coverage analysis, bug fixes
- **Completion Report**: Phase summary, achievements, next steps

### Testing Requirements
- **每 Phase End**: Complete test suite implementation before proceeding
- **Test Coverage**: Target >90% coverage on business logic
- **Test Documentation**: Document test implementation process
- **Bug Resolution**: Fix all discovered issues during testing phase

### Quality Gates
Before moving to the next phase:
1. ✅ All implemented features fully tested
2. ✅ Code coverage meets target (>90%)
3. ✅ All tests passing
4. ✅ Documentation updated (CLAUDE.md, devlog/)
5. ✅ Phase completion report written

## Directory Structure
```
/scoremateserver/   # Django project settings
  settings.py       # Main configuration (uses env vars)
  urls.py          # Root URL configuration
  celery.py        # Celery configuration (if exists)

/core/             # Authentication, users, quota, referrals
/scores/           # Score model, metadata, tags, CRUD operations  
/setlists/         # Setlist and SetlistItem models
/files/            # Presigned URL generation for S3
/tasks/            # Celery task definitions (pdf_info, thumbnail)
/admin/            # Django admin customizations

/nginx/            # Nginx configuration
/devlog/           # Development logs and notes
```

## API Endpoint Structure
All API endpoints should follow RESTful conventions and use Django REST Framework ViewSets where appropriate.

### Authentication
- JWT-based using `djangorestframework-simplejwt`
- All endpoints except auth require `Bearer` token
- Token lifetime: 60 min access, 1 day refresh

### Main Endpoints
- `/auth/` - Registration, login, logout
- `/scores/` - Score CRUD, search, tagging
- `/setlists/` - Setlist management
- `/files/` - Presigned URL generation
- `/tasks/` - Background task monitoring
- `/billing/` - Quota, usage, referrals

## Dependencies and Requirements

### Production Requirements
```
Django>=5.0,<5.1
djangorestframework
djangorestframework-simplejwt
celery
redis
psycopg2-binary
boto3
python-dotenv
Pillow
pdfplumber
dj-database-url
```

### Testing Requirements  
```
pytest
pytest-django
pytest-cov
factory-boy
```

### Development Tools
- **Docker**: All services containerized with docker-compose
- **PostgreSQL**: Primary database
- **Redis**: Celery broker and cache
- **MinIO**: S3-compatible object storage for development

## Environment Configuration
Key environment variables (see `.env.example`):
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for Celery
- `STORAGE_*`: MinIO/S3 configuration
- `JWT_SIGNING_KEY`: Secret for JWT tokens
- `MAX_UPLOAD_MB`: Upload size limit
- `ALLOWED_MIME`: Allowed file types (default: application/pdf)

## Testing Strategy

### Framework and Structure
- **Primary**: pytest with pytest-django for Django integration
- **Test Location**: Centralized `tests/` directory (not individual app `tests.py`)
- **Data Generation**: factory_boy for flexible test data creation
- **Coverage Target**: Maintain >90% code coverage on core business logic

### Test Organization
```
tests/
├── conftest.py          # pytest fixtures and Django setup
├── factories.py         # factory_boy factories for all models
├── test_core_models.py  # User, quota, referral logic tests
├── test_scores_models.py # Score S3 keys, metadata tests
├── test_setlists_models.py # Setlist ordering, statistics tests
└── test_api_*.py        # API endpoint tests (Phase 2+)
```

### Test Data with Factory_boy
```python
# Use factories instead of manual object creation
user = UserFactory(email="test@example.com", plan="pro")
score = ScoreFactory(user=user, title="Test Score")
setlist = SetlistFactory(user=user)
item = SetlistItemFactory(setlist=setlist, score=score)
```

### Best Practices
- Mock S3 operations in tests using `moto` or similar
- Test Celery tasks synchronously with `CELERY_ALWAYS_EAGER=True`
- Each phase should have comprehensive tests before proceeding
- Use `@pytest.mark.django_db` for database access in tests

## Important Constraints
1. **No WebSocket/Realtime**: All synchronization happens client-side
2. **No Public Sharing**: Server doesn't provide public access to scores
3. **Idempotent Tasks**: Background jobs must be safely retryable
4. **Quota Enforcement**: Always update `used_quota_mb` on file operations
5. **Presigned URLs Only**: Never stream files through Django

## Code Conventions
- Follow PEP 8 style guide
- Use type hints for function signatures where beneficial
- Prefer Django REST Framework serializers for validation
- Use ViewSets for standard CRUD operations
- Keep business logic in models or separate service modules
- Write docstrings for public methods and complex logic

## Migration and Database Notes
- Always create migrations for model changes: `python manage.py makemigrations`
- Review migrations before applying: `python manage.py showmigrations`
- Use `db_index=True` on frequently queried fields
- Tags stored as PostgreSQL array field or normalized table

## Background Task Patterns
```python
# Tasks should be idempotent and atomic
@shared_task(bind=True, max_retries=3)
def process_pdf(self, score_id):
    try:
        # Task logic here
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

## Security Considerations
- All user uploads are private by default
- Use presigned URLs with short TTL (5-15 minutes)
- Validate MIME types and file sizes before upload
- Never expose S3 credentials to clients
- Rate limit API endpoints in production
- Sanitize user input in metadata fields