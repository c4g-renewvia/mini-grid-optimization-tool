# Mini-Grid Optimization Tool

The **Mini-Grid Optimization Tool** is a full-stack web application designed to help engineers and planners optimize mini-grid network designs. It provides a geographical interface to define nodes (consumers, generation sites) and uses advanced optimization algorithms to find the most cost-effective network topology.

## Key Features

- **Interactive Map Interface**: Place and manage nodes directly on Google Maps.
- **Advanced Optimization Solvers**: Multiple algorithms including MST, Steiner Tree approximations, and Local Optimization.
- **Cost Analysis**: Real-time cost breakdown based on poles, low-voltage lines, and high-voltage lines.
- **Data Management**: Import/Export node data via CSV and KML; save and revisit previous optimization runs.
- **Progressive Web App (PWA)**: Installable on mobile and desktop with offline support and push notifications.

---

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:
- [Node.js](https://nodejs.org/) (v24 or higher)
- [pnpm](https://pnpm.io/) (v10 or higher)
- [Python](https://www.python.org/) (v3.13 or higher)
- [Docker](https://www.docker.com/) (for database and local containerized execution)
- 
- [Make](https://www.gnu.org/software/make/) (optional, for simplified setup)

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/c4g-renewvia/mini-grid-optimization-tool.git
   cd mini-grid-optimization-tool
   ```

2. Create a `.env` file in the root directory. You can use `example.env` as a template. You will need the following API keys:
   - `AUTH_GOOGLE_ID`: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - `AUTH_GOOGLE_SECRET`: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - `NEXT_PUBLIC_VAPID_PUBLIC_KEY`: [VAPID Key Generator](https://knock.app/tools/vapid-key-generator)
   - `VAPID_PRIVATE_KEY`: [VAPID Key Generator](https://knock.app/tools/vapid-key-generator)
   - 
### Local Development

#### 1. Frontend & Database
Install Node dependencies and initialize the database:
```bash
pnpm install
pnpm run init # Starts Docker, applies Prisma migrations, and seeds the DB
```

Start the development server:
```bash
pnpm run dev
```
Open [http://localhost:3000](http://localhost:3000) to view the app.

#### 2. Backend (Optimization Solver)
The backend is a FastAPI server located in the `/backend` directory.
```bash
cd backend
pip install -e .
uvicorn server:app --reload --port 8000
```

---

## Running with Docker

Install and run Docker Compose (V2.X+) (Desktop). [Docker Compose](https://docs.docker.com/compose/install) is required for local development.

Ensure the `.env` file in the root directory.

```bash
# Using Make
make

# OR Using Docker Compose directly
docker compose --profile local up -d --build
```

Access the tool at [http://localhost:3000](http://localhost:3000).

---

## Optimization Solvers

The tool includes several pluggable solvers located in `backend/mini_grid_solver/solvers/`:

- **MST Solver**: Uses Minimum Spanning Tree to connect all nodes with minimal total length.
- **Greedy Iterative Steiner Solver**: An iterative approach to finding Steiner points to reduce network cost.
- **Disk-Based Steiner Solver**: Optimizes network topology based on disk geometry constraints.
- **Biniaz Disk Steiner Solver**: Advanced variant for enhanced accuracy in Steiner tree construction.
- **Local Optimization**: A post-processing step that refines existing solutions to further minimize costs.

---

## Project Architecture

- **Frontend**: Next.js 16 (React 19, TypeScript, Tailwind CSS, Shadcn UI)
- **Backend API**: FastAPI (Python 3.13)
- **Database**: PostgreSQL with Prisma ORM
- **Authentication**: NextAuth.js (Google OAuth)
- **Optimization**: NetworkX, SciPy, Shapely, Scikit-learn

For more details, see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [architecture.png](docs/architecture.png).

---

## Technologies Used

- **Frameworks**: [Next.js](https://nextjs.org/), [FastAPI](https://fastapi.tiangolo.com/)
- **UI/UX**: [Tailwind CSS](https://tailwindcss.com/), [Shadcn UI](https://ui.shadcn.com/), [Lucide Icons](https://lucide.dev/), [AG-Grid](https://www.ag-grid.com/)
- **Database**: [PostgreSQL](https://www.postgresql.org/), [Prisma](https://www.prisma.io/)
- **State & Auth**: [NextAuth.js](https://authjs.dev/), [React Context](https://react.dev/learn/passing-data-deeply-with-context)
- **DevOps**: [Docker](https://www.docker.com/), [GitHub Actions](https://github.com/features/actions), [Nginx](https://nginx.org/)
- **Libraries**: [NetworkX](https://networkx.org/), [Shapely](https://shapely.readthedocs.io/), [SciPy](https://scipy.org/), [Pandas](https://pandas.pydata.org/)

## Team Members - Georgia Tech C4G (Spring 2026)
- Cody Kesler
- Harry Li
- Haden Sangree
- Emily Thomas
- Mlen-Too Wesley

## License

GPL License. See [LICENSE](LICENSE) for details.
