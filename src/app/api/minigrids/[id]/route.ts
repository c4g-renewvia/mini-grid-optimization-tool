// app/api/minigrids/[id]/route.ts

import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ id: string }> } // ← note: Promise<{ id: string }>
) {
  const session = await auth();

  if (!session?.user?.id) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Await the params Promise – this is the required fix
  const params = await context.params;
  const runId = params.id;

  // Safety guard (now safe)
  if (!runId) {
    console.error('DELETE called without valid ID. URL was:', req.url);
    return NextResponse.json(
      { error: 'Missing or invalid mini-grid ID' },
      { status: 400 }
    );
  }

  console.log(`Deleting mini-grid ID: ${runId}`);

  try {
    const run = await prisma.miniGridRun.findUnique({
      where: { id: runId },
      select: { userId: true },
    });

    if (!run) {
      return NextResponse.json(
        { error: 'Mini-grid not found' },
        { status: 404 }
      );
    }

    if (run.userId !== session.user.id) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
    }

    await prisma.miniGridRun.delete({
      where: { id: runId },
    });

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error('[DELETE /api/minigrids/[id]]', err);
    return NextResponse.json(
      { error: 'Failed to delete mini-grid' },
      { status: 500 }
    );
  }
}
