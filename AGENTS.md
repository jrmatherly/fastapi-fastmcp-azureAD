# AGENTS.md
This file provides guidance to AI coding assistants working in this repository.

**Note:** CLAUDE.md, .clinerules, .cursorrules, and other AI config files are symlinks to AGENTS.md in this project.

# Full Stack FastAPI Template

A modern full-stack web application template combining FastAPI (Python backend) with React (TypeScript frontend), designed for rapid development and production deployment.

**Architecture:**
- **Backend:** FastAPI + SQLModel + PostgreSQL + Alembic migrations
- **Authentication:** Azure AD + MSAL + JWT + Role-based access control
- **MCP Integration:** fastMCP server with weather tools example
- **Session Storage:** Redis for secure token storage and caching
- **Frontend:** React 19 + TypeScript + TanStack Router + Chakra UI
- **Development:** Docker Compose + hot reloading + live debugging
- **Production:** Docker containers + Traefik proxy + GitHub Actions CI/CD

## Build & Commands

### Development Environment

**Start full development stack:**
```bash
docker compose watch
```

**Individual services:**
```bash
# Frontend development server (http://localhost:5173)
cd frontend && npm run dev

# Backend development server (http://localhost:8000)
cd backend && fastapi dev app/main.py
```

### Frontend Commands (npm)

**CRITICAL:** Use these EXACT script names from package.json:

- **Development:** `npm run dev` (Vite dev server with hot reload)
- **Build:** `npm run build` (TypeScript compile + Vite production build)
- **Lint:** `npm run lint` (Biome check with auto-fix and format)
- **Preview:** `npm run preview` (Preview production build locally)
- **Generate Client:** `npm run generate-client` (Generate OpenAPI client)

**Testing:**
```bash
# End-to-end tests with Playwright
npx playwright test

# UI mode for interactive testing
npx playwright test --ui

# Specific test file
npx playwright test tests/login.test.ts
```

### Backend Commands (uv)

**Development:**
```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run development server
fastapi dev app/main.py
```

**Testing:**
```bash
# Run all tests
uv run bash scripts/tests-start.sh

# Run tests with coverage
bash scripts/test.sh

# Run specific test
uv run pytest app/tests/test_users.py -v
```

**Code Quality:**
```bash
# Lint and format check
uv run bash scripts/lint.sh

# Run pre-commit hooks manually
uv run pre-commit run --all-files
```

**Database Operations:**
```bash
# Create migration
docker compose exec backend alembic revision --autogenerate -m "Description"

# Run migrations
docker compose exec backend alembic upgrade head

# Database console
docker compose exec backend bash
```

### Docker Operations

**Full stack:**
```bash
# Start with file watching (development)
docker compose watch

# Build and start (production-like)
docker compose up -d

# Stop and cleanup
docker compose down -v

# View logs
docker compose logs backend
docker compose logs frontend
```

**Individual containers:**
```bash
# Execute commands in backend container
docker compose exec backend bash

# Execute commands in frontend container
docker compose exec frontend bash
```

### Build & Deployment

**Production build:**
```bash
# Build Docker images with tag
TAG=latest bash scripts/build.sh

# Generate OpenAPI client
bash scripts/generate-client.sh
```

### Script Command Consistency

**Important:** When modifying scripts, ensure all references are updated in:
- **GitHub Actions:** `.github/workflows/*.yml`
- **README files:** `README.md`, `backend/README.md`, `frontend/README.md`
- **Docker Compose:** `docker-compose.yml`, `docker-compose.override.yml`
- **Development docs:** `development.md`, `deployment.md`

**Critical script references:**
- Build commands → Check: workflows, deployment.md, docker-compose.yml
- Test commands → Check: workflows, backend/README.md
- Lint commands → Check: pre-commit hooks, workflows
- Development commands → Check: development.md, README.md

## Code Style

### Backend (Python)

**Framework:** FastAPI with SQLModel ORM
**Linting:** Ruff + MyPy (strict mode)
**Formatting:** Ruff format

**Code Conventions:**
- **Imports:** Absolute imports preferred, group by standard/third-party/local
- **Naming:** `snake_case` for variables/functions, `PascalCase` for classes/models
- **Type Hints:** Required for all functions and class attributes
- **Line Length:** 88 characters (Ruff default)
- **String Quotes:** Double quotes preferred

