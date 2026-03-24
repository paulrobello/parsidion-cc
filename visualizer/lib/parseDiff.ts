export interface DiffLine {
  type: 'add' | 'remove' | 'context'
  content: string
  oldLineNo: number | null
  newLineNo: number | null
}

export interface DiffHunk {
  header: string
  lines: DiffLine[]
}

/**
 * Parse a raw unified diff string into structured hunks.
 * Strips the --- / +++ file header lines.
 * Returns [] for empty or header-only input.
 */
export function parseDiff(raw: string): DiffHunk[] {
  const lines = raw.split('\n')
  const hunks: DiffHunk[] = []
  let current: DiffHunk | null = null
  let oldLine = 0
  let newLine = 0
  let expectedOldLines = 0
  let expectedNewLines = 0
  let oldLinesProcessed = 0
  let newLinesProcessed = 0

  for (const line of lines) {
    if (line.startsWith('--- ') || line.startsWith('+++ ')) continue

    const hunkMatch = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/)
    if (hunkMatch) {
      oldLine = parseInt(hunkMatch[1], 10)
      expectedOldLines = hunkMatch[2] ? parseInt(hunkMatch[2], 10) : 1
      newLine = parseInt(hunkMatch[3], 10)
      expectedNewLines = hunkMatch[4] ? parseInt(hunkMatch[4], 10) : 1
      oldLinesProcessed = 0
      newLinesProcessed = 0
      current = { header: line.match(/^(@@ [^@]+ @@)/)?.[1] ?? line, lines: [] }
      hunks.push(current)
      continue
    }

    if (!current) continue

    // Stop processing if we've hit the expected line counts
    if (oldLinesProcessed >= expectedOldLines && newLinesProcessed >= expectedNewLines) {
      current = null
      continue
    }

    if (line.startsWith('+')) {
      current.lines.push({ type: 'add', content: line.slice(1), oldLineNo: null, newLineNo: newLine++ })
      newLinesProcessed++
    } else if (line.startsWith('-')) {
      current.lines.push({ type: 'remove', content: line.slice(1), oldLineNo: oldLine++, newLineNo: null })
      oldLinesProcessed++
    } else if (line.startsWith(' ') || line === '') {
      // Treat lines starting with space OR empty lines as context (blank lines in diffs)
      current.lines.push({ type: 'context', content: line === '' ? '' : line.slice(1), oldLineNo: oldLine++, newLineNo: newLine++ })
      oldLinesProcessed++
      newLinesProcessed++
    }
  }

  return hunks
}

/** Count total additions and deletions across all hunks */
export function diffStats(hunks: DiffHunk[]): { additions: number; deletions: number } {
  let additions = 0
  let deletions = 0
  for (const hunk of hunks) {
    for (const line of hunk.lines) {
      if (line.type === 'add') additions++
      else if (line.type === 'remove') deletions++
    }
  }
  return { additions, deletions }
}
