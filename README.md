# Mini-Grid Optimization Tool

The **Mini-Grid Optimization Tool** is a full-stack web application designed to help engineers and planners optimize mini-grid network designs.
The the mini-grid layout problem is a challenging NP-hard combinatorial optimization problem that involves connecting a set of nodes 
(representing households, businesses, or other terminal/demand points) to a power source with a cost-effective network of poles and lines. 

### Terminology:
- Terminal Node: A point that requires power (e.g., a household or business).
- Pole Node: A point that power can travel through (e.g., a transformer or substation).
- Source Node: A point that provides power (e.g., a generator or main grid connection).
- Edge: A connection between nodes that can be either low-voltage (up to 30m) or high-voltage (up to 50m), with different costs.

### Current Problem Constraints
- Maximum length of wire between poles (e.g., 30m for low-voltage lines, 50m for high-voltage lines)
- Maximum length of wire between poles and terminal nodes (e.g., 20m)
- Terminal Nodes are sink nodes (no wires allowed between terminal nodes)

---

## Core Concepts
This tool provides an intuitive interface for defining nodes and visualizing network topologies, along with powerful backend solvers to find optimal or near-optimal solutions.

It is built around 2 core concepts:

### Plug-and-Play:
Allows users to:
   - Switch between different optimization algorithms to compare results and cost
   - Contribute algorithmic solutions of their own to the project

### Human in the Loop:
Allows users to:
   - Visually review and analyze the optimization results
   - Manipulate network nodes directly on the map to test "what-if" scenarios and see real-time cost updates
   - Rerun optimization algorithms to update results
   - Export and import network data for future optimization runs
   - Save and revisit previous optimization runs


## Key Features

- **Interactive Map Interface**: Place and manage nodes directly on Google Maps.
- **Advanced Optimization Solvers**: Multiple algorithms including MST, Steiner Tree approximations, and Local Optimization.
- **Cost Analysis**: Real-time cost breakdown based on poles, low-voltage lines, and high-voltage lines.
- **Data Management**: Import/Export node data via CSV and KML; save and revisit previous optimization runs.
- **Progressive Web App (PWA)**: Installable on mobile and desktop with offline support.

---

## Optimization Solvers

The tool includes several pluggable solvers located in `backend/mini_grid_solver/solvers/`:

- **MST Solver**: Uses Minimum Spanning Tree to connect all nodes with minimal total length.
- **Greedy Iterative Steiner Solver**: An iterative approach to finding Steiner points to reduce network cost.
- **Disk-Based Steiner Solver**: Optimizes network topology based on disk geometry constraints.
- **Local Optimization**: A post-processing step that refines existing solutions to further minimize costs.

---

## Project Architecture

To enable the above concepts, the tool provides a modular system with 2 components:
1. A geographical Google Maps based interface to define and manipulate nodes and visualize network topologies.
2. A python based backend implementing optimization algorithms to find the most cost-effective network topology.

- **Frontend**: Next.js 16 (React 19, TypeScript, Tailwind CSS, Shadcn UI)
- **Backend API**: FastAPI (Python 3.13)
- **Database**: PostgreSQL with Prisma ORM
- **Authentication**: NextAuth.js (Google OAuth)
- **Optimization**: NetworkX, SciPy, Shapely, Scikit-learn

For more details, see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [architecture.png](docs/architecture.png).

---

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:
- [Node.js](https://nodejs.org/) (v24 or higher)
- [pnpm](https://pnpm.io/) (v10 or higher)
- [Python](https://www.python.org/) (v3.13 or higher)
- [Docker](https://www.docker.com/) (for database and local containerized execution)
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
   
     (Note: No environment variables are required for Docker Deployment)
   
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

Rename `.env.example` to `.env`.

```bash
# Using Make
make

# OR Using Docker Compose directly
docker compose --profile local up -d --build
```

Access the tool at [http://localhost:3000](http://localhost:3000).


---

## Running Offline (No Docker, No PostgreSQL)

The tool can also run in offline mode using a local SQLite database instead of PostgreSQL. No Docker, no Google OAuth credentials, and no internet connection (beyond Google Maps tile fetches) are required. There are three ways to run offline, depending on your audience:

### 1. Developer Mode

For developers with Node.js and Python already installed. Runs directly from the source tree.

**Prerequisites**: Node.js 24+, pnpm 10+, Python 3.13+, [uv](https://github.com/astral-sh/uv)

```bash
pnpm run offline:init   # Prompts for Google Maps API key, sets up SQLite DB
make offline             # Starts solver + Next.js dev server
```

Open [http://localhost:3000](http://localhost:3000). To switch back to the standard Postgres workflow, delete `.env.local` and run `pnpm exec prisma generate` against the default schema.

### 2. Standalone Bundle

For non-developers on Linux or macOS who have Node.js installed but not Python or Docker. Distributed as a `.zip` from GitHub Releases.

**Prerequisites**: Node.js 24+

```bash
unzip minigrid-tool-<platform>.zip
cd minigrid-tool
./setup.sh    # Prompts for Google Maps API key
./start.sh    # Starts solver binary + Next.js standalone server
```

The solver runs as a self-contained binary (PyInstaller); no Python installation needed on the host. User data (saved grid runs) is stored in an OS-managed directory and persists across updates.

### 3. Desktop App (Electron)

For end users on macOS, Windows, or Linux. No prerequisites.

Download the `.dmg` (macOS), `.exe` (Windows), or `.AppImage` (Linux) from GitHub Releases. On first launch the app prompts for a Google Maps API key. Google OAuth sign-in is optional and can be configured in the setup screen or later via the Settings menu.

**Notes**:
- macOS: The app is unsigned. Right-click > Open > click through the Gatekeeper warning on first launch.
- Windows: Click "More info" > "Run anyway" to dismiss the SmartScreen warning.
- There is no auto-updater. Download a new release to update.

---

## Technologies Used

- **Frameworks**: [Next.js](https://nextjs.org/), [FastAPI](https://fastapi.tiangolo.com/)
- **UI/UX**: [Tailwind CSS](https://tailwindcss.com/), [Shadcn UI](https://ui.shadcn.com/), [Lucide Icons](https://lucide.dev/), [AG-Grid](https://www.ag-grid.com/)
- **Database**: [PostgreSQL](https://www.postgresql.org/), [Prisma](https://www.prisma.io/)
- **State & Auth**: [NextAuth.js](https://authjs.dev/), [React Context](https://react.dev/learn/passing-data-deeply-with-context)
- **DevOps**: [Docker](https://www.docker.com/), [GitHub Actions](https://github.com/features/actions), [Nginx](https://nginx.org/)
- **Libraries**: [NetworkX](https://networkx.org/), [Shapely](https://shapely.readthedocs.io/), [SciPy](https://scipy.org/), [Pandas](https://pandas.pydata.org/)

---

# Team Members - Georgia Tech C4G

## Spring 2026
- Cody Kesler
- Harry Li
- Haden Sangree
- Emily Thomas
- Mlen-Too Wesley

## License

GPL License. See [LICENSE](LICENSE) for details.
