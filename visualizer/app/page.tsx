'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useLocalStorage } from '@/lib/useLocalStorage'
import dynamic from 'next/dynamic'
import { loadGraphData, filterEdges } from '@/lib/graph'
import { HUDPanel } from '@/components/HUDPanel'
import { NotePanel } from '@/components/NotePanel'
import { SearchBox } from '@/components/SearchBox'
import type { GraphData, GraphSource } from '@/lib/graph'
import type { GraphCanvasHandle } from '@/components/GraphCanvas'
import { TYPE_COLORS } from '@/lib/sigma-colors'

// Simulation setting defaults — used by useLocalStorage and the reset button
const SIM_DEFAULTS = {
  scalingRatio: 10,
  gravity: 1,
  slowDown: 0.5,
  edgeWeightInfluence: 2,
  startTemperature: 0.8,
  stopThreshold: 0.01,
}

// Dynamic import for the graph canvas (browser-only)
const GraphCanvas = dynamic(() => import('@/components/GraphCanvas').then(m => m.GraphCanvas), {
  ssr: false,
  loading: () => (
    <div style={{
      position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Oxanium, sans-serif', color: '#00FFC8', fontSize: 14, letterSpacing: '0.1em',
    }}>
      <div>
        <div style={{ textAlign: 'center', marginBottom: 16 }}>◈</div>
        <div>INITIALIZING GRAPH...</div>
      </div>
    </div>
  )
})

