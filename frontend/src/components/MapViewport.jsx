import React, { useRef, useEffect, useState } from 'react';
import { 
  Plus, Minus, RotateCcw, Compass, Maximize2, 
  Layers, Sliders, Eye, EyeOff, AlertCircle, Sparkles, Box, Map as MapIcon
} from 'lucide-react';

export default function MapViewport({
  parcels,
  selectedParcel,
  onSelectParcel,
  layerVisibility,
  layerOpacity,
  viewMode, // '2d' or '3d'
  infrastructure,
  activeEncroachmentFocus
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  // Split Screen Swipe position (0 to 100 percentage)
  const [swipePos, setSwipePos] = useState(50);
  const [isDraggingSlider, setIsDraggingSlider] = useState(false);

  // Viewport transformation state (Pan & Zoom)
  const [transform, setTransform] = useState({
    x: 0,
    y: 0,
    k: 1.0,
    isPanning: false,
    startX: 0,
    startY: 0
  });

  // Mouse hover state for instant tooltip
  const [hoveredParcel, setHoveredParcel] = useState(null);
  const [mouseCoord, setMouseCoord] = useState({ x: 0, y: 0, lat: 18.5204, lon: 73.8567 });

  // Center coordinate bounds of Ward 14 Pune
  const bounds = {
    minLon: 73.8510,
    maxLon: 73.8624,
    minLat: 18.5160,
    maxLat: 18.5255
  };

  // Convert geographic coordinates (lon, lat) to canvas pixel coordinates
  const project = (lon, lat, width, height) => {
    const normX = (lon - bounds.minLon) / (bounds.maxLon - bounds.minLon);
    const normY = 1.0 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat);
    
    const margin = 40;
    const baseW = width - margin * 2;
    const baseH = height - margin * 2;

    const px = margin + normX * baseW;
    const py = margin + normY * baseH;

    // Apply viewport pan and zoom
    const centerX = width / 2;
    const centerY = height / 2;

    const screenX = (px - centerX) * transform.k + centerX + transform.x;
    const screenY = (py - centerY) * transform.k + centerY + transform.y;

    return [screenX, screenY];
  };

  // Focus on selected parcel or encroachment if changed
  useEffect(() => {
    if (activeEncroachmentFocus) {
      const p = parcels.find(item => item.parcel_id === activeEncroachmentFocus.parcel_id);
      if (p && containerRef.current) {
        onSelectParcel(p);
      }
    }
  }, [activeEncroachmentFocus]);

  // Main Render Loop for Split-Screen & 3D Extrusion
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = containerRef.current.clientWidth;
    const height = canvas.height = containerRef.current.clientHeight;

    ctx.clearRect(0, 0, width, height);

    const splitX = (width * swipePos) / 100;

    // --- Helper function to draw background simulated high-res drone raster ---
    const drawDroneBase = (clipLeft, clipRight) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipLeft, 0, clipRight - clipLeft, height);
      ctx.clip();

      // Drone imagery dark urban grid base
      ctx.fillStyle = '#0b111e';
      ctx.fillRect(clipLeft, 0, clipRight - clipLeft, height);

      // Draw subtle urban street grid / texture
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
      ctx.lineWidth = 1;
      const gridSize = 40 * transform.k;
      const startGridX = (transform.x % gridSize);
      const startGridY = (transform.y % gridSize);

      for (let x = startGridX; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = startGridY; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw Drone tile footprint markers
      ctx.fillStyle = 'rgba(56, 189, 248, 0.03)';
      ctx.fillRect(clipLeft, 0, clipRight - clipLeft, height);

      ctx.restore();
    };

    // --- Draw Infrastructure Layers (Drainage & Road ROW) ---
    const drawInfrastructure = (clipLeft, clipRight) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(clipLeft, 0, clipRight - clipLeft, height);
      ctx.clip();

      // 1. Stormwater Drainage Canal
      if (layerVisibility.drainage && infrastructure?.drainage) {
        ctx.save();
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = Math.max(3, 4 * transform.k);
        ctx.setLineDash([8, 6]);
        ctx.shadowColor = '#06b6d4';
        ctx.shadowBlur = 10;
        
        ctx.beginPath();
        infrastructure.drainage.forEach(([lon, lat], i) => {
          const [px, py] = project(lon, lat, width, height);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();

        // Drainage 3m buffer zone
        ctx.strokeStyle = 'rgba(6, 182, 212, 0.2)';
        ctx.lineWidth = Math.max(12, 16 * transform.k);
        ctx.setLineDash([]);
        ctx.stroke();
        ctx.restore();
      }

      // 2. Road Right-of-Way (RoW)
      if (layerVisibility.roadRow && infrastructure?.road) {
        ctx.save();
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.8)';
        ctx.lineWidth = Math.max(8, 14 * transform.k);
        ctx.setLineDash([12, 8]);
        
        ctx.beginPath();
        infrastructure.road.forEach(([lon, lat], i) => {
          const [px, py] = project(lon, lat, width, height);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.stroke();
        ctx.restore();
      }

      ctx.restore();
    };

    // --- LEFT SIDE: RAW DISTORTED LEGACY CADASTRE (Shajra/Musavi Blue) ---
    drawDroneBase(0, splitX);
    drawInfrastructure(0, splitX);

    if (layerVisibility.legacy) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, splitX, height);
      ctx.clip();
      ctx.globalAlpha = layerOpacity.legacy;

      parcels.forEach(p => {
        const isSelected = selectedParcel?.parcel_id === p.parcel_id;
        const coords = p.coordinates_legacy;
        if (!coords || coords.length === 0) return;

        ctx.beginPath();
        coords.forEach(([lon, lat], i) => {
          const [px, py] = project(lon, lat, width, height);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        ctx.closePath();

        // Legacy fill (Translucent distressed blue)
        ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.4)' : 'rgba(30, 58, 138, 0.18)';
        ctx.fill();

        // Legacy stroke (Crooked dashed blue lines)
        ctx.strokeStyle = isSelected ? '#60a5fa' : '#38bdf8';
        ctx.lineWidth = isSelected ? 2.5 : 1.2;
        ctx.setLineDash([5, 3]);
        ctx.stroke();
      });

      ctx.restore();
    }

    // --- RIGHT SIDE: AI HARMONIZED BOUNDARIES (SAM-2 Snapped Green & Red Encroachments) ---
    drawDroneBase(splitX, width);
    drawInfrastructure(splitX, width);

    if (layerVisibility.aiWalls) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(splitX, 0, width - splitX, height);
      ctx.clip();
      ctx.globalAlpha = layerOpacity.aiWalls;

      parcels.forEach(p => {
        const isSelected = selectedParcel?.parcel_id === p.parcel_id;
        const coords = p.coordinates_ai;
        if (!coords || coords.length === 0) return;

        // 3D Digital Twin Isometric Height Extrusion
        if (viewMode === '3d') {
          const heightOffset = (p.ndsm_height_m || 5.0) * 2.2 * transform.k;

          // Draw extruded building side walls
          ctx.beginPath();
          const basePts = coords.map(([lon, lat]) => project(lon, lat, width, height));
          const topPts = basePts.map(([px, py]) => [px, py - heightOffset]);

          for (let i = 0; i < basePts.length - 1; i++) {
            ctx.beginPath();
            ctx.moveTo(basePts[i][0], basePts[i][1]);
            ctx.lineTo(basePts[i+1][0], basePts[i+1][1]);
            ctx.lineTo(topPts[i+1][0], topPts[i+1][1]);
            ctx.lineTo(topPts[i][0], topPts[i][1]);
            ctx.closePath();

            ctx.fillStyle = p.is_encroaching ? 'rgba(159, 18, 57, 0.5)' : 'rgba(6, 78, 59, 0.45)';
            ctx.fill();
            ctx.strokeStyle = p.is_encroaching ? '#e11d48' : '#059669';
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }

          // Draw extruded building roof top polygon
          ctx.beginPath();
          topPts.forEach(([tx, ty], i) => {
            if (i === 0) ctx.moveTo(tx, ty);
            else ctx.lineTo(tx, ty);
          });
          ctx.closePath();

          ctx.fillStyle = p.is_encroaching 
            ? (isSelected ? 'rgba(244, 63, 94, 0.7)' : 'rgba(225, 29, 72, 0.5)')
            : (isSelected ? 'rgba(16, 185, 129, 0.7)' : 'rgba(16, 185, 129, 0.28)');
          ctx.fill();

          ctx.strokeStyle = p.is_encroaching ? '#f43f5e' : (isSelected ? '#34d399' : '#10b981');
          ctx.lineWidth = isSelected ? 2.5 : 1.2;
          ctx.setLineDash([]);
          ctx.stroke();

        } else {
          // Standard 2D Cadastral Planimetric view
          ctx.beginPath();
          coords.forEach(([lon, lat], i) => {
            const [px, py] = project(lon, lat, width, height);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.closePath();

          if (p.is_encroaching) {
            // Encroachment styling (Alert red)
            ctx.fillStyle = isSelected ? 'rgba(244, 63, 94, 0.55)' : 'rgba(225, 29, 72, 0.35)';
            ctx.fill();

            ctx.strokeStyle = '#f43f5e';
            ctx.lineWidth = isSelected ? 3.0 : 1.8;
            ctx.shadowColor = '#f43f5e';
            ctx.shadowBlur = isSelected ? 12 : 6;
            ctx.stroke();
            ctx.shadowBlur = 0;
          } else if (p.status === 'Review') {
            // Review status (Amber)
            ctx.fillStyle = isSelected ? 'rgba(245, 158, 11, 0.45)' : 'rgba(245, 158, 11, 0.22)';
            ctx.fill();
            ctx.strokeStyle = '#fbbf24';
            ctx.lineWidth = isSelected ? 2.5 : 1.2;
            ctx.stroke();
          } else {
            // Approved Clean Title (Emerald Green)
            ctx.fillStyle = isSelected ? 'rgba(16, 185, 129, 0.45)' : 'rgba(16, 185, 129, 0.18)';
            ctx.fill();
            ctx.strokeStyle = isSelected ? '#34d399' : '#10b981';
            ctx.lineWidth = isSelected ? 2.5 : 1.1;
            ctx.stroke();
          }
        }

        // Draw Parcel ID Centroid Text Label if sufficiently zoomed in
        if (transform.k >= 1.2) {
          const [cx, cy] = project(p.centroid[0], p.centroid[1], width, height);
          ctx.font = '10px JetBrains Mono';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = p.is_encroaching ? '#fecdd3' : '#a7f3d0';
          ctx.fillText(p.khasra_no, cx, cy);
        }
      });

      ctx.restore();
    }

    // --- Draw Split Divider Line & Glow ---
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(splitX, 0);
    ctx.lineTo(splitX, height);
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2.5;
    ctx.shadowColor = '#06b6d4';
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.restore();

  }, [swipePos, transform, parcels, selectedParcel, layerVisibility, layerOpacity, viewMode, infrastructure]);

  // Mouse drag handling for the Split-Screen slider
  const handleSliderMouseDown = (e) => {
    e.stopPropagation();
    setIsDraggingSlider(true);
  };

  const handleMouseMove = (e) => {
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (isDraggingSlider) {
      const pct = Math.max(0, Math.min(100, (mouseX / rect.width) * 100));
      setSwipePos(pct);
    } else if (transform.isPanning) {
      setTransform(prev => ({
        ...prev,
        x: prev.x + (mouseX - prev.startX),
        y: prev.y + (mouseY - prev.startY),
        startX: mouseX,
        startY: mouseY
      }));
    } else {
      // Find hovered parcel
      const width = rect.width;
      const height = rect.height;
      
      let found = null;
      for (const p of parcels) {
        const [cx, cy] = project(p.centroid[0], p.centroid[1], width, height);
        const dist = Math.hypot(mouseX - cx, mouseY - cy);
        if (dist < 18 * transform.k) {
          found = p;
          break;
        }
      }
      setHoveredParcel(found);

      // Approximate coordinates
      const normX = (mouseX - transform.x) / (width * transform.k);
      const normY = (mouseY - transform.y) / (height * transform.k);
      const lon = bounds.minLon + normX * (bounds.maxLon - bounds.minLon);
      const lat = bounds.maxLat - normY * (bounds.maxLat - bounds.minLat);
      setMouseCoord({ x: mouseX, y: mouseY, lat, lon });
    }
  };

  const handleMouseUp = () => {
    setIsDraggingSlider(false);
    setTransform(prev => ({ ...prev, isPanning: false }));
  };

  const handleCanvasMouseDown = (e) => {
    if (isDraggingSlider) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (hoveredParcel) {
      onSelectParcel(hoveredParcel);
    } else {
      setTransform(prev => ({
        ...prev,
        isPanning: true,
        startX: mouseX,
        startY: mouseY
      }));
    }
  };

  // Zoom controls
  const handleZoom = (delta) => {
    setTransform(prev => ({
      ...prev,
      k: Math.max(0.6, Math.min(4.0, prev.k + delta))
    }));
  };

  const handleReset = () => {
    setTransform({ x: 0, y: 0, k: 1.0, isPanning: false, startX: 0, startY: 0 });
    setSwipePos(50);
  };

  return (
    <div 
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className="relative flex-1 h-full w-full bg-[#080c14] overflow-hidden select-none cursor-crosshair"
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleCanvasMouseDown}
        className="w-full h-full block"
      />

      {/* Floating Split Screen Labels */}
      <div className="absolute top-4 left-4 pointer-events-none z-10 flex items-center space-x-2">
        <div className="gis-glass px-3 py-1.5 rounded-lg border border-blue-500/40 text-blue-300 font-mono text-xs font-semibold flex items-center space-x-2 shadow-lg backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
          <span>LEGACY DISTORTED (Shajra/Musavi)</span>
        </div>
      </div>

      <div className="absolute top-4 right-4 pointer-events-none z-10 flex items-center space-x-2">
        <div className="gis-glass px-3 py-1.5 rounded-lg border border-emerald-500/40 text-emerald-300 font-mono text-xs font-semibold flex items-center space-x-2 shadow-lg backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>AI HARMONIZED (SAM-2 + nDSM Eaves)</span>
        </div>
      </div>

      {/* Center Interactive Slider Handle */}
      <div 
        style={{ left: `${swipePos}%` }}
        onMouseDown={handleSliderMouseDown}
        className="absolute top-0 bottom-0 w-8 -ml-4 z-20 flex items-center justify-center cursor-ew-resize group"
      >
        <div className="w-8 h-8 rounded-full bg-surface border-2 border-cyan-400 shadow-lg shadow-cyan-500/50 flex items-center justify-center group-hover:scale-110 transition-transform swipe-divider">
          <Sliders className="w-4 h-4 text-cyan-400" />
        </div>
      </div>

      {/* Map Control Toolbar (Bottom-Right) */}
      <div className="absolute bottom-6 right-6 z-10 flex flex-col space-y-2">
        <div className="gis-glass p-1.5 rounded-xl border border-surface-border flex flex-col space-y-1 shadow-2xl">
          <button
            onClick={() => handleZoom(0.25)}
            className="w-8 h-8 rounded-lg bg-surface-raised hover:bg-[#1E4C40] text-slate-200 hover:text-white flex items-center justify-center transition-colors"
            title="Zoom In"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleZoom(-0.25)}
            className="w-8 h-8 rounded-lg bg-surface-raised hover:bg-[#1E4C40] text-slate-200 hover:text-white flex items-center justify-center transition-colors"
            title="Zoom Out"
          >
            <Minus className="w-4 h-4" />
          </button>
          <div className="h-px bg-surface-border my-1"></div>
          <button
            onClick={handleReset}
            className="w-8 h-8 rounded-lg bg-surface-raised hover:bg-[#1E4C40] text-slate-200 hover:text-white flex items-center justify-center transition-colors"
            title="Reset View & Split"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Coordinate Readout & Scale Bar (Bottom-Left) */}
      <div className="absolute bottom-6 left-6 z-10 flex items-center space-x-3 pointer-events-none">
        <div className="gis-glass px-3 py-1.5 rounded-lg border border-surface-border font-mono text-[11px] text-slate-300 flex items-center space-x-3">
          <span className="text-cyan-400 font-semibold">EPSG:4326</span>
          <span>Lat: {mouseCoord.lat.toFixed(6)}° N</span>
          <span>Lon: {mouseCoord.lon.toFixed(6)}° E</span>
          <span className="text-slate-500">|</span>
          <span className="text-emerald-400">Zoom: {transform.k.toFixed(1)}x</span>
        </div>

        <div className="gis-glass px-3 py-1.5 rounded-lg border border-surface-border flex items-center space-x-2">
          <div className="w-12 h-1 bg-slate-200 border-x border-white"></div>
          <span className="font-mono text-[10px] text-slate-300">50 m</span>
        </div>
      </div>

      {/* Instant Hover Tooltip */}
      {hoveredParcel && !isDraggingSlider && !transform.isPanning && (
        <div 
          style={{ left: `${mouseCoord.x + 15}px`, top: `${mouseCoord.y + 15}px` }}
          className="absolute z-30 pointer-events-none gis-glass-card p-3 rounded-lg border border-surface-border text-xs min-w-[210px] shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-surface-border">
            <span className="font-mono font-bold text-white text-xs">{hoveredParcel.khasra_no}</span>
            <span className={`px-1.5 py-0.5 rounded font-mono text-[9px] font-bold ${
              hoveredParcel.is_encroaching 
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' 
                : hoveredParcel.status === 'Review'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }`}>
              {hoveredParcel.status_chip}
            </span>
          </div>

          <div className="space-y-1 text-[11px]">
            <div className="text-slate-300 font-medium truncate">{hoveredParcel.owner_en}</div>
            <div className="text-slate-400 font-mono text-[10px] truncate">{hoveredParcel.ulpin}</div>
            <div className="flex justify-between text-slate-400 text-[10px] pt-1">
              <span>Surveyed: <b className="text-slate-200">{hoveredParcel.surveyed_area_sqm} m²</b></span>
              <span>AI Conf: <b className="text-cyan-400">{hoveredParcel.confidence_score}%</b></span>
            </div>
            {hoveredParcel.is_encroaching && (
              <div className="mt-1.5 p-1 rounded bg-rose-950/60 border border-rose-500/40 text-[10px] text-rose-300 font-medium">
                ⚠️ {hoveredParcel.encroachment_type} (+{hoveredParcel.encroached_area_sqm} m²)
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
