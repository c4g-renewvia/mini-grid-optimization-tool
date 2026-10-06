import { PrismaClient } from './generated/prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { seedUsers } from './seed/users.mjs';

function getPostgresConnectionString() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) return undefined;

  const url = new URL(connectionString);
  const sslMode = url.searchParams.get('sslmode')?.toLowerCase();

  if (
    sslMode === 'prefer' ||
    sslMode === 'require' ||
    sslMode === 'verify-ca'
  ) {
    url.searchParams.set('sslmode', 'verify-full');
    return url.toString();
  }

  return connectionString;
}

const adapter = new PrismaPg({
  connectionString: getPostgresConnectionString(),
});

const prisma = new PrismaClient({ adapter });

async function main() {
  // Initial seeds
  console.log('----- Starting to seed initial data -----');
  await seedUsers(prisma);
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
