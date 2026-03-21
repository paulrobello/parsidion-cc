export const TYPE_COLORS: Record<string, string> = {
  pattern:   '#6366f1',
  debugging: '#ef4444',
  research:  '#10b981',
  project:   '#0ea5e9',
  tool:      '#f59e0b',
  language:  '#a855f7',
  framework: '#f97316',
  daily:     '#4b5563',
}

export function getNodeColor(type: string): string {
  return TYPE_COLORS[type] ?? '#6b7280'
}

export function getNodeSize(incomingLinks: number): number {
  return Math.max(2, Math.log(incomingLinks + 1) * 2)
}
