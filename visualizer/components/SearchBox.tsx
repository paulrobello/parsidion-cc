'use client'

import { useState, useRef, useEffect } from 'react'
import type { NoteNode } from '@/lib/graph'

interface Props {
  nodes: NoteNode[]
  onSelect: (stem: string) => void
  panelOpen?: boolean
}

export function SearchBox({ nodes, onSelect, panelOpen }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [results, setResults] = useState<NoteNode[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const q = query.toLowerCase()
    const isTagSearch = q.startsWith('#')
    const tagQ = isTagSearch ? q.slice(1) : ''

    const filtered = nodes.filter(n => {
      if (isTagSearch) return n.tags.some(t => t.includes(tagQ))
      return n.title.toLowerCase().includes(q)
    }).slice(0, 8)

    setResults(filtered)
    setOpen(filtered.length > 0)
  }, [query, nodes])

  const handleSelect = (stem: string) => {
    setQuery('')
    setOpen(false)
    onSelect(stem)
  }

  return (
    <div style={{
      position: 'fixed', top: 16,
      right: panelOpen ? 'calc(min(42%, 680px) + 16px)' : 16,
      zIndex: 100,
      width: 280,
      transition: 'right 300ms cubic-bezier(0.4, 0, 0.2, 1)',
      animation: 'fadeSlideIn 0.4s ease-out both',
      animationDelay: '0.3s',
    }}>
      <div style={{ position: 'relative' }}>
        <input
          ref={inputRef}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search title or #tag…"
          style={{
            width: '100%',
            padding: '9px 12px 9px 36px',
            background: 'rgba(8, 10, 18, 0.92)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(0,255,200,0.2)',
            borderRadius: 8,
            color: '#E8E8F0',
            fontFamily: 'Oxanium, sans-serif',
            fontSize: 12,
            outline: 'none',
            boxShadow: '0 0 20px rgba(0,255,200,0.05)',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
          onFocusCapture={e => {
            const el = e.target as HTMLInputElement
            el.style.borderColor = 'rgba(0,255,200,0.5)'
            el.style.boxShadow = '0 0 20px rgba(0,255,200,0.12)'
          }}
          onBlurCapture={e => {
            const el = e.target as HTMLInputElement
            el.style.borderColor = 'rgba(0,255,200,0.2)'
            el.style.boxShadow = '0 0 20px rgba(0,255,200,0.05)'
          }}
        />
        <span style={{
          position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)',
          color: '#6B7A99', fontSize: 14, pointerEvents: 'none',
        }}>⌕</span>
      </div>

      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          marginTop: 4,
          background: 'rgba(8, 10, 18, 0.97)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(0,255,200,0.15)',
          borderRadius: 8,
          overflow: 'hidden',
          boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
        }}>
          {results.map((node, i) => (
            <button
              key={node.id}
              onMouseDown={() => handleSelect(node.id)}
              style={{
                display: 'block', width: '100%', textAlign: 'left',
                padding: '8px 12px',
                background: 'transparent',
                border: 'none',
                borderTop: i > 0 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                color: '#E8E8F0',
                cursor: 'pointer',
                transition: 'background 0.1s',
              }}
              onMouseEnter={e => (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,255,200,0.06)'}
              onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.background = 'transparent'}
            >
              <div style={{ fontFamily: 'Oxanium, sans-serif', fontSize: 12, lineHeight: 1.3 }}>{node.title}</div>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#6B7A99', marginTop: 2 }}>
                {node.folder} · {node.tags.slice(0, 3).map(t => `#${t}`).join(' ')}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