**SQLModel Patterns:**
```python
# Model definition
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    is_active: bool = True

# API endpoint pattern
@router.post("/", response_model=UserPublic)
def create_user(
    *,
    session: SessionDep,
    user_in: UserCreate,
) -> User:
    # Implementation
```

**Error Handling:**
```python
from fastapi import HTTPException

# Standard error pattern
if not user:
    raise HTTPException(
        status_code=404,
        detail="User not found"
    )
```

### Frontend (TypeScript/React)

**Framework:** React 19 + TypeScript + TanStack Router
**Linting:** Biome (replaces ESLint + Prettier)
**UI Framework:** Chakra UI v3

**Code Conventions:**
- **Imports:** Absolute imports with path mapping, group by external/internal
- **Naming:** `camelCase` for variables/functions, `PascalCase` for components/types
- **Components:** Function components with TypeScript interfaces
- **Hooks:** Custom hooks start with `use`, follow React rules of hooks
- **Files:** `kebab-case` for files, `PascalCase` for React components

**Component Pattern:**
```typescript
// Component definition
interface UserCardProps {
  user: User;
  onEdit?: (user: User) => void;
}

export function UserCard({ user, onEdit }: UserCardProps) {
  return (
    // JSX implementation
  );
}
```

**API Client Usage:**
```typescript
// Generated OpenAPI client
import { UsersService } from "@/client";
import { useMutation, useQuery } from "@tanstack/react-query";

// Query pattern
const { data: users } = useQuery({
  queryKey: ["users"],
  queryFn: () => UsersService.readUsers({}),
});
```

**Routing (TanStack Router):**
```typescript
// Route definition in src/routes/
export const Route = createFileRoute("/users")({
  component: UsersPage,
});
```

## Testing

### Backend Testing

**Framework:** pytest with FastAPI TestClient
**Coverage:** coverage.py with HTML reports (target: >85%)
**Database:** PostgreSQL test database with transactions

**Test Structure:**
```
backend/app/tests/
├── conftest.py          # Fixtures and test configuration
├── test_users.py        # User API tests
├── test_auth.py         # Authentication tests
└── utils.py            # Test utilities
```

**Test Patterns:**
```python
def test_create_user(client: TestClient, superuser_token_headers: dict):
    data = {"email": "test@example.com", "password": "testpass"}
    r = client.post(
        "/api/v1/users/",
        headers=superuser_token_headers,
        json=data,
    )
    assert r.status_code == 200
    created_user = r.json()
    assert created_user["email"] == data["email"]
```

**Run specific tests:**
```bash
# Single test file
uv run pytest app/tests/test_users.py -v

# Single test function
uv run pytest app/tests/test_users.py::test_create_user -v

# With coverage
uv run pytest --cov=app --cov-report=html
```

### Frontend Testing

**Framework:** Playwright for E2E testing
**Configuration:** `playwright.config.ts`
**Test Structure:**
```
frontend/tests/
├── auth.test.ts         # Authentication flows
├── users.test.ts        # User management
└── utils.ts            # Test utilities
```

**Test Patterns:**
```typescript
test('user login flow', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[placeholder="Email"]', 'admin@example.com');
  await page.fill('[placeholder="Password"]', 'changethis');
  await page.click('button[type="submit"]');

  await expect(page.locator('text=Dashboard')).toBeVisible();
});
```

**Run specific tests:**
```bash
# All tests
npx playwright test

# Specific test file
npx playwright test auth.test.ts

# Interactive debugging
npx playwright test --debug
```

### Testing Philosophy

**When tests fail, fix the code, not the test.**

**Key Principles:**
- **Test Realistic Scenarios:** Use actual API calls and database operations
- **Maintain Test Data:** Use factories and fixtures for consistent test data
- **Test Edge Cases:** Authentication failures, validation errors, permission boundaries
- **Fast Feedback:** Unit tests should run in <5 seconds, E2E tests in <30 seconds
- **Parallel Execution:** Tests must be independent and thread-safe
- **Clear Assertions:** Each test should verify one specific behavior

**Test Categories:**
- **Unit Tests:** Individual functions and classes (backend only)
- **Integration Tests:** API endpoints with database operations
- **E2E Tests:** Complete user workflows through the browser
- **Contract Tests:** API response schemas match OpenAPI specification

## Security

### Authentication & Authorization

