import { PrismaClient } from './generated/prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { seedUsers } from './seed/users.mjs';
import { getPostgresConnectionString } from '../src/lib/postgres-connection-string';

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
