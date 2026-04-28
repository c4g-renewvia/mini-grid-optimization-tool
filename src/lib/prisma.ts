import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

const isOffline = process.env.OFFLINE_MODE === 'true';

function offlineAdapter() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      'DATABASE_URL is required in offline mode. Run pnpm run offline:init or invoke the offline start script which writes .env.'
    );
  }
  return new PrismaBetterSqlite3({ url });
}

const adapter = isOffline
  ? offlineAdapter()
  : new PrismaPg({ connectionString: process.env.DATABASE_URL });

export const prisma =
  globalForPrisma.prisma || new PrismaClient({ adapter });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