**Backend Security:**
- **JWT Tokens:** HS256 signing with configurable SECRET_KEY
- **Password Hashing:** bcrypt via PassLib with secure defaults
- **Session Management:** Stateless JWT with 60-minute expiration
- **CORS:** Configured for frontend domain only in production

**Authorization Patterns:**
```python
from app.api.deps import CurrentUser, SessionDep

# Protected endpoint
@router.get("/me")
def read_current_user(current_user: CurrentUser) -> UserPublic:
    return current_user
```

### Data Protection

**Database Security:**
- **Connection Security:** PostgreSQL with password authentication
- **Migration Safety:** Alembic migrations with backup recommendations
- **Sensitive Data:** Never log passwords, tokens, or personal information

**Environment Variables:**
- **Required Secrets:** SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD
- **Azure AD Secrets:** AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
- **Redis Configuration:** REDIS_HOST, REDIS_PORT, REDIS_PASSWORD (optional)
- **Secret Management:** Use environment variables, never commit secrets
- **Production:** Secrets via CI/CD variables or secret management service

**Input Validation:**
```python
from pydantic import EmailStr, Field

class UserCreate(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None
```

### Frontend Security

**Client-Side Protection:**
- **XSS Prevention:** React's built-in XSS protection, avoid dangerouslySetInnerHTML
- **CSRF:** Not applicable for SPA with JWT (stateless)
- **Content Security Policy:** Configure for production deployment

**API Security:**
```typescript
// Token management
const token = localStorage.getItem('access_token');
if (token) {
  // Include in API calls
  headers: { Authorization: `Bearer ${token}` }
}
```

## Directory Structure & File Organization

### Backend Structure
```
backend/
├── app/
│   ├── api/              # API route handlers
│   │   ├── deps.py      # Dependency injection
│   │   └── routes/      # Route modules
│   ├── core/            # Core configuration
│   │   ├── config.py    # Settings management
│   │   ├── db.py        # Database connection
│   │   └── security.py  # Auth utilities
│   ├── models/          # SQLModel definitions
│   ├── crud/            # Database operations
│   ├── tests/           # Test suite
│   └── main.py         # FastAPI application
├── scripts/             # Build and deployment scripts
├── alembic/             # Database migrations
└── pyproject.toml       # Dependencies and config
```

### Frontend Structure
```
frontend/
├── src/
│   ├── client/          # Generated OpenAPI client (don't edit)
│   ├── components/      # Reusable React components
│   ├── routes/          # TanStack Router pages
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Utility functions
│   └── theme/           # Chakra UI theme customization
├── tests/               # Playwright E2E tests
├── public/              # Static assets
├── package.json         # Dependencies and scripts
└── vite.config.ts       # Build configuration
```

### Reports Directory
ALL project reports and documentation should be saved to the `reports/` directory:

```
fastapi-fastmcp-azureAD/
├── reports/              # All project reports and documentation
│   ├── README.md        # Report directory documentation
│   ├── TEST_RESULTS_*.md # Test execution reports
│   ├── COVERAGE_*.md    # Code coverage analysis
│   └── PERFORMANCE_*.md # Performance benchmarks
└── temp/                # Temporary files and debugging
```

**Report Generation Guidelines:**
- **Test Reports:** `TEST_RESULTS_[COMPONENT]_[DATE].md`
- **Coverage Reports:** `COVERAGE_REPORT_[DATE].md`
- **Performance Analysis:** `PERFORMANCE_[SCENARIO]_[DATE].md`
- **Security Scans:** `SECURITY_SCAN_[DATE].md`
- **Implementation Reports:** `FEATURE_[NAME]_COMPLETION.md`

### Temporary Files & Debugging
All temporary files should be organized in `/temp` folder:
- **Debug scripts:** `temp/debug-*.py`, `temp/analyze-*.js`
- **Test artifacts:** `temp/test-results/`, `temp/coverage/`
- **Log files:** `temp/logs/debug.log`

### Git Ignore Patterns
```gitignore
# Temporary files
/temp/
**/temp/
debug-*.py
test-*.js
*.debug

# Generated files
/frontend/src/client/  # Don't ignore entire directory
coverage/
htmlcov/
.coverage

# Environment
.env.local
.env.*.local

# Claude settings
.claude/settings.local.json
```

## Configuration

### Environment Setup

