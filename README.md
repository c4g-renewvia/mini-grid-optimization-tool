# Georgia Tech C4G - Renewvia Project

## Spring 2026
Team Members: 
- Cody Kesler
- Harry Li
- Haden Sangree
- Emily Thomas
- Mlen-Too Wesley


## Getting Started

1. Make sure you have the following setup and configured on your computer:
   - [git](https://docs.github.com/en/get-started/getting-started-with-git/set-up-git) or [Github Desktop](https://desktop.github.com/download/)
   - [NodeJS](https://nodejs.org/en/download) - version 24 or higher
   - [pnpm](https://pnpm.io/installation) - Fast, disk space efficient package manager
   - [Docker](https://www.docker.com/get-started/)
2. Clone the repo using either SSH, HTTPS, or Github Desktop

- SSH

```bash
git clone git@github.gatech.edu:cs-6150-computing-for-good/template.git
```

- HTTPS

```bash
git clone https://github.gatech.edu/cs-6150-computing-for-good/template.git
```

3. Get the `.env` file from Microsoft teams or ask a TA for the file. This file will be specific to your project once this repo is cloned and must be created by a TA as we have to setup the github action secrets.
4. Install all of the node dependencies with the following command

```bash
pnpm install
```

5. Make sure you have docker running and run the following command to initialize the database, apply all database schema, and seed some test users:

```bash
pnpm run init
```

6. If all is well up to this point your terminal should look like this:
   ![Initialization Successful](/documentation/init_success.png?raw=true 'Initialization Successful')
7. Next, run the development server

```bash
pnpm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

8. Login with a gmail account


9. To access the database you can run the following command in a new terminal:

```bash
pnpm exec prisma studio
```

It should open the browser automatically or you can open [http://localhost:5555/](http://localhost:5555/) to see the database tables.

You can start editing the page by modifying `src/app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.


## Running the Tool Locally with Docker

### Requirements

- Docker
- .env file (ask TA for the file)

1. Clone the Mini-Grid Optimization Tool Repository

```bash
git clone https://github.com/c4g-renewvia/mini-grid-optimization-tool.git
```

2. Navigate into the directory

```bash
cd mini-grid-optimization-tool
```

3. Validate the .env file is setup. The following API Keys must be present:

- [AUTH_GOOGLE_ID](https://console.cloud.google.com/apis/credentials?project=c4g-template)
- [AUTH_GOOGLE_SECRET](https://console.cloud.google.com/apis/credentials?project=c4g-template)
- [NEXT_PUBLIC_GOOGLE_MAPS_API_KEY](https://console.cloud.google.com/apis/credentials?project=c4g-template)
- [NEXT_PUBLIC_VAPID_PUBLIC_KEY](https://knock.app/tools/vapid-key-generator)
- [VAPID_PRIVATE_KEY](https://knock.app/tools/vapid-key-generator)

3. Docker Compose to start the application locally

```bash
docker compose --profile local up -d --remove-orphans --build
```

4. Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

**Alternative**: Use the `make` ([Windows](https://gnuwin32.sourceforge.net/packages/make.htm) | [Linux](https://www.gnu.org/software/make/#download)) build tool to validate the .env file is setup and open the necessary web pages to retrieve the required keys if missing. Will also build the Docker images and start the application locally:

```bash
make
```

## Technologies Used

- [Nextjs](https://nextjs.org/) - framework
- [Typescript](https://www.typescriptlang.org/)
- [Tailwind](https://tailwindcss.com/) - css atomic classes
- [Prisma](https://www.prisma.io/) - db type ORM system
- [Prettier](https://prettier.io/) - formatter
- [ESLint](https://eslint.org/) - enforce rules / policies for maintable code
- [Husky](https://typicode.github.io/husky/) - allows for code changes during local commit
- [Lint-Staged](https://github.com/lint-staged/lint-staged) - lints code on only staged files with auto-fix
- [Docker](https://www.docker.com/) - containers
- [Postgres](https://www.postgresql.org/) - database
- [Github Actions](https://github.com/features/actions) - ci/cd process
- [Nginx](https://nginx.org/) - server hosting configuration / routing
- [Shadcn](https://ui.shadcn.com/) - UI component library
- [RadixUI](https://www.radix-ui.com/) - UI component library
- [Lucide-React](https://lucide.dev/guide/packages/lucide-react) - UI icons
- [Next-Auth](https://authjs.dev/) - authentication with google
- [Ag-Grid](https://www.ag-grid.com/) - grid / table component
- [Resend](https://resend.com) - emails

