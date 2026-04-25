import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

const isOffline = process.env.OFFLINE_MODE === 'true';

const adapter = isOffline
  ? new PrismaBetterSqlite3({
      url: process.env.DATABASE_URL ?? 'file:./prisma/offline.db',
    })
  : new PrismaPg({
      connectionString: process.env.DATABASE_URL,
    });

export const prisma =
  globalForPrisma.prisma || new PrismaClient({ adapter });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
