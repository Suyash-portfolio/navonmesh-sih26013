import React, { useState } from 'react';
import { 
  Layers, Eye, EyeOff, Sliders, Box, Map as MapIcon, 
  Filter, CheckCircle2, AlertTriangle, Settings2
} from 'lucide-react';

export default function LayerTreeSidebar({
  layerVisibility,
  onToggleLayer,
  layerOpacity,
  onChangeOpacity,
  viewMode,
  onChangeViewMode,
  statusFilter,
  onChangeStatusFilter,
  statusCounts,
  geoAiParams,
  onChangeGeoAiParam
}) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  return (
    <aside className={`h-full bg-surface/95 border-r border-surface-border flex flex-col transition-all duration-300 z-20 select-none ${
      isCollapsed ? 'w-14' : 'w-80'
    }`}>
      {/* Sidebar Header */}
      <div className="p-3.5 border-b border-surface-border flex items-center justify-between">
        {!isCollapsed && (
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">GIS Layers & Filters</h2>
          </div>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-1.5 rounded-lg bg-surface-raised hover:bg-[#1E4C40] text-slate-400 hover:text-white transition-colors"
          title={isCollapsed ? "Expand Layer Tree" : "Collapse Sidebar"}
        >
          <Sliders className="w-3.5 h-3.5" />
        </button>
      </div>

      {!isCollapsed ? (
        <div className="flex-1 overflow-y-auto p-3.5 space-y-4">
          {/* View Mode Toggle: 2D Planar vs 3D Digital Twin */}
          <div>
            <label className="text-[10px] font-mono uppercase text-slate-400 font-semibold mb-1.5 block">
              Projection Engine
            </label>
            <div className="grid grid-cols-2 gap-1.5 p-1 bg-surface-raised rounded-xl border border-surface-border">
              <button
                onClick={() => onChangeViewMode('2d')}
                className={`flex items-center justify-center space-x-1.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  viewMode === '2d'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <MapIcon className="w-3.5 h-3.5" />
                <span>2D Planar</span>
              </button>

              <button
                onClick={() => onChangeViewMode('3d')}
                className={`flex items-center justify-center space-x-1.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  viewMode === '3d'
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Box className="w-3.5 h-3.5" />
                <span>3D Digital Twin</span>
              </button>
            </div>
          </div>

          {/* Status Filter Chips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[10px] font-mono uppercase text-slate-400 font-semibold flex items-center space-x-1">
                <Filter className="w-3 h-3 text-indigo-400" />
                <span>Filter by Cadastral Status</span>
              </label>
            </div>
            
            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => onChangeStatusFilter('all')}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center justify-between border transition-all ${
                  statusFilter === 'all'
                    ? 'bg-surface-raised text-white border-indigo-500/50 shadow-sm'
                    : 'bg-surface/50 text-slate-400 border-surface-border hover:border-slate-600'
                }`}
              >
                <span>All Parcels</span>
                <span className="font-mono text-[10px] text-slate-400">{statusCounts.all}</span>
              </button>

              <button
                onClick={() => onChangeStatusFilter('Approved')}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center justify-between border transition-all ${
                  statusFilter === 'Approved'
                    ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/50 shadow-sm'
                    : 'bg-surface/50 text-slate-400 border-surface-border hover:border-emerald-500/30'
                }`}
              >
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1"></span>
                  <span>Approved</span>
                </span>
                <span className="font-mono text-[10px] text-emerald-400">{statusCounts.approved}</span>
              </button>

              <button
                onClick={() => onChangeStatusFilter('Review')}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center justify-between border transition-all ${
                  statusFilter === 'Review'
                    ? 'bg-amber-950/40 text-amber-300 border-amber-500/50 shadow-sm'
                    : 'bg-surface/50 text-slate-400 border-surface-border hover:border-amber-500/30'
                }`}
              >
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1"></span>
                  <span>Review</span>
                </span>
                <span className="font-mono text-[10px] text-amber-400">{statusCounts.review}</span>
              </button>

              <button
                onClick={() => onChangeStatusFilter('Encroachment')}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center justify-between border transition-all ${
                  statusFilter === 'Encroachment'
                    ? 'bg-rose-950/50 text-rose-300 border-rose-500/50 shadow-sm'
                    : 'bg-surface/50 text-slate-400 border-surface-border hover:border-rose-500/30'
                }`}
              >
                <span className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse mr-1"></span>
                  <span>Disputed</span>
                </span>
                <span className="font-mono text-[10px] text-rose-400 font-bold">{statusCounts.encroachment}</span>
              </button>
            </div>
          </div>

          {/* Spatial Layer Tree Switches */}
          <div>
            <label className="text-[10px] font-mono uppercase text-slate-400 font-semibold mb-2 block">
              Spatial Layers
            </label>
            
            <div className="space-y-2">
              {/* Layer 1: Legacy Cadastre (Shajra Blue) */}
              <div className="gis-glass-card rounded-xl p-2.5 border border-surface-border">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2.5">
                    <span className="w-3 h-3 rounded-full bg-blue-500 shadow-sm shadow-blue-500/30"></span>
                    <div>
                      <div className="text-xs font-semibold text-blue-300">Legacy Cadastre (Shajra)</div>
                      <div className="text-[10px] text-slate-400">Distorted Paper/Cloth Vector</div>
                    </div>
                  </div>
                  <button
                    onClick={() => onToggleLayer('legacy')}
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    {layerVisibility.legacy ? <Eye className="w-4 h-4 text-blue-400" /> : <EyeOff className="w-4 h-4" />}
                  </button>
                </div>

                {layerVisibility.legacy && (
                  <div className="flex items-center space-x-2 pt-1.5 border-t border-surface-border/50">
                    <span className="text-[10px] font-mono text-slate-400">Alpha</span>
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={layerOpacity.legacy}
                      onChange={(e) => onChangeOpacity('legacy', parseFloat(e.target.value))}
                      className="w-full h-1 bg-surface rounded-lg appearance-none cursor-pointer"
                    />
                    <span className="text-[10px] font-mono text-slate-300 w-6 text-right">
                      {Math.round(layerOpacity.legacy * 100)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Layer 2: AI SAM-2 Segmented Walls (Snapped Green) */}
              <div className="gis-glass-card rounded-xl p-2.5 border border-surface-border">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2.5">
                    <span className="w-3 h-3 rounded-full bg-emerald-400 shadow-sm shadow-emerald-500/30"></span>
                    <div>
                      <div className="text-xs font-semibold text-emerald-300">AI SAM-2 Walls</div>
                      <div className="text-[10px] text-slate-400">Snapped Foundation Footprints</div>
                    </div>
                  </div>
                  <button
                    onClick={() => onToggleLayer('aiWalls')}
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    {layerVisibility.aiWalls ? <Eye className="w-4 h-4 text-emerald-400" /> : <EyeOff className="w-4 h-4" />}
                  </button>
                </div>

                {layerVisibility.aiWalls && (
                  <div className="flex items-center space-x-2 pt-1.5 border-t border-surface-border/50">
                    <span className="text-[10px] font-mono text-slate-400">Alpha</span>
                    <input
                      type="range"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={layerOpacity.aiWalls}
                      onChange={(e) => onChangeOpacity('aiWalls', parseFloat(e.target.value))}
                      className="w-full h-1 bg-surface rounded-lg appearance-none cursor-pointer"
                    />
                    <span className="text-[10px] font-mono text-slate-300 w-6 text-right">
                      {Math.round(layerOpacity.aiWalls * 100)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Layer 3: Drainage Canal */}
              <div className="gis-glass-card rounded-xl p-2.5 flex items-center justify-between border border-surface-border">
                <div className="flex items-center space-x-2.5">
                  <span className="w-3 h-3 rounded-full bg-teal-400 shadow-sm shadow-teal-400/30"></span>
                  <div>
                    <div className="text-xs font-semibold text-teal-300">Stormwater Drainage</div>
                    <div className="text-[10px] text-slate-400">3m Municipal Buffer</div>
                  </div>
                </div>
                <button
                  onClick={() => onToggleLayer('drainage')}
                  className="text-slate-400 hover:text-white transition-colors"
                >
                  {layerVisibility.drainage ? <Eye className="w-4 h-4 text-teal-400" /> : <EyeOff className="w-4 h-4" />}
                </button>
              </div>

              {/* Layer 4: Road Right-of-Way */}
              <div className="gis-glass-card rounded-xl p-2.5 flex items-center justify-between border border-surface-border">
                <div className="flex items-center space-x-2.5">
                  <span className="w-3 h-3 rounded-full bg-amber-400 shadow-sm shadow-amber-400/30"></span>
                  <div>
                    <div className="text-xs font-semibold text-amber-300">14m Road Right-of-Way</div>
                    <div className="text-[10px] text-slate-400">Public Corridor Bounds</div>
                  </div>
                </div>
                <button
                  onClick={() => onToggleLayer('roadRow')}
                  className="text-slate-400 hover:text-white transition-colors"
                >
                  {layerVisibility.roadRow ? <Eye className="w-4 h-4 text-amber-400" /> : <EyeOff className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* GeoAI Parameters Tuner Dropdown */}
          <div className="border-t border-surface-border pt-3">
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="w-full flex items-center justify-between text-[11px] font-mono font-semibold text-slate-400 hover:text-slate-200 mb-2 transition-colors"
            >
              <span className="flex items-center space-x-1.5">
                <Settings2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>GeoAI Conflation Tuning</span>
              </span>
              <span>{showSettings ? '▲' : '▼'}</span>
            </button>

            {showSettings && (
              <div className="gis-glass-card rounded-xl p-3 space-y-3 border border-surface-border">
                <div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                    <span>Vertex Snapping (ε)</span>
                    <span className="text-indigo-400 font-semibold">{geoAiParams.snapToleranceCm} cm</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    step="1"
                    value={geoAiParams.snapToleranceCm}
                    onChange={(e) => onChangeGeoAiParam('snapToleranceCm', parseInt(e.target.value))}
                    className="w-full h-1 bg-surface rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                    <span>Min Sliver Area</span>
                    <span className="text-indigo-400 font-semibold">{geoAiParams.minSliverAreaSqm} m²</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="5.0"
                    step="0.5"
                    value={geoAiParams.minSliverAreaSqm}
                    onChange={(e) => onChangeGeoAiParam('minSliverAreaSqm', parseFloat(e.target.value))}
                    className="w-full h-1 bg-surface rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                    <span>nDSM Eave Contraction</span>
                    <span className="text-indigo-400 font-semibold">{geoAiParams.eaveBufferM} m</span>
                  </div>
                  <input
                    type="range"
                    min="0.2"
                    max="0.8"
                    step="0.05"
                    value={geoAiParams.eaveBufferM}
                    onChange={(e) => onChangeGeoAiParam('eaveBufferM', parseFloat(e.target.value))}
                    className="w-full h-1 bg-surface rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Collapsed Icon Bar */
        <div className="p-2 space-y-3 flex flex-col items-center">
          <button onClick={() => setIsCollapsed(false)} className="p-2 rounded-lg bg-surface-raised text-indigo-400" title="Expand">
            <Layers className="w-4 h-4" />
          </button>
          <div className="w-2 h-2 rounded-full bg-emerald-400" title="AI Walls"></div>
          <div className="w-2 h-2 rounded-full bg-blue-400" title="Legacy Cadastre"></div>
          <div className="w-2 h-2 rounded-full bg-teal-400" title="Drainage"></div>
          <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" title="Encroachments"></div>
        </div>
      )}
    </aside>
  );
}
