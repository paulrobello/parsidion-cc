// app/api/graph/rebuild/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import { vaultBroadcast } from '@/lib/vaultBroadcast.server'
import { resolveVault } from '@/lib/vaultResolver'

export async function POST(req: NextRequest) {
  const vault = req.nextUrl.searchParams.get('vault')
  const vaultPath = resolveVault(vault)
  const repoRoot = path.join(process.cwd(), '..')
  const scriptPath = path.join(repoRoot, 'scripts', 'build_graph.py')

  const args = ['run', '--no-project', scriptPath, '--vault', vaultPath]

  return new Promise<NextResponse>(resolve => {
    const proc = spawn('uv', args, {
      cwd: repoRoot,
      stdio: 'pipe',
    })

    let stderr = ''
    proc.stderr?.on('data', (chunk: Buffer) => { stderr += chunk.toString() })

    proc.on('close', code => {
      if (code === 0) {
        vaultBroadcast.emit('graph:rebuilt')
        resolve(NextResponse.json({ ok: true }))
      } else {
        resolve(NextResponse.json(
          { error: `build_graph.py exited ${code}`, detail: stderr },
          { status: 500 }
        ))
      }
    })

    proc.on('error', err => {
      resolve(NextResponse.json({ error: err.message }, { status: 500 }))
    })
  })
}