export default function Home() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Controls — persisted to localStorage
  const [threshold, setThreshold] = useLocalStorage('vv:threshold', 0.8)
  const [graphSource, setGraphSource] = useLocalStorage<GraphSource>('vv:graphSource', 'semantic')
  const [showOverlayEdges, setShowOverlayEdges] = useLocalStorage('vv:showOverlayEdges', false)
  const [filterNodesBySimilarity, setFilterNodesBySimilarity] = useLocalStorage('vv:filterNodesBySimilarity', false)
  const [activeTypesArr, setActiveTypesArr] = useLocalStorage<string[]>(
    'vv:activeTypes',
    Object.keys(TYPE_COLORS).filter(t => t !== 'daily')
  )
  const activeTypes = useMemo(() => new Set(activeTypesArr), [activeTypesArr])
  const setActiveTypes = useCallback((updater: Set<string> | ((prev: Set<string>) => Set<string>)) => {
    setActiveTypesArr(prev => {
      const prevSet = new Set(prev)
      const next = typeof updater === 'function' ? updater(prevSet) : updater
      return [...next]
    })
  }, [setActiveTypesArr])
  const [showDaily, setShowDaily] = useLocalStorage('vv:showDaily', false)
  const [hideIsolated, setHideIsolated] = useLocalStorage('vv:hideIsolated', false)
  const [labelsOnHoverOnly, setLabelsOnHoverOnly] = useLocalStorage('vv:labelsOnHoverOnly', false)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [scalingRatio, setScalingRatio] = useLocalStorage('vv:scalingRatio', SIM_DEFAULTS.scalingRatio)
  const [gravityRaw, setGravity] = useLocalStorage('vv:gravity', SIM_DEFAULTS.gravity)
  const gravity = Math.min(gravityRaw, 5)
  const [slowDown, setSlowDown] = useLocalStorage('vv:slowDown', SIM_DEFAULTS.slowDown)
  const [edgeWeightInfluence, setEdgeWeightInfluence] = useLocalStorage('vv:edgeWeightInfluence', SIM_DEFAULTS.edgeWeightInfluence)
  const [startTemperature, setStartTemperature] = useLocalStorage('vv:startTemperature', SIM_DEFAULTS.startTemperature)
  const [stopThreshold, setStopThreshold] = useLocalStorage('vv:stopThreshold', SIM_DEFAULTS.stopThreshold)
  const [isLayoutRunning, setIsLayoutRunning] = useState(true)

  const graphCanvasRef = useRef<GraphCanvasHandle>(null)

  useEffect(() => {
    // Clear stale persisted keys that have new defaults
    localStorage.removeItem('vv:isLayoutRunning')
    if (!localStorage.getItem('vv:threshold_v2')) {
      localStorage.removeItem('vv:threshold')
      localStorage.setItem('vv:threshold_v2', '1')
    }
    loadGraphData()
      .then(setGraphData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const selectedNodeData = useMemo(() => {
    if (!graphData || !selectedNode) return null
    return graphData.nodes.find(n => n.id === selectedNode) ?? null
  }, [graphData, selectedNode])

  const handleNodeClick = useCallback((stem: string) => {
    setSelectedNode(stem)
  }, [])

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const handleWikiNav = useCallback((stem: string) => {
    setSelectedNode(stem)
    graphCanvasRef.current?.flyToNode(stem)
  }, [])

  const handleToggleType = useCallback((type: string) => {
    setActiveTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }, [setActiveTypes])

  // Stats for HUD
  const stats = useMemo(() => {
    if (!graphData) return { nodeCount: 0, edgeCount: 0, avgScore: 0 }
    const qualifying = (filterNodesBySimilarity && graphSource === 'wiki')
      ? new Set(graphData.edges.filter(e => e.kind === 'semantic' && e.w >= threshold).flatMap(e => [e.s, e.t]))
      : null
    const visibleNodes = new Set(
      graphData.nodes
        .filter(n => (showDaily || n.folder !== 'Daily') && activeTypes.has(n.type) && (!qualifying || qualifying.has(n.id)))
        .map(n => n.id)
    )
    const edges = filterEdges(graphData.edges, graphSource, threshold)
      .filter(e => visibleNodes.has(e.s) && visibleNodes.has(e.t))
    const semEdges = edges.filter(e => e.kind === 'semantic')
    const avg = semEdges.length > 0
      ? semEdges.reduce((sum, e) => sum + e.w, 0) / semEdges.length
      : 0
    return { nodeCount: visibleNodes.size, edgeCount: edges.length, avgScore: avg }
  }, [graphData, threshold, graphSource, activeTypes, showDaily, filterNodesBySimilarity])

  const panelOpen = !!selectedNode

  return (
    <main style={{
      position: 'fixed', inset: 0,
      background: 'radial-gradient(ellipse at 50% 50%, #0C0F1E 0%, #060608 70%)',
      overflow: 'hidden',
    }}>
      {/* Star field */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'radial-gradient(1px 1px at 10% 15%, rgba(255,255,255,0.15) 0%, transparent 100%), radial-gradient(1px 1px at 35% 60%, rgba(255,255,255,0.1) 0%, transparent 100%), radial-gradient(1px 1px at 75% 25%, rgba(255,255,255,0.12) 0%, transparent 100%), radial-gradient(1px 1px at 90% 80%, rgba(255,255,255,0.08) 0%, transparent 100%)',
        pointerEvents: 'none',
      }} />

      {loading && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Oxanium, sans-serif', color: '#00FFC8', fontSize: 14, letterSpacing: '0.12em',
          flexDirection: 'column', gap: 12,
        }}>
          <div style={{ fontSize: 24 }}>◈</div>
          <div>LOADING GRAPH DATA...</div>
        </div>
      )}

      {error && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Oxanium, sans-serif', color: '#ef4444', fontSize: 13, flexDirection: 'column', gap: 8,
        }}>
          <div>⚠ Failed to load graph.json</div>
          <div style={{ color: '#6B7A99', fontSize: 11 }}>{error}</div>
          <div style={{ color: '#6B7A99', fontSize: 11 }}>Run: make graph</div>
        </div>
      )}

      {/* Graph canvas — compressed when panel open */}
      <div style={{
        position: 'absolute',
        left: 0, top: 0, bottom: 0,
        right: panelOpen ? 'min(42%, 680px)' : 0,
        transition: 'right 300ms cubic-bezier(0.4, 0, 0.2, 1)',
      }}>
        {graphData && !loading && (
          <GraphCanvas
            ref={graphCanvasRef}
            data={graphData}
            threshold={threshold}
            graphSource={graphSource}
            activeTypes={activeTypes}
            showDaily={showDaily}
            hideIsolated={hideIsolated}
            labelsOnHoverOnly={labelsOnHoverOnly}
            showOverlayEdges={showOverlayEdges}
            filterNodesBySimilarity={filterNodesBySimilarity}
            selectedNode={selectedNode}
            onNodeClick={handleNodeClick}
            onBackgroundClick={handleBackgroundClick}
            scalingRatio={scalingRatio}
            gravity={gravity}
            slowDown={slowDown}
            edgeWeightInfluence={edgeWeightInfluence}
            startTemperature={startTemperature}
            stopThreshold={stopThreshold}
            isLayoutRunning={isLayoutRunning}
            onLayoutStop={() => setIsLayoutRunning(false)}
            onLayoutRestart={() => setIsLayoutRunning(true)}
          />
        )}
      </div>

      {/* HUD Panel */}
      {graphData && (
        <HUDPanel
          threshold={threshold}
          onThresholdChange={setThreshold}
          graphSource={graphSource}
          onGraphSourceChange={setGraphSource}
          showOverlayEdges={showOverlayEdges}
          onToggleOverlayEdges={() => setShowOverlayEdges(s => !s)}
          filterNodesBySimilarity={filterNodesBySimilarity}
          onToggleFilterNodesBySimilarity={() => setFilterNodesBySimilarity(s => !s)}
          activeTypes={activeTypes}
          onToggleType={handleToggleType}
          showDaily={showDaily}
          onToggleDaily={() => setShowDaily(s => !s)}
          hideIsolated={hideIsolated}
          onToggleHideIsolated={() => setHideIsolated(s => !s)}
          labelsOnHoverOnly={labelsOnHoverOnly}
          onToggleLabelsOnHoverOnly={() => setLabelsOnHoverOnly(s => !s)}
          nodeCount={stats.nodeCount}
          edgeCount={stats.edgeCount}
          avgScore={stats.avgScore}
          scalingRatio={scalingRatio}
          onScalingRatioChange={setScalingRatio}
          gravity={gravity}
          onGravityChange={setGravity}
          slowDown={slowDown}
          onSlowDownChange={setSlowDown}
          edgeWeightInfluence={edgeWeightInfluence}
          onEdgeWeightInfluenceChange={setEdgeWeightInfluence}
          startTemperature={startTemperature}
          onStartTemperatureChange={setStartTemperature}
          stopThreshold={stopThreshold}
          onStopThresholdChange={setStopThreshold}
          isLayoutRunning={isLayoutRunning}
          onToggleLayout={() => setIsLayoutRunning(r => !r)}
          onResetSimSettings={() => {
            setScalingRatio(SIM_DEFAULTS.scalingRatio)
            setGravity(SIM_DEFAULTS.gravity)
            setSlowDown(SIM_DEFAULTS.slowDown)
            setEdgeWeightInfluence(SIM_DEFAULTS.edgeWeightInfluence)
            setStartTemperature(SIM_DEFAULTS.startTemperature)
            setStopThreshold(SIM_DEFAULTS.stopThreshold)
          }}
          canvasRef={graphCanvasRef}
        />
      )}

      {/* Search Box */}
      {graphData && (
        <SearchBox
          nodes={graphData.nodes}
          panelOpen={panelOpen}
          onSelect={(stem) => {
            setSelectedNode(stem)
            graphCanvasRef.current?.flyToNode(stem)
            graphCanvasRef.current?.selectNode(stem)
          }}
        />
      )}

      {/* Note Panel */}
      <NotePanel
        node={selectedNodeData}
        onClose={() => setSelectedNode(null)}
        onNavigate={handleWikiNav}
      />
    </main>
  )
}