**Backend (.env):**
```bash
# Required for production
SECRET_KEY="your-secret-key-here"
FIRST_SUPERUSER_PASSWORD="changethis"
POSTGRES_PASSWORD="changethis"

# Azure AD Configuration
AZURE_TENANT_ID="your-tenant-id"
AZURE_CLIENT_ID="your-client-id"
AZURE_CLIENT_SECRET="your-client-secret"
AZURE_REDIRECT_URI="http://localhost:8000/auth/callback"

# Redis Configuration
REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_PASSWORD=""  # Optional
REDIS_SSL="false"

# Development defaults
ENVIRONMENT=local
DOMAIN=localhost
PROJECT_NAME="Full Stack FastAPI Project"
BACKEND_CORS_ORIGINS="http://localhost:5173"
```

**Frontend (.env):**
```bash
VITE_API_URL=http://localhost:8000
```

### Development Requirements

**Backend:**
- **Python:** 3.10-3.13
- **Package Manager:** uv (recommended) or pip
- **Database:** PostgreSQL (via Docker)

**Frontend:**
- **Node.js:** Version specified in `.nvmrc`
- **Package Manager:** npm (lockfile committed)
- **Browser:** Chrome/Chromium for Playwright

### Production Configuration

**Docker Compose Services:**
- **backend:** FastAPI application
- **frontend:** Static React build via nginx
- **db:** PostgreSQL with persistent volumes
- **traefik:** Reverse proxy with SSL certificates

**Required Environment Variables:**
- `DOMAIN` - Production domain name
- `SECRET_KEY` - JWT signing key (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- `POSTGRES_PASSWORD` - Database password
- `FIRST_SUPERUSER_PASSWORD` - Initial admin password

## Agent Delegation & Tool Execution

### ⚠️ MANDATORY: Always Delegate to Specialists & Execute in Parallel

**When specialized agents are available, you MUST use them instead of attempting tasks yourself.**

**When performing multiple operations, send all tool calls (including Task calls for agent delegation) in a single message to execute them concurrently for optimal performance.**

### FastAPI-Specific Agent Priorities

**Backend Development:**
- **Python Expert** → SQLModel patterns, FastAPI endpoints, Pydantic validation
- **Database Expert** → PostgreSQL queries, Alembic migrations, performance optimization
- **Security Engineer** → Authentication flows, JWT handling, input validation
- **Testing Expert** → pytest patterns, TestClient usage, database fixtures

**Frontend Development:**
- **React Expert** → Component patterns, hooks, TanStack Router
- **TypeScript Expert** → Type definitions, API client integration
- **CSS/Styling Expert** → Chakra UI theming, responsive design
- **Playwright Expert** → E2E test automation, browser testing

**DevOps & Infrastructure:**
- **Docker Expert** → Container optimization, multi-stage builds
- **DevOps Expert** → GitHub Actions, deployment pipelines
- **Performance Engineer** → Load testing, optimization, monitoring

### Critical: Always Use Parallel Tool Calls

**These cases MUST use parallel tool calls:**
- Reading multiple configuration files (backend + frontend)
- Searching for imports, usage patterns, and definitions simultaneously
- Running tests while checking code quality (lint + test in parallel)
- Analyzing both backend and frontend code for full-stack features
- Multiple grep searches across different file types (`.py`, `.ts`, `.yml`)

**Planning Approach for Full-Stack Tasks:**
1. **Identify Scope:** Backend only, frontend only, or full-stack?
2. **Plan Parallel Analysis:** What information do I need from both sides?
3. **Execute Concurrently:** Send all tool calls in a single message
4. **Cross-Reference:** How do backend changes affect frontend and vice versa?

**Performance Impact:** This full-stack architecture benefits significantly from parallel execution since backend and frontend can be analyzed independently before integration.

### Available Specialized Agents

Check for these domain-specific agents using `claudekit list agents`:
- **fastapi-expert** - FastAPI patterns, SQLModel, API design
- **react-expert** - React patterns, hooks, component architecture
- **typescript-expert** - TypeScript types, API client generation
- **docker-expert** - Container optimization, multi-service orchestration
- **testing-expert** - pytest + Playwright integration testing
- **security-engineer** - JWT, auth flows, input validation
- **performance-engineer** - Database optimization, caching strategies

**Default to parallel execution and expert delegation for all non-trivial tasks.**
