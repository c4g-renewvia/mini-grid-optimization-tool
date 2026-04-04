import { PrismaAdapter } from '@auth/prisma-adapter';
import { createId } from '@paralleldrive/cuid2';

const USERS = [
  {
    email: 'c4gdevad@gmail.com',
    userName: 'C4G Admin',
    role: 'ADMIN',
    providerAccountId: '102858545601971723113',
    access_token:
      'ya29.a0ARW5m75ebIow_zleIZhGH5JZLdu_KwlRrkvHUqkR__PCBmWtEEZ7y0-pkNdCBeXE3dLgfvBh5Hm5b229EPkfI5_rNOQmWiIhW526-M5Kec542kL3ORyAef0g8kfutOIURrUisC_plPgBMCHNEdaemYlrQKsZDVKa87PDZvYtaCgYKAXgSARASFQHGX2Mi_M6TsgN9eU1uSB1APqxswg0175',
  },
  {
    email: 'c4gdevstaff@gmail.com',
    userName: 'C4G Staff',
    role: 'STAFF',
    providerAccountId: '116868783453066553710',
    access_token:
      'ya29.a0ARW5m75h3Di2X6tWkpSZTnrgvj5A1KaI5eq29lMRz3qOc_jmJJ3xDr-X1qZOFbpxSshdxctOWVI0OpEUfG_uUnlCa6_22sNxvPYZMGAjMJ3KFKtIXFjeSHprSZ8-SOS4IC4k16qZWxCbN0m6i_B9RbpslRVHbFSicetX6jZgaCgYKATMSARESFQHGX2MihfffXVDHDMtKUATMoKonqA0175',
  },
];

const seedUser = async (
  prisma,
  adapter,
  { email, providerAccountId, access_token, role, userName }
) => {
  const hasUser = await prisma.user.findUnique({
    where: { email },
  });
  if (hasUser) {
    console.warn(`${email} already exists and will not be seeded!`);
    return;
  }
  if (!hasUser && adapter.createUser) {
    const user = await adapter.createUser({
      id: createId(),
      email,
      emailVerified: new Date(),
    });
    await prisma.account.create({
      data: {
        userId: user.id,
        type: 'oauth',
        provider: 'google',
        providerAccountId,
        access_token,
        token_type: 'bearer',
        scope:
          'https://www.googleapis.com/auth/userinfo.email openid https://www.googleapis.com/auth/userinfo.profile',
        expires_at: Math.floor(Date.now() / 1000) + 365 * 24 * 60 * 60,
      },
    });
    await prisma.user.update({
      where: { id: user.id },
      data: { name: userName, role },
    });
    console.log(`${email} has been seeded`);
  }
};

export const seedUsers = async (prisma) => {
  const adapter = PrismaAdapter(prisma);
  for (const user of USERS) {
    await seedUser(prisma, adapter, user);
  }
};
