'use client'

import { useEffect, useRef, useState } from 'react'
import type { GraphCanvasHandle } from './GraphCanvas'

interface Props {
  canvasRef: React.RefObject<GraphCanvasHandle | null>
  stopThreshold: number  // 0 = disabled
}

// Linear scale: temperature 0 → 0% (cold), 1.0 → 100% (hot)
function energyToRatio(energy: number): number {
  if (!isFinite(energy) || energy < 0) return 1
  return Math.max(0, Math.min(1, energy))
}

export function TemperatureBar({ canvasRef, stopThreshold }: Props) {
  const [ratio, setRatio] = useState(1)
  const rafRef = useRef<number | null>(null)
  const frameRef = useRef(0)

  useEffect(() => {
    const tick = () => {
      frameRef.current++
      if (frameRef.current % 3 === 0) {
        const energy = canvasRef.current?.getEnergy() ?? Infinity
        setRatio(energyToRatio(energy))
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [canvasRef])

  const thresholdRatio = stopThreshold > 0 ? energyToRatio(stopThreshold) : null

  // Color interpolation: hot = red, warm = amber, cold = teal
  // We match the bar fill color to its actual temperature for the glow
  const glowColor = ratio > 0.6
    ? `rgba(239,68,68,${(ratio - 0.5) * 1.5})`
    : `rgba(0,255,200,${0.15 + (0.6 - ratio) * 0.5})`

  return (
    <div style={{ position: 'relative', height: 6, borderRadius: '0 0 10px 10px', overflow: 'visible' }}>
      {/* Track */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(255,255,255,0.04)',
        borderRadius: '0 0 10px 10px',
      }} />

      {/* Fill — background-size spans panel width so gradient position = temperature */}
      <div style={{
        position: 'absolute', top: 0, left: 0, bottom: 0,
        width: `${ratio * 100}%`,
        background: 'linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #00FFC8 100%)',
        backgroundSize: '260px 100%',  // 260 = panel width
        backgroundPosition: '0 0',
        backgroundRepeat: 'no-repeat',
        borderRadius: ratio > 0.99 ? '0 0 10px 10px' : '0 0 0 10px',
        boxShadow: `0 0 8px ${glowColor}`,
        transition: 'width 80ms linear',
      }} />

      {/* Threshold marker */}
      {thresholdRatio !== null && (
        <div style={{
          position: 'absolute',
          top: -2, bottom: -2,
          left: `calc(${thresholdRatio * 100}% - 0.5px)`,
          width: 1,
          background: '#e879f9',
          boxShadow: '0 0 4px #e879f9',
          zIndex: 2,
        }}>
          <div style={{
            position: 'absolute',
            bottom: 'calc(100% + 2px)',
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: 7,
            color: '#c026d3',
            fontFamily: 'JetBrains Mono, monospace',
            whiteSpace: 'nowrap',
            letterSpacing: 0,
            pointerEvents: 'none',
          }}>
            ▲
          </div>
        </div>
      )}
    </div>
  )
}
