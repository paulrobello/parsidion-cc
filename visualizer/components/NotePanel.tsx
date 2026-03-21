'use client'

import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getNodeColor } from '@/lib/sigma-colors'
import type { NoteNode } from '@/lib/graph'

interface Props {
  node: NoteNode | null
  onClose: () => void
  onNavigate: (stem: string) => void
}


export function NotePanel({ node, onClose, onNavigate }: Props) {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [maximized, setMaximized] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchNote = useCallback(async (stem: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/note?stem=${encodeURIComponent(stem)}`)
      const data = await res.json()
      if (data.error) { setError(data.error as string); setContent('') }
      else setContent(data.content as string)
    } catch {
      setError('Failed to load note')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (node) {
      setMaximized(false)
      fetchNote(node.id)
    } else {
      setMaximized(false)
      setContent('')
      setError(null)
    }
  }, [node, fetchNote])

  const handleWikilink = useCallback((stem: string) => {
    onNavigate(stem)
  }, [onNavigate])

  // Extract fields from frontmatter
  const fm = content.match(/^---\n([\s\S]*?)\n---/)
  const fmBody = fm?.[1] ?? ''
  const noteDate: string | null = fmBody.match(/^date:\s*(.+)$/m)?.[1]?.trim() ?? null
  const relatedStems: string[] = (() => {
    const relatedLine = fmBody.match(/^related:\s*(.+)$/m)
    if (!relatedLine) return []
    const stems: string[] = []
    const re = /\[\[([^\]]+)\]\]/g
    let m: RegExpExecArray | null
    while ((m = re.exec(relatedLine[1])) !== null) stems.push(m[1])
    return stems
  })()

  // Strip frontmatter, then convert [[wikilinks]] → markdown links with wikilink: scheme
  const displayContent = content
    .replace(/^---[\s\S]*?---\n/, '')
    .replace(/\[\[([^\]]+)\]\]/g, (_, stem) => `[${stem}](wikilink:${encodeURIComponent(stem)})`)

  const isOpen = !!node

  return (
    <>
      {/* Overlay when maximized */}
      {maximized && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 199 }}
          onClick={() => setMaximized(false)}
        />
      )}

      <div
        style={{
          position: 'fixed',
          right: 0, top: 0, bottom: 0,
          width: maximized ? '100vw' : '42%',
          maxWidth: maximized ? '100vw' : 680,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 300ms cubic-bezier(0.4, 0, 0.2, 1), width 300ms ease',
          background: 'rgba(6, 8, 14, 0.97)',
          backdropFilter: 'blur(24px)',
          borderLeft: '1px solid rgba(0,255,200,0.12)',
          boxShadow: '-20px 0 60px rgba(0,0,0,0.5)',
          zIndex: maximized ? 200 : 50,
          display: 'flex',
          flexDirection: 'column',
          fontFamily: 'Syne, sans-serif',
        }}
      >
        {/* Header */}
        {node && (
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            flexShrink: 0,
          }}>
            <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, marginTop: 2 }}>
              <div style={{
                padding: '2px 8px', borderRadius: 3,
                background: `${getNodeColor(node.type)}22`,
                border: `1px solid ${getNodeColor(node.type)}55`,
                color: getNodeColor(node.type),
                fontFamily: 'Oxanium, sans-serif',
                fontSize: 10, fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.08em',
              }}>
                {node.type}
              </div>
              {noteDate && (
                <span style={{
                  fontSize: 9, color: '#6B7A99',
                  fontFamily: 'JetBrains Mono, monospace',
                  whiteSpace: 'nowrap',
                }}>{noteDate}</span>
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h2 style={{
                fontFamily: 'Oxanium, sans-serif',
                fontSize: '1rem', fontWeight: 600,
                color: '#E8E8F0', lineHeight: 1.3,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {node.title}
              </h2>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                {node.tags.slice(0, 6).map(tag => (
                  <span key={tag} style={{
                    fontSize: 9, padding: '1px 5px', borderRadius: 2,
                    background: 'rgba(123,97,255,0.12)',
                    border: '1px solid rgba(123,97,255,0.25)',
                    color: '#7B61FF', fontFamily: 'JetBrains Mono, monospace',
                  }}>#{tag}</span>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button
                onClick={() => setMaximized(m => !m)}
                title={maximized ? 'Restore' : 'Maximize'}
                style={{ background: 'none', border: 'none', color: '#6B7A99', cursor: 'pointer', fontSize: 14, padding: '2px 4px' }}
              >
                {maximized ? '⊡' : '⛶'}
              </button>
              <button
                onClick={onClose}
                style={{ background: 'none', border: 'none', color: '#6B7A99', cursor: 'pointer', fontSize: 16, padding: '2px 4px', lineHeight: 1 }}
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Content */}
        <div style={{
          flex: 1, overflow: 'auto', padding: '16px 20px',
        }}>
          {loading && (
            <div style={{ color: '#6B7A99', fontFamily: 'JetBrains Mono, monospace', fontSize: 12, paddingTop: 20 }}>
              Loading...
            </div>
          )}
          {error && (
            <div style={{ color: '#ef4444', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
              Error: {error}
            </div>
          )}
          {!loading && !error && relatedStems.length > 0 && (
            <div style={{
              marginBottom: 16,
              padding: '8px 12px',
              background: 'rgba(123,97,255,0.06)',
              border: '1px solid rgba(123,97,255,0.15)',
              borderRadius: 6,
            }}>
              <div style={{
                fontSize: 9, fontFamily: 'Oxanium, sans-serif', color: '#6B7A99',
                textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6,
              }}>Related</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {relatedStems.map(stem => (
                  <span
                    key={stem}
                    className="wikilink"
                    onClick={() => handleWikilink(stem)}
                    style={{ fontSize: 12, fontFamily: 'Syne, sans-serif' }}
                  >
                    {stem}
                  </span>
                ))}
              </div>
            </div>
          )}

          {!loading && !error && displayContent && (
            <div className="note-markdown">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  a: ({ href, children }: any) => {
                    if (href?.startsWith('wikilink:')) {
                      const stem = decodeURIComponent(href.slice(9))
                      return (
                        <span className="wikilink" onClick={() => handleWikilink(stem)}>
                          {children}
                        </span>
                      )
                    }
                    return <a href={href} target="_blank" rel="noreferrer">{children}</a>
                  },
                }}
              >
                {displayContent}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
