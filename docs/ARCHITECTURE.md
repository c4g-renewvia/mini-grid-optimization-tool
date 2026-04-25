# Technical Architecture - Mini-Grid Optimization Tool

## Overview

The Mini-Grid Optimization Tool is a full-stack web application that helps users optimize mini-grid network designs. It combines a modern frontend for user interaction with a powerful backend for complex optimization algorithms.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER (Browser)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    React 19 Application                             │     │
│  │  ┌──────────────────────────────────────────────────────────────┐  │     │
│  │  │  Components:                                                 │  │     │
│  │  │  • MapControls (Google Maps Integration)                     │  │     │
│  │  │  • SavedGridsSection (CRUD operations)                       │  │     │
│  │  │  • CostsSolver (Solver Interface)                            │  │     │
│  │  │  • DefineMarkers (Node Definition)                           │  │     │
│  │  │  • ExportSummary (Results Export)                            │  │     │
│  │  │  • SidebarUserMenu (User Account)                            │  │     │
│  │  └──────────────────────────────────────────────────────────────┘  │     │
│  │                                                                       │     │
│  │  ┌──────────────────────────────────────────────────────────────┐  │     │
│  │  │  UI Libraries:                                               │  │     │
│  │  │  • Shadcn/RadixUI (Buttons, Dialogs, Tabs)                   │  │     │
│  │  │  • Lucide Icons                                              │  │     │
│  │  │  • AG-Grid (Data Tables)                                     │  │     │
│  │  │  • Tailwind CSS (Styling)                                    │  │     │
│  │  └──────────────────────────────────────────────────────────────┘  │     │
│  │                                                                       │     │
│  │  ┌──────────────────────────────────────────────────────────────┐  │     │
│  │  │  State Management & Utils:                                   │  │     │
│  │  │  • React Context (Theme, Notifications)                      │  │     │
│  │  │  • Hooks (useIsTheme, usePushNotifications, useToast)        │  │     │
│  │  │  • Next-Themes (Dark/Light Mode)                             │  │     │
│  │  └──────────────────────────────────────────────────────────────┘  │     │
│  │                                                                       │     │
│  │  ┌──────────────────────────────────────────────────────────────┐  │     │
│  │  │  Features:                                                   │  │     │
│  │  │  • Service Worker (PWA & Push Notifications)                 │  │     │
│  │  │  • Offline Support                                           │  │     │
│  │  │  • Google Maps Integration                                   │  │     │
│  │  │  • CSV Import/Export                                         │  │     │
│  │  └──────────────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │                    NextAuth v5 (Authentication)                     │     │
│  │  • Google OAuth 2.0 Provider                                        │     │
│  │  • Session Management                                              │     │
│  │  • JWT Tokens                                                       │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │  HTTPS / WebSocket Connection │
                    └───────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY LAYER (Next.js Server)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │           Next.js App Router (Route Handlers)                      │     │
