import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

const isOffline = process.env.OFFLINE_MODE === 'true';

const client = isOffline
  ? new PrismaClient()
  : new PrismaClient({
      adapter: new PrismaPg({
        connectionString: process.env.DATABASE_URL,
      }),
    });

export const prisma = globalForPrisma.prisma || client;

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
