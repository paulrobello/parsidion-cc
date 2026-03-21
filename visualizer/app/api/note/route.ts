import { NextRequest, NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

export async function GET(req: NextRequest) {
  const stem = req.nextUrl.searchParams.get('stem')
  if (!stem) return NextResponse.json({ error: 'stem required' }, { status: 400 })

  const vaultRoot = process.env.VAULT_ROOT || path.join(process.env.HOME || '~', 'ClaudeVault')

  // Search for the note file recursively in the vault
  function findNote(dir: string, stemToFind: string): string | null {
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true })
      for (const entry of entries) {
        if (entry.name.startsWith('.')) continue
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
          const found = findNote(full, stemToFind)
          if (found) return found
        } else if (entry.isFile() && entry.name.endsWith('.md')) {
          const fileStem = entry.name.replace(/\.md$/, '')
          if (fileStem === stemToFind) return full
        }
      }
    } catch { /* skip unreadable dirs */ }
    return null
  }

  const notePath = findNote(vaultRoot, stem)
  if (!notePath) return NextResponse.json({ error: `Note not found: ${stem}` }, { status: 404 })

  try {
    const content = fs.readFileSync(notePath, 'utf-8')
    const relativePath = path.relative(vaultRoot, notePath)
    return NextResponse.json({ content, path: relativePath })
  } catch {
    return NextResponse.json({ error: 'Failed to read note' }, { status: 500 })
  }
}
