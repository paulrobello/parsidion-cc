import { describe, it, expect } from 'bun:test'
import { parseDiff } from './parseDiff'

const SAMPLE_DIFF = `--- a/Patterns/my-note.md
+++ b/Patterns/my-note.md
@@ -1,4 +1,5 @@
 # My Note

-Old line one.
+New line one.
+Added line.
 Context line.
`

describe('parseDiff', () => {
  it('returns empty array for empty input', () => {
    expect(parseDiff('')).toEqual([])
  })

  it('parses a single hunk', () => {
    const hunks = parseDiff(SAMPLE_DIFF)
    expect(hunks).toHaveLength(1)
    expect(hunks[0].header).toBe('@@ -1,4 +1,5 @@')
  })

  it('strips file header lines (--- / +++)', () => {
    const hunks = parseDiff(SAMPLE_DIFF)
    const allContent = hunks.flatMap(h => h.lines.map(l => l.content))
    expect(allContent.some(c => c.startsWith('---') || c.startsWith('+++')))
      .toBe(false)
  })

  it('classifies line types correctly', () => {
    const lines = parseDiff(SAMPLE_DIFF)[0].lines
    const types = lines.map(l => l.type)
    expect(types).toEqual(['context', 'context', 'remove', 'add', 'add', 'context'])
  })

  it('assigns oldLineNo to context and remove lines', () => {
    const lines = parseDiff(SAMPLE_DIFF)[0].lines
    const removeLine = lines.find(l => l.type === 'remove')!
    expect(removeLine.oldLineNo).toBe(3)
    expect(removeLine.newLineNo).toBeNull()
  })

  it('assigns newLineNo to context and add lines', () => {
    const lines = parseDiff(SAMPLE_DIFF)[0].lines
    const addLine = lines.find(l => l.type === 'add')!
    expect(addLine.newLineNo).toBe(3)
    expect(addLine.oldLineNo).toBeNull()
  })

  it('counts additions and deletions', () => {
    const hunks = parseDiff(SAMPLE_DIFF)
    const all = hunks.flatMap(h => h.lines)
    expect(all.filter(l => l.type === 'add').length).toBe(2)
    expect(all.filter(l => l.type === 'remove').length).toBe(1)
  })
})
