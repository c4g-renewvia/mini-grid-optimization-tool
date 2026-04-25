import { prisma } from '@/lib/prisma';
import { PrismaAdapter } from '@auth/prisma-adapter';
import type { User } from '@prisma/client';
import NextAuth, { type NextAuthConfig, type Session } from 'next-auth';
import Google from 'next-auth/providers/google';
import { cookies } from 'next/headers';
import type { NextRequest } from 'next/server';

const isOffline = process.env.OFFLINE_MODE === 'true';

const OFFLINE_SESSION: Session = {
  user: {
    id: 'offline-user',
    email: 'offline@localhost',
    name: 'Offline User',
    role: 'ADMIN',
    image: null,
  },
  expires: '2099-01-01T00:00:00.000Z',
};

export const authOptions: NextAuthConfig = {
  adapter: PrismaAdapter(prisma),
  providers: [Google],
  trustHost: true,
  callbacks: {
    async session({ session, user }) {
      // Check for impersonation cookie
      const cookieStore = await cookies();
      const impersonatedUserCookie = cookieStore.get('impersonated-user');

      // Type assertion for our custom User fields
      const dbUser = user as unknown as User;

      if (impersonatedUserCookie) {
        try {
          const impersonationData = JSON.parse(impersonatedUserCookie.value);

          // Destructure impersonation data with fallbacks for backward compatibility
          const {
            impersonatedUser: newFormatUser,
            originalAdminId: newFormatAdminId,
          } = impersonationData;
          const impersonatedUser = newFormatUser ?? impersonationData;
          const originalAdminId = newFormatAdminId ?? dbUser.id;

          // Verify the original admin is still an admin and matches the current user
          const isValidImpersonation =
            originalAdminId === dbUser.id && dbUser.role === 'ADMIN';

          if (isValidImpersonation) {
            // Override session with impersonated user data
            session.user = {
              ...session.user,
              id: impersonatedUser.id,
              name: impersonatedUser.name,
              email: impersonatedUser.email,
              role: impersonatedUser.role,
              image: impersonatedUser.image || null,
            };
          } else {
            // Invalid impersonation, use original user data
            Object.assign(session.user, {
              role: dbUser.role,
              id: dbUser.id,
            });
          }
        } catch {
          // Invalid cookie, use original user data
          Object.assign(session.user, {
            role: dbUser.role,
            id: dbUser.id,
          });
        }
      } else {
        // No impersonation cookie, use original user data
        Object.assign(session.user, {
          role: dbUser.role,
          id: dbUser.id,
        });
      }

      return session;
    },
    redirect({ url, baseUrl }) {
      // Allows relative callback URLs
      if (url.startsWith('/')) return `${baseUrl}${url}`;
      // Allows callback URLs on the same origin
      if (new URL(url).origin === baseUrl) return url;
      return baseUrl;
    },
  },
};

const real = NextAuth(authOptions);

const offlineHandlers = {
  GET: async (req: NextRequest) => {
    if (new URL(req.url).pathname.endsWith('/session')) {
      return Response.json(OFFLINE_SESSION);
    }
    return real.handlers.GET(req);
  },
  POST: real.handlers.POST,
};

export const handlers = isOffline ? offlineHandlers : real.handlers;
export const auth = (
  isOffline ? (async () => OFFLINE_SESSION) : real.auth
) as typeof real.auth;
export const signIn = real.signIn;
export const signOut = real.signOut;
