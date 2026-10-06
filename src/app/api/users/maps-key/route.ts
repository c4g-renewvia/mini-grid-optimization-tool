import { auth } from '@/lib/auth';
import { decryptMapsApiKey, encryptMapsApiKey } from '@/lib/maps-key-crypto';
import { prisma } from '@/lib/prisma';
import { NextResponse } from 'next/server';

function isValidMapsKey(apiKey: string) {
  const trimmed = apiKey.trim();
  return trimmed.length >= 20 && trimmed.length <= 512;
}

export async function GET() {
  const session = await auth();

  if (!session?.user?.id || session.user.id === 'anonymous-user') {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const rows = await prisma.$queryRaw<
    Array<{
      mapsApiKeyCipher: string | null;
      mapsApiKeyIv: string | null;
      mapsApiKeyTag: string | null;
    }>
  >`SELECT "mapsApiKeyCipher", "mapsApiKeyIv", "mapsApiKeyTag" FROM "User" WHERE "id" = ${session.user.id} LIMIT 1`;
  const user = rows[0];

  if (!user?.mapsApiKeyCipher || !user.mapsApiKeyIv || !user.mapsApiKeyTag) {
    return NextResponse.json({ hasKey: false });
  }

  try {
    const apiKey = decryptMapsApiKey({
      cipherText: user.mapsApiKeyCipher,
      iv: user.mapsApiKeyIv,
      tag: user.mapsApiKeyTag,
    });

    return NextResponse.json({ hasKey: true, apiKey });
  } catch (error) {
    console.warn(
      'Discarding an inaccessible encrypted Google Maps API key:',
      error
    );

    try {
      await prisma.$executeRaw`
        UPDATE "User"
        SET
          "mapsApiKeyCipher" = NULL,
          "mapsApiKeyIv" = NULL,
          "mapsApiKeyTag" = NULL,
          "updatedAt" = ${new Date()}
        WHERE "id" = ${session.user.id}
      `;
    } catch (cleanupError) {
      console.error(
        'Failed to clear inaccessible Google Maps API key:',
        cleanupError
      );
      return NextResponse.json(
        { error: 'Could not reset stored key' },
        { status: 500 }
      );
    }

    return NextResponse.json({ hasKey: false, keyWasReset: true });
  }
}

export async function PUT(req: Request) {
  const session = await auth();

  if (!session?.user?.id || session.user.id === 'anonymous-user') {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  const body = (await req.json()) as { apiKey?: string };
  const apiKey = body.apiKey?.trim() ?? '';

  if (!isValidMapsKey(apiKey)) {
    return NextResponse.json(
      { error: 'Please provide a valid Google Maps API key.' },
      { status: 400 }
    );
  }

  try {
    const encrypted = encryptMapsApiKey(apiKey);

    await prisma.$executeRaw`
      UPDATE "User"
      SET
        "mapsApiKeyCipher" = ${encrypted.cipherText},
        "mapsApiKeyIv" = ${encrypted.iv},
        "mapsApiKeyTag" = ${encrypted.tag},
        "updatedAt" = ${new Date()}
      WHERE "id" = ${session.user.id}
    `;

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error storing Google Maps API key:', error);
    return NextResponse.json({ error: 'Failed to save key' }, { status: 500 });
  }
}

export async function DELETE() {
  const session = await auth();

  if (!session?.user?.id || session.user.id === 'anonymous-user') {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
  }

  try {
    await prisma.$executeRaw`
      UPDATE "User"
      SET
        "mapsApiKeyCipher" = NULL,
        "mapsApiKeyIv" = NULL,
        "mapsApiKeyTag" = NULL,
        "updatedAt" = ${new Date()}
      WHERE "id" = ${session.user.id}
    `;

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error deleting Google Maps API key:', error);
    return NextResponse.json(
      { error: 'Failed to delete key' },
      { status: 500 }
    );
  }
}
