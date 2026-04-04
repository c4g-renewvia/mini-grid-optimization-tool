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

## Manual Updates after cloning the template (by C4G staff)

1. Replace `template` in many files to your project name.
2. Setup oauth settings in [GCP](https://console.cloud.google.com/apis/credentials?project=c4g-template)
3. Setup nginx configuration, and re-run SSL cert on [C4G Server](https://c4g.dev).
4. Generate VAPID keys for PWA setup [Generator](https://vapidkeys.com/)
5. Generate RESEND key [Resend](https://resend.com/emails)

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

If you want to contribute to this template for future projects please work with the teaching staff. We welcome any technologies that could benefit the partners and speed to delivery for features.