│  │                                                                     │     │
│  │  POST   /api/auth/*              → NextAuth Auth Routes            │     │
│  │  GET    /api/health              → Health Check                    │     │
│  │  POST   /api/minigrids           → Create Mini-Grid Run            │     │
│  │  GET    /api/minigrids           → Fetch User's Runs               │     │
│  │  GET    /api/minigrids/[id]      → Get Specific Run                │     │
│  │  POST   /api/export-csv          → Export Results to CSV            │     │
│  │  POST   /api/notifications/send  → Send Push Notifications         │     │
│  │  GET    /api/users/profile       → Get User Profile                │     │
│  │  POST   /api/impersonate         → Admin Impersonation             │     │
│  │                                                                     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │        Prisma Client (Database ORM)                                │     │
│  │  • User Model                                                       │     │
│  │  • MiniGridRun Model                                               │     │
│  │  • Account & Session Models (NextAuth)                             │     │
│  │  • UserRole & VerificationToken Models                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │        Utilities & Services                                         │     │
│  │  • Web Push Service                                                 │     │
│  │  • Email Service (Resend)                                           │     │
│  │  • CSV Export Utility                                               │     │
│  │  • Authentication Helper                                            │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
        ▼                                           ▼
┌──────────────────────────┐        ┌──────────────────────────────┐
│   PostgreSQL Database    │        │   Python Backend (FastAPI)   │
│   (localhost:5432)       │        │   (localhost:8000)           │
│                          │        │                              │
│  ┌──────────────────┐    │        │  ┌──────────────────────┐    │
│  │ Users Table      │    │        │  │ /solve Endpoint      │    │
│  │ • id (UUID)      │    │        │  │ POST Request Handler │    │
│  │ • email          │    │        │  │ • Validates input    │    │
│  │ • name           │    │        │  │ • Selects solver     │    │
│  │ • emailVerified  │    │        │  │ • Returns result     │    │
│  │ • role           │    │        │  └──────────────────────┘    │
│  │ • image          │    │        │                              │
│  │ • pushSub        │    │        │  ┌──────────────────────┐    │
│  │ • createdAt      │    │        │  │ /local_optimization  │    │
│  │ • updatedAt      │    │        │  │ Refines Solutions    │    │
│  └──────────────────┘    │        │  └──────────────────────┘    │
│                          │        │                              │
│  ┌──────────────────┐    │        │  ┌──────────────────────┐    │
│  │ MiniGridRun      │    │        │  │ /solvers Endpoint    │    │
│  │ • id (UUID)      │    │        │  │ GET Available Solvers│    │
│  │ • userId (FK)    │    │        │  └──────────────────────┘    │
│  │ • name           │    │        │                              │
│  │ • fileName       │    │        │  ┌──────────────────────┐    │
│  │ • miniGridNodes  │    │        │  │ CORS Middleware      │    │
│  │ • miniGridEdges  │    │        │  │ • localhost:3000     │    │
│  │ • costBreakdown  │    │        │  │ • Vercel Domain      │    │
│  │ • poleCost       │    │        │  └──────────────────────┘    │
│  │ • createdAt      │    │        │                              │
│  │ • updatedAt      │    │        │  ┌──────────────────────┐    │
│  └──────────────────┘    │        │  │ Solver Registry      │    │
│                          │        │  │ • MST Solver         │    │
│  ┌──────────────────┐    │        │  │ • Greedy Steiner     │    │
│  │ Accounts Table   │    │        │  │ • Disk Steiner       │    │
│  │ • NextAuth Data  │    │        │  │ • Biniaz Disk        │    │
│  │ • OAuth Tokens   │    │        │  │ • Local Optimization │    │
│  └──────────────────┘    │        │  └──────────────────────┘    │
│                          │        │                              │
│  ┌──────────────────┐    │        │  ┌──────────────────────┐    │
│  │ Sessions Table   │    │        │  │ Solver Algorithms    │    │
│  │ • Session Data   │    │        │  │ • NetworkX (Graphs)  │    │
│  │ • User Reference │    │        │  │ • Shapely (Geometry) │    │
│  │ • Expiry         │    │        │  │ • SciPy (Scientific) │    │
│  └──────────────────┘    │        │  │ • Scikit-learn       │    │
│                          │        │  │ • Pandas (Data)      │    │
│  ┌──────────────────┐    │        │  │ • Matplotlib (Plot)  │    │
│  │ UserRole Table   │    │        │  └──────────────────────┘    │
│  │ • Role Definitions   │        │                              │
│  │ • Permissions        │        │  ┌──────────────────────┐    │
│  └──────────────────┘    │        │  │ Input Processing     │    │
│                          │        │  │ • KML File Parsing   │    │
└──────────────────────────┘        │  │ • Node Validation    │    │
                                    │  │ • Edge Creation      │    │
                                    │  └──────────────────────┘    │
                                    │                              │
                                    │  ┌──────────────────────┐    │
                                    │  │ Output Generation    │    │
                                    │  │ • SolverResult JSON  │    │
                                    │  │ • Cost Breakdown     │    │
                                    │  │ • Topology Data      │    │
                                    │  └──────────────────────┘    │
                                    │                              │
                                    └──────────────────────────────┘
```

---

## Frontend Architecture (Next.js)

### Technology Stack
- **Framework**: Next.js 16.1.6
- **Language**: TypeScript
- **Runtime**: Node.js 24+
- **UI Framework**: React 19.2.1
- **Styling**: Tailwind CSS 4.1.18
- **Package Manager**: pnpm 10.29.2

### Key Components

#### Authentication Layer
- **NextAuth v5 Beta**: Google OAuth 2.0 provider
- **Session Management**: JWT-based sessions
- **Protected Routes**: API middleware validation

#### Frontend Components

1. **Map Interface** (`MapControls.tsx`)
   - Google Maps integration
   - Node/marker placement
   - Real-time map updates

2. **Mini-Grid Management** (`SavedGridsSection.tsx`)
   - CRUD operations for saved grids
   - History tracking
   - AG-Grid data display

3. **Solver Interface** (`costs-solver/`)
   - Algorithm selection
   - Parameter configuration
   - Results visualization

4. **Marker Definition** (`define-markers/`)
   - Node coordinate input
   - Building data import
   - CSV processing

5. **Results Export** (`export-summary/`)
   - CSV export functionality
   - Cost breakdown visualization
   - PDF generation (optional)

#### State Management
- React Context API for global state
- Custom hooks for business logic
- NextAuth session context

#### UI Component Libraries
- **Shadcn**: Custom UI components
- **RadixUI**: Accessible component primitives
- **Lucide Icons**: Icon library
- **AG-Grid Community**: Data table component

#### PWA Features
- Service Worker (`/public/sw.js`)
- Web Push Notifications
- Offline capability
- Push subscription management

#### External Integrations
- **Google Maps API**: Location visualization
- **Resend Email**: Transactional emails
- **Web Push Protocol**: Browser notifications

---

## Backend Architecture (Python FastAPI)

### Technology Stack
- **Framework**: FastAPI 0.135.3
- **Server**: Uvicorn 0.44.0
- **Language**: Python 3.13+
- **API Style**: REST with Pydantic validation

### API Endpoints

#### Solve Endpoints
```
POST /solve
├── Input: SolverRequest
│   ├── solver: str (algorithm name)
│   ├── nodes: List[Node] (coordinates + metadata)
│   └── edges: List[Edge] (optional connections)
└── Output: SolverResult
    ├── edges: List[Edge] (optimal connections)
    ├── cost: float (total cost)
    └── metrics: dict (performance data)

POST /local_optimization
├── Input: SolverRequest (from /solve output)
└── Output: SolverResult (refined solution)

GET /solvers
└── Output: List[Solver]
    ├── name: str
    └── params: List[Parameter]
```

#### CORS Configuration
```python
Allowed Origins:
- http://localhost:3000 (Development)
- http://localhost:8000 (Development)
- https://mini-grid-optimization-tool.vercel.app (Production)
```

### Solver Registry

The system implements a pluggable solver architecture:

1. **MST Solver** (`mst_solver.py`)
   - Minimum Spanning Tree algorithm
   - Baseline solution

2. **Greedy Iterative Steiner Solver** (`greedy_iter_steiner_solver.py`)
   - Iterative refinement
   - Steiner tree approximation

3. **Disk-Based Steiner Solver** (`disk_based_steiner_solver.py`)
   - Disk geometry optimization
   - Topology constraints

4. **Biniaz Disk Steiner Solver** (`biniaz_disk_steiner_solver.py`)
   - Advanced algorithm variant
   - Enhanced accuracy

5. **Local Optimization** (`local_opt.py`)
   - Post-processing refinement
   - Cost minimization

### Core Libraries

| Library | Purpose |
|---------|---------|
| **NetworkX** | Graph algorithms and analysis |
| **Shapely** | Geometric operations and validation |
| **SciPy** | Scientific computing and optimization |
| **Scikit-learn** | Machine learning utilities |
| **Pandas** | Data manipulation and analysis |
| **NumPy** | Numerical computing |
| **Matplotlib** | Data visualization |
| **PyKML** | KML file processing |
| **Pydantic** | Data validation and serialization |

### Data Models

```python
class SolverRequest:
    solver: str
    nodes: List[Dict]  # Node coordinates and metadata
    edges: List[Dict]  # Optional existing connections

class SolverResult:
    edges: List[Dict]
    cost: float
    poleCost: float
    lowVoltageCost: float
    highVoltageCost: float
    metrics: Dict
```

---

## Database Architecture

### PostgreSQL Schema

#### Core Tables

1. **User**
   - Authentication and profile data
   - Role-based access control
   - Push notification subscriptions

2. **MiniGridRun**
   - Stores optimization results
   - Linked to user account
   - JSON storage for flexible data

3. **Account** (NextAuth)
   - OAuth provider credentials
   - Token management

4. **Session** (NextAuth)
   - User session tracking
   - Expiration management

5. **UserRole**
   - Role definitions
   - Permission management

#### Relationships
```
User (1) ──→ (Many) MiniGridRun
User (1) ──→ (Many) Account
User (1) ──→ (Many) Session
User (1) ──→ (Many) UserRole
```

#### Data Persistence
- Results stored as JSON in MiniGridRun
- Enables schema flexibility
- Indexed on userId and createdAt for performance

---

## Deployment Architecture

### Containerization

#### Frontend Container

```dockerfile
# Node.js container
FROM node:24-alpine
WORKDIR /app
COPY package*.json ./
RUN pnpm install
COPY .. .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
```

#### Backend Container
```dockerfile
# Python container
FROM python:3.13
WORKDIR /app
COPY pyproject.toml ./
RUN pip install -e .
COPY . .
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0"]
```

### Local Development (Docker Compose)
```yaml
Services:
- frontend (Next.js, port 3000)
- backend (FastAPI, port 8000)
- postgres (PostgreSQL, port 5432)
- nginx (Reverse proxy, port 80)
```

### Production Deployment

#### Frontend
- **Platform**: Vercel
- **Build**: Standalone output
- **CI/CD**: GitHub Actions
- **Domain**: mini-grid-optimization-tool.vercel.app

#### Backend
- **Platform**: Vercel (Python runtime)
- **Deployment**: GitHub Actions workflow
- **Secrets**: VERCEL_ORG_ID, VERCEL_PROJECT_ID, VERCEL_TOKEN

---

## Data Flow Diagrams

### User Registration & Authentication Flow
```
1. User visits app
   ↓
2. Redirected to Google OAuth
   ↓
3. User authenticates with Google
   ↓
4. Google returns access token
   ↓
5. NextAuth creates session
   ↓
6. Session stored in database
   ↓
7. JWT cookie created
   ↓
8. User redirected to app
```

### Mini-Grid Optimization Flow
```
1. User defines nodes on map
   ↓
2. Frontend validates input
   ↓
3. Request sent to POST /api/minigrids
   ↓
4. Next.js API route validates auth
   ↓
5. Request forwarded to Backend /solve
   ↓
6. Backend validates 2+ nodes
   ↓
7. Solver selected from registry
   ↓
8. Algorithm executes
   ↓
9. Result returned as JSON
   ↓
10. Frontend stores in database via POST
    ↓
11. Results displayed and cached
```

### Push Notification Flow
```
1. User enables notifications
   ↓
2. Service Worker creates subscription
   ↓
3. Subscription sent to backend
   ↓
4. Stored in User.pushSubscription
   ↓
5. Backend generates VAPID keys
   ↓
6. Sends notification via web-push
   ↓
7. Browser displays notification
   ↓
8. User can interact with notification
```

---

## Security Architecture

### Authentication & Authorization
- **OAuth 2.0** via Google provider
- **NextAuth** manages session lifecycle
- **JWT tokens** for API authentication
- **Role-based access control** (RBAC)

### Environment Secrets
```
Frontend:
- AUTH_GOOGLE_ID
- AUTH_GOOGLE_SECRET
- NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
- NEXT_PUBLIC_VAPID_PUBLIC_KEY

Backend:
- VAPID_PRIVATE_KEY
- DATABASE_URL
- NEXTAUTH_SECRET

Deployment:
- VERCEL_ORG_ID
- VERCEL_PROJECT_ID
- VERCEL_TOKEN
```

### HTTPS & CORS
- All production traffic encrypted
- CORS policies restrict origins
- Service Worker requires HTTPS

---

## Performance Considerations

### Frontend Optimization
- **Code Splitting**: Dynamic imports for components
- **Image Optimization**: Next.js automatic optimization
- **Caching Strategy**: Service Worker caching
- **Bundle Size**: Shadcn components are tree-shakeable

### Backend Optimization
- **Algorithm Efficiency**: O(n log n) to O(n²) complexity depending on solver
- **JSON Serialization**: Efficient Pydantic models
- **Connection Pooling**: Database connection management
- **Async Processing**: FastAPI async route handlers

### Database Optimization
- **Indexes**: On userId and createdAt in MiniGridRun
- **Query Optimization**: Prisma intelligent query generation
- **Connection Caching**: Prisma connection pooling

---

## Development Workflow

### Local Setup
```bash
# Install dependencies
pnpm install

# Initialize database
pnpm run init

# Start development server
pnpm run dev

# Start backend separately
cd backend && python -m uvicorn server:app --reload
```

### Deployment Process
```bash
# Frontend: Automatic on push to main
# Backend: GitHub Actions workflow on backend/* changes

# Manual deployment:
cd backend
vercel deploy --prod
```

---

## CI/CD Pipeline

### GitHub Actions Workflows

1. **Backend Deploy** (`backend_deploy.yml`)
   - Triggers on backend/* changes
   - Runs on self-hosted runner
   - Deploys to Vercel production

2. **Frontend Deploy** (Vercel connected)
   - Automatic on main branch push
   - Runs linting and tests
   - Deploys to Vercel

---

## Monitoring & Logging

### Frontend Monitoring
- Vercel Analytics integration
- Vercel Speed Insights
- Browser console logging

### Backend Logging
- Python logging module
- FastAPI request logging
- Error tracking via exceptions

### Database Monitoring
- Prisma Studio for manual inspection
- Query performance analysis
- Connection pool monitoring

---

## Offline / Desktop Architecture

The tool supports an offline mode that replaces the PostgreSQL + Docker + Google OAuth stack with a lightweight local setup. The standard web deployment is unaffected.

### Database

Offline mode uses SQLite via Prisma's `@prisma/adapter-better-sqlite3` driver adapter. A duplicate schema lives in `prisma/schema-offline/` (SQLite provider, `String?` instead of the `UserRole` enum). The active database file is stored in the OS-managed user data directory, not alongside the application files:
- macOS: `~/Library/Application Support/minigrid-solver/offline.db`
- Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/minigrid-solver/offline.db`
- Windows (Electron): `%APPDATA%/minigrid-tool/offline.db`

### Authentication

When `OFFLINE_MODE=true` and no Google OAuth credentials are provided, `src/lib/auth.ts` returns a hardcoded anonymous session (`id: 'anonymous-user'`). The sidebar hides all auth UI (sign-in, profile, notifications) for this user and shows only the theme switcher. If Google OAuth credentials are provided in the setup, the standard NextAuth flow runs normally.

### Solver Binary

The Python FastAPI backend is compiled into a single-file executable via PyInstaller (`backend/build-solver.py`). The binary bundles all solver dependencies (NetworkX, SciPy, Shapely, etc.) and requires no Python installation on the host. Matplotlib's font cache is written to the OS cache directory (`platformdirs.user_cache_dir`) to avoid a slow rebuild on every launch.

### Distribution Formats

| Format | Audience | Contents |
|--------|----------|----------|
| **Developer mode** (`make offline`) | Developers | Source tree, `next dev`, `uv run uvicorn` |
| **Standalone bundle** (`.zip`) | Non-devs with Node.js | PyInstaller solver binary, Next.js standalone server, setup/start shell scripts |
| **Desktop app** (`.dmg`/`.exe`/`.AppImage`) | End users | Electron wrapper bundling a Node runtime, the standalone server, and the solver binary |

### Electron Desktop App

The Electron app (`electron/`) spawns two child processes: the solver binary and the Next.js standalone server (via a bundled Node runtime). Configuration (Google Maps API key, optional OAuth credentials) is stored in `app.getPath('userData')/config.json`. Logs go to `app.getPath('logs')`. The app detects version changes via a build-time commit hash baked into `build-info.json`; on mismatch, it deletes the old config and re-runs setup. The database is preserved across updates.

```
Electron Main Process
├── Solver Binary (port 8000, 127.0.0.1)
├── Node + Next.js Standalone Server (port 3000, 127.0.0.1)
│   ├── OFFLINE_MODE=true
│   ├── DATABASE_URL=file:<userData>/offline.db
│   └── GOOGLE_MAPS_API_KEY=<from config.json>
└── BrowserWindow → http://localhost:3000
```

---

## Future Architecture Improvements

1. **Message Queue**: Redis for async job processing
2. **Caching Layer**: Redis for API response caching
3. **CDN**: CloudFront for static asset delivery
4. **Microservices**: Separate solver service
5. **Real-time Updates**: WebSocket support for live results
6. **API Rate Limiting**: Protection against abuse
7. **Advanced Monitoring**: DataDog or New Relic integration
8. **ML Pipeline**: Result prediction and optimization

---

## Glossary

| Term | Definition |
|------|-----------|
| **Steiner Tree** | Optimal network connecting points with minimal edges |
| **MST** | Minimum Spanning Tree - connects all nodes with minimum cost |
| **CORS** | Cross-Origin Resource Sharing - policy for cross-domain requests |
| **JWT** | JSON Web Token - stateless authentication token |
| **OAuth 2.0** | Industry-standard authorization protocol |
| **PWA** | Progressive Web App - web app with native-like features |
| **ORM** | Object-Relational Mapping - abstracts database queries |

---

**Document Version**: 1.1  
**Last Updated**: April 25, 2026  
**Maintained By**: C4G Renewvia Team

