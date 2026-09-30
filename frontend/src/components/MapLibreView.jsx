import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { Map, setWorkerUrl } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

// Configure MapLibre Web Worker for Vite production bundles
try {
  if (typeof setWorkerUrl === 'function' && workerUrl) {
    setWorkerUrl(workerUrl);
  }
} catch (e) {
  console.warn('MapLibre workerUrl setup:', e);
}

import {
  Plus, Minus, RotateCcw, Box, Map as MapIcon,
  Satellite, Sliders, AlertTriangle, Compass,
  CheckCircle2, Moon
} from 'lucide-react';
import { drainageLine, roadLine } from '../data/puneWard14Data';

// Center and default zoom for Pune
const PUNE_CENTER = [73.8567, 18.5204];
const DEFAULT_ZOOM = 17.2;

// CARTO API Key
const CARTO_API_KEY = import.meta.env.VITE_CARTO_API_KEY || 'cb1_27y0_1_9b33dcb1032562b41e545bda';

// Basemap Tile Sources
const BASEMAPS = {
  satellite: {
    name: 'Esri Satellite',
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    maxzoom: 19,
    attribution: 'Tiles &copy; Esri'
  },
  streets: {
    name: 'Carto Positron (Light)',
    tiles: [`https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}.png?key=${CARTO_API_KEY}`],
    maxzoom: 19,
    attribution: '&copy; CARTO'
  },
  voyager: {
    name: 'Carto Voyager',
    tiles: [`https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${CARTO_API_KEY}`],
    maxzoom: 19,
    attribution: '&copy; CARTO'
  },
  dark: {
    name: 'Carto Dark Matter',
    tiles: [`https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${CARTO_API_KEY}`],
    maxzoom: 19,
    attribution: '&copy; CARTO'
  }
};

// Convert parcels list to Harmonized GeoJSON
function parcelsToHarmonizedGeoJSON(parcels) {
  if (!parcels || !parcels.length) return { type: 'FeatureCollection', features: [] };
  return {
    type: 'FeatureCollection',
    features: parcels.map((p, idx) => {
      const rawCoords = p.coordinates_ai || (p.geometry && p.geometry.coordinates ? p.geometry.coordinates[0] : null);
      if (!rawCoords || !rawCoords.length) return null;
      return {
        type: 'Feature',
        id: idx + 1,
        properties: {
          parcel_id: p.parcel_id || `MH-${idx}`,
          ulpin: p.ulpin || '',
          khasra_no: p.khasra_no || `${idx}`,
          owner_en: p.owner_en || p.owner_name || '',
          owner_name: p.owner_en || p.owner_name || '',
          owner_vernacular: p.owner_vernacular || '',
          legal_area_sqm: p.legal_area_sqm || 0,
          surveyed_area_sqm: p.surveyed_area_sqm || 0,
          area_diff_sqm: p.area_diff_sqm !== undefined ? p.area_diff_sqm : +( (p.surveyed_area_sqm || 0) - (p.legal_area_sqm || 0) ).toFixed(1),
          delta_area_pct: p.delta_area_pct || 0,
          confidence_score: p.confidence_score || 95,
          status: p.status || 'Approved',
          status_chip: p.status_chip || p.status || 'APPROVED',
          ndsm_height_m: p.ndsm_height_m || 6.5,
          eave_buffer_m: p.eave_buffer_m || 0.0,
          is_encroaching: !!p.is_encroaching,
          encroachment_type: p.encroachment_type || p.discrepancy_type || '',
          discrepancy_type: p.discrepancy_type || p.encroachment_type || '',
          encroached_area_sqm: p.encroached_area_sqm || 0,
          variance_sqm: p.variance_sqm || `+${p.encroached_area_sqm || 0} sq.m`,
          iou_pct: p.iou_pct || 96.2,
          centroid: p.centroid || rawCoords[0]
        },
        geometry: {
          type: 'Polygon',
          coordinates: [rawCoords]
        }
      };
    }).filter(Boolean)
  };
}

// Convert parcels list to Distorted Legacy GeoJSON (Cloth Shajra Map)
function parcelsToLegacyGeoJSON(parcels) {
  if (!parcels || !parcels.length) return { type: 'FeatureCollection', features: [] };
  return {
    type: 'FeatureCollection',
    features: parcels.map((p, idx) => {
      const rawCoords = p.coordinates_legacy || p.coordinates_ai || (p.geometry && p.geometry.coordinates ? p.geometry.coordinates[0] : null);
      if (!rawCoords || !rawCoords.length) return null;
      return {
        type: 'Feature',
        id: idx + 1,
        properties: {
          parcel_id: p.parcel_id || `MH-${idx}`,
          ulpin: p.ulpin || '',
          khasra_no: p.khasra_no || `${idx}`,
          owner_en: p.owner_en || p.owner_name || '',
          owner_name: p.owner_en || p.owner_name || '',
          owner_vernacular: p.owner_vernacular || '',
          legal_area_sqm: p.legal_area_sqm || 0,
          surveyed_area_sqm: p.surveyed_area_sqm || 0,
          area_diff_sqm: p.area_diff_sqm !== undefined ? p.area_diff_sqm : +( (p.surveyed_area_sqm || 0) - (p.legal_area_sqm || 0) ).toFixed(1),
          delta_area_pct: p.delta_area_pct || 0,
          status: p.status || 'Approved',
          status_chip: 'LEGACY DISTORTED',
          confidence_score: 55.0,
          is_encroaching: !!p.is_encroaching,
          encroachment_type: p.encroachment_type || p.discrepancy_type || '',
          discrepancy_type: p.discrepancy_type || p.encroachment_type || '',
          encroached_area_sqm: p.encroached_area_sqm || 0,
          isLegacy: true,
          centroid: p.centroid || rawCoords[0]
        },
        geometry: {
          type: 'Polygon',
          coordinates: [rawCoords]
        }
      };
    }).filter(Boolean)
  };
}

export default function MapLibreView({
  parcelsList = [],
  selectedParcel,
  onSelectParcel,
  layerVisibility = { legacy: true, aiWalls: true, drainage: true, roadRow: true },
  layerOpacity = { legacy: 0.85, aiWalls: 0.95 },
  viewMode = '2d',
  onChangeViewMode,
  sectorInfo,
  infrastructure
}) {
  const containerRef = useRef(null);
  const leftMapContainerRef = useRef(null);
  const rightMapContainerRef = useRef(null);

  const leftMapRef = useRef(null);
  const rightMapRef = useRef(null);

  // Split-Screen Swipe position (0% - 100%)
  const [swipePos, setSwipePos] = useState(50);
  const [isDraggingSlider, setIsDraggingSlider] = useState(false);

  // Selected Basemap: 'satellite' | 'streets' | 'voyager' | 'dark'
  const [activeBasemap, setActiveBasemap] = useState('satellite');

  // Hovered parcel state for popup
  const [hoveredInfo, setHoveredInfo] = useState(null);

  // GeoJSON data derived from parcelsList
  const harmonizedGeoJSON = useMemo(() => parcelsToHarmonizedGeoJSON(parcelsList), [parcelsList]);
  const legacyGeoJSON = useMemo(() => parcelsToLegacyGeoJSON(parcelsList), [parcelsList]);

  // Infrastructure GeoJSON
  const drainageGeoJSON = useMemo(() => {
    const coords = infrastructure?.drainage || drainageLine;
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { name: 'Stormwater Canal', type: 'Drainage' },
        geometry: { type: 'LineString', coordinates: coords }
      }]
    };
  }, [infrastructure]);

  const roadGeoJSON = useMemo(() => {
    const coords = infrastructure?.road || roadLine;
    return {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { name: 'Municipal Road Right-of-Way Corridor (14m)', type: 'Road' },
        geometry: { type: 'LineString', coordinates: coords }
      }]
    };
  }, [infrastructure]);

  // Compute live KPIs
  const totalCount = parcelsList?.length || 0;
  const approvedCount = parcelsList?.filter(p => p.status === 'Approved').length || 0;
  const harmonizedRate = totalCount > 0 ? ((approvedCount / totalCount) * 100).toFixed(1) : '0.0';
  const conflictCount = parcelsList?.filter(p => p.is_encroaching || p.status === 'Encroachment').length || 0;

  // Declarative Style Object for Left Map (Legacy Distorted Cadastre)
  const createLeftMapStyle = useCallback((basemapKey) => {
    const basemap = BASEMAPS[basemapKey] || BASEMAPS.satellite;
    return {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        'raster-tiles': {
          type: 'raster',
          tiles: basemap.tiles,
          tileSize: 256,
          maxzoom: basemap.maxzoom,
          attribution: basemap.attribution
        },
        'legacy-parcels': {
          type: 'geojson',
          data: legacyGeoJSON
        },
        'infra-drain-source-left': {
          type: 'geojson',
          data: drainageGeoJSON
        },
        'infra-road-source-left': {
          type: 'geojson',
          data: roadGeoJSON
        }
      },
      layers: [
        {
          id: 'raster-layer',
          type: 'raster',
          source: 'raster-tiles',
          minzoom: 0,
          maxzoom: 22
        },
        {
          id: 'legacy-fill',
          type: 'fill',
          source: 'legacy-parcels',
          layout: {
            visibility: layerVisibility?.legacy !== false ? 'visible' : 'none'
          },
          paint: {
            'fill-color': '#2563eb',
            'fill-opacity': 0.35 * (layerOpacity?.legacy ?? 0.85)
          }
        },
        {
          id: 'legacy-line',
          type: 'line',
          source: 'legacy-parcels',
          layout: {
            visibility: layerVisibility?.legacy !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': '#38bdf8',
            'line-width': 2.2,
            'line-dasharray': [3, 2]
          }
        },
        {
          id: 'infra-drainage-left',
          type: 'line',
          source: 'infra-drain-source-left',
          layout: {
            visibility: layerVisibility?.drainage !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': '#06b6d4',
            'line-width': 4.0,
            'line-dasharray': [4, 2]
          }
        },
        {
          id: 'infra-road-left',
          type: 'line',
          source: 'infra-road-source-left',
          layout: {
            visibility: layerVisibility?.roadRow !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': '#f59e0b',
            'line-width': 6.5,
            'line-opacity': 0.45
          }
        }
      ]
    };
  }, [legacyGeoJSON, drainageGeoJSON, roadGeoJSON, layerVisibility, layerOpacity]);

  // Declarative Style Object for Right Map (AI Harmonized SAM-2 Ground Truth)
  const createRightMapStyle = useCallback((basemapKey) => {
    const basemap = BASEMAPS[basemapKey] || BASEMAPS.satellite;
    return {
      version: 8,
      glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      sources: {
        'raster-tiles': {
          type: 'raster',
          tiles: basemap.tiles,
          tileSize: 256,
          maxzoom: basemap.maxzoom,
          attribution: basemap.attribution
        },
        'harmonized-parcels': {
          type: 'geojson',
          data: harmonizedGeoJSON
        },
        'infra-drain-source-right': {
          type: 'geojson',
          data: drainageGeoJSON
        },
        'infra-road-source-right': {
          type: 'geojson',
          data: roadGeoJSON
        }
      },
      layers: [
        {
          id: 'raster-layer',
          type: 'raster',
          source: 'raster-tiles',
          minzoom: 0,
          maxzoom: 22
        },
        {
          id: 'harmonized-fill',
          type: 'fill',
          source: 'harmonized-parcels',
          layout: {
            visibility: layerVisibility?.aiWalls !== false ? 'visible' : 'none'
          },
          paint: {
            'fill-color': [
              'match',
              ['get', 'status'],
              'Encroachment', '#f43f5e',
              'Review', '#f59e0b',
              'Approved', '#10b981',
              '#10b981'
            ],
            'fill-opacity': [
              'match',
              ['get', 'status'],
              'Encroachment', 0.58 * (layerOpacity?.aiWalls ?? 0.95),
              'Review', 0.42 * (layerOpacity?.aiWalls ?? 0.95),
              0.34 * (layerOpacity?.aiWalls ?? 0.95)
            ]
          }
        },
        {
          id: 'harmonized-line',
          type: 'line',
          source: 'harmonized-parcels',
          layout: {
            visibility: layerVisibility?.aiWalls !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': [
              'match',
              ['get', 'status'],
              'Encroachment', '#f43f5e',
              'Review', '#f59e0b',
              'Approved', '#10b981',
              '#10b981'
            ],
            'line-width': [
              'match',
              ['get', 'status'],
              'Encroachment', 3.2,
              'Review', 2.4,
              2.0
            ]
          }
        },
        {
          id: 'harmonized-3d-extrusion',
          type: 'fill-extrusion',
          source: 'harmonized-parcels',
          layout: {
            visibility: viewMode === '3d' && layerVisibility?.aiWalls !== false ? 'visible' : 'none'
          },
          paint: {
            'fill-extrusion-color': [
              'match',
              ['get', 'status'],
              'Encroachment', '#e11d48',
              'Review', '#d97706',
              'Approved', '#059669',
              '#059669'
            ],
            'fill-extrusion-height': ['get', 'ndsm_height_m'],
            'fill-extrusion-base': 0,
            'fill-extrusion-opacity': 0.85
          }
        },
        {
          id: 'harmonized-selected',
          type: 'line',
          source: 'harmonized-parcels',
          paint: {
            'line-color': '#06b6d4',
            'line-width': 4.5,
            'line-opacity': 0.95
          },
          filter: ['==', ['get', 'parcel_id'], selectedParcel?.parcel_id || '']
        },
        {
          id: 'infra-drainage-right',
          type: 'line',
          source: 'infra-drain-source-right',
          layout: {
            visibility: layerVisibility?.drainage !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': '#06b6d4',
            'line-width': 4.5,
            'line-dasharray': [4, 2]
          }
        },
        {
          id: 'infra-road-right',
          type: 'line',
          source: 'infra-road-source-right',
          layout: {
            visibility: layerVisibility?.roadRow !== false ? 'visible' : 'none'
          },
          paint: {
            'line-color': '#f59e0b',
            'line-width': 7.5,
            'line-opacity': 0.55
          }
        }
      ]
    };
  }, [harmonizedGeoJSON, drainageGeoJSON, roadGeoJSON, layerVisibility, layerOpacity, viewMode, selectedParcel]);

  // Initialize Dual Synchronized MapLibre Instances
  useEffect(() => {
    if (!leftMapContainerRef.current || !rightMapContainerRef.current) return;

    const centerCoord = sectorInfo?.center || PUNE_CENTER;
    const zoomLevel = sectorInfo?.zoom || DEFAULT_ZOOM;

    // 1. Initialize Left Map (Legacy Distorted Layer)
    const leftMap = new Map({
      container: leftMapContainerRef.current,
      style: createLeftMapStyle(activeBasemap),
      center: centerCoord,
      zoom: zoomLevel,
      pitch: viewMode === '3d' ? 50 : 0,
      bearing: viewMode === '3d' ? -15 : 0,
      attributionControl: false
    });

    // 2. Initialize Right Map (AI Harmonized Layer)
    const rightMap = new Map({
      container: rightMapContainerRef.current,
      style: createRightMapStyle(activeBasemap),
      center: centerCoord,
      zoom: zoomLevel,
      pitch: viewMode === '3d' ? 50 : 0,
      bearing: viewMode === '3d' ? -15 : 0,
      attributionControl: false
    });

    leftMapRef.current = leftMap;
    rightMapRef.current = rightMap;

    // Dual Map Camera Synchronization
    let isSyncing = false;
    const syncMaps = (sourceMap, targetMap) => {
      if (isSyncing) return;
      isSyncing = true;
      targetMap.jumpTo({
        center: sourceMap.getCenter(),
        zoom: sourceMap.getZoom(),
        bearing: sourceMap.getBearing(),
        pitch: sourceMap.getPitch()
      });
      isSyncing = false;
    };

    leftMap.on('move', () => syncMaps(leftMap, rightMap));
    rightMap.on('move', () => syncMaps(rightMap, leftMap));

    // Parcel Click Handler on Right Map
    rightMap.on('click', 'harmonized-fill', (e) => {
      if (e.features && e.features.length > 0) {
        const props = e.features[0].properties;
        const matched = parcelsList?.find(p => p.parcel_id === props.parcel_id) || props;
        if (onSelectParcel) onSelectParcel(matched);
      }
    });

    // Parcel Click Handler on Left Map
    leftMap.on('click', 'legacy-fill', (e) => {
      if (e.features && e.features.length > 0) {
        const props = e.features[0].properties;
        const matched = parcelsList?.find(p => p.parcel_id === props.parcel_id) || props;
        if (onSelectParcel) onSelectParcel(matched);
      }
    });

    // Cursor & Hover Tooltip
    rightMap.on('mousemove', 'harmonized-fill', (e) => {
      rightMap.getCanvas().style.cursor = 'pointer';
      if (e.features && e.features.length > 0) {
        setHoveredInfo({
          props: e.features[0].properties,
          x: e.point.x,
          y: e.point.y
        });
      }
    });

    rightMap.on('mouseleave', 'harmonized-fill', () => {
      rightMap.getCanvas().style.cursor = '';
      setHoveredInfo(null);
    });

    return () => {
      leftMap.remove();
      rightMap.remove();
    };
  }, []); // Run once on mount

  // Sync data updates dynamically to existing map sources
  useEffect(() => {
    try {
      if (leftMapRef.current && leftMapRef.current.isStyleLoaded()) {
        const src = leftMapRef.current.getSource('legacy-parcels');
        if (src) src.setData(legacyGeoJSON);
      }
      if (rightMapRef.current && rightMapRef.current.isStyleLoaded()) {
        const src = rightMapRef.current.getSource('harmonized-parcels');
        if (src) src.setData(harmonizedGeoJSON);
      }
    } catch (e) {
      // Ignored if style is updating
    }
  }, [legacyGeoJSON, harmonizedGeoJSON]);

  // Update selected parcel filter and smooth flyTo
  useEffect(() => {
    if (rightMapRef.current && rightMapRef.current.isStyleLoaded() && rightMapRef.current.getLayer('harmonized-selected')) {
      rightMapRef.current.setFilter('harmonized-selected', [
        '==',
        ['get', 'parcel_id'],
        selectedParcel?.parcel_id || ''
      ]);
    }
    if (selectedParcel?.centroid && rightMapRef.current) {
      rightMapRef.current.flyTo({
        center: selectedParcel.centroid,
        zoom: 18.4,
        duration: 800
      });
    }
  }, [selectedParcel]);

  // Fly to sector center when sector changes
  useEffect(() => {
    if (sectorInfo?.center && rightMapRef.current) {
      rightMapRef.current.flyTo({
        center: sectorInfo.center,
        zoom: sectorInfo.zoom || DEFAULT_ZOOM,
        duration: 1000
      });
    }
  }, [sectorInfo]);

  // Apply Layer Visibility & Opacity updates dynamically
  useEffect(() => {
    const lm = leftMapRef.current;
    const rm = rightMapRef.current;

    // Left Map
    if (lm && lm.isStyleLoaded()) {
      const legVis = layerVisibility?.legacy !== false ? 'visible' : 'none';
      if (lm.getLayer('legacy-fill')) {
        lm.setLayoutProperty('legacy-fill', 'visibility', legVis);
        lm.setPaintProperty('legacy-fill', 'fill-opacity', 0.35 * (layerOpacity?.legacy ?? 0.85));
      }
      if (lm.getLayer('legacy-line')) lm.setLayoutProperty('legacy-line', 'visibility', legVis);

      const drainVis = layerVisibility?.drainage !== false ? 'visible' : 'none';
      if (lm.getLayer('infra-drainage-left')) lm.setLayoutProperty('infra-drainage-left', 'visibility', drainVis);

      const roadVis = layerVisibility?.roadRow !== false ? 'visible' : 'none';
      if (lm.getLayer('infra-road-left')) lm.setLayoutProperty('infra-road-left', 'visibility', roadVis);
    }

    // Right Map
    if (rm && rm.isStyleLoaded()) {
      const aiVis = layerVisibility?.aiWalls !== false ? 'visible' : 'none';
      if (rm.getLayer('harmonized-fill')) {
        rm.setLayoutProperty('harmonized-fill', 'visibility', aiVis);
        rm.setPaintProperty('harmonized-fill', 'fill-opacity', [
          'match',
          ['get', 'status'],
          'Encroachment', 0.58 * (layerOpacity?.aiWalls ?? 0.95),
          'Review', 0.42 * (layerOpacity?.aiWalls ?? 0.95),
          0.34 * (layerOpacity?.aiWalls ?? 0.95)
        ]);
      }
      if (rm.getLayer('harmonized-line')) rm.setLayoutProperty('harmonized-line', 'visibility', aiVis);
      if (rm.getLayer('harmonized-3d-extrusion')) {
        rm.setLayoutProperty('harmonized-3d-extrusion', 'visibility', viewMode === '3d' && aiVis === 'visible' ? 'visible' : 'none');
      }

      const drainVis = layerVisibility?.drainage !== false ? 'visible' : 'none';
      if (rm.getLayer('infra-drainage-right')) rm.setLayoutProperty('infra-drainage-right', 'visibility', drainVis);

      const roadVis = layerVisibility?.roadRow !== false ? 'visible' : 'none';
      if (rm.getLayer('infra-road-right')) rm.setLayoutProperty('infra-road-right', 'visibility', roadVis);
    }
  }, [layerVisibility, layerOpacity, viewMode]);

  // Update Basemap Style dynamically
  const handleChangeBasemap = (key) => {
    setActiveBasemap(key);
    if (leftMapRef.current) leftMapRef.current.setStyle(createLeftMapStyle(key));
    if (rightMapRef.current) rightMapRef.current.setStyle(createRightMapStyle(key));
  };

  // Toggle 3D Digital Twin Pitch and 3D Extrusion
  useEffect(() => {
    const pitch = viewMode === '3d' ? 55 : 0;
    const bearing = viewMode === '3d' ? -20 : 0;

    if (leftMapRef.current) {
      leftMapRef.current.easeTo({ pitch, bearing, duration: 800 });
    }
    if (rightMapRef.current) {
      rightMapRef.current.easeTo({ pitch, bearing, duration: 800 });
      if (rightMapRef.current.isStyleLoaded() && rightMapRef.current.getLayer('harmonized-3d-extrusion')) {
        rightMapRef.current.setLayoutProperty(
          'harmonized-3d-extrusion',
          'visibility',
          viewMode === '3d' && layerVisibility?.aiWalls !== false ? 'visible' : 'none'
        );
      }
    }
  }, [viewMode, layerVisibility]);

  // Smooth Split-Screen Slider Dragging
  const handleSliderMouseDown = (e) => {
    e.preventDefault();
    setIsDraggingSlider(true);
  };

  const handleMouseMove = (e) => {
    if (!isDraggingSlider || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const newPos = Math.max(0, Math.min(100, (clientX / rect.width) * 100));
    setSwipePos(newPos);
  };

  const handleMouseUp = () => {
    setIsDraggingSlider(false);
  };

  // Zoom and View Controls
  const handleZoom = (delta) => {
    if (rightMapRef.current) {
      rightMapRef.current.zoomTo(rightMapRef.current.getZoom() + delta, { duration: 300 });
    }
  };

  const handleResetView = () => {
    if (rightMapRef.current) {
      const centerCoord = sectorInfo?.center || PUNE_CENTER;
      const zoomLevel = sectorInfo?.zoom || DEFAULT_ZOOM;
      rightMapRef.current.flyTo({
        center: centerCoord,
        zoom: zoomLevel,
        pitch: viewMode === '3d' ? 50 : 0,
        bearing: viewMode === '3d' ? -15 : 0,
        duration: 800
      });
      setSwipePos(50);
    }
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className="relative flex-1 h-full w-full overflow-hidden select-none bg-slate-950 font-sans"
    >
      {/* 1. Left Map Viewport (Legacy Distorted Cadastre) */}
      <div
        ref={leftMapContainerRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          width: '100%',
          clipPath: `polygon(0 0, ${swipePos}% 0, ${swipePos}% 100%, 0 100%)`
        }}
        className="h-full z-0 pointer-events-none"
      />

      {/* 2. Right Map Viewport (AI-Harmonized Snapped Boundaries) */}
      <div
        ref={rightMapContainerRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          width: '100%',
          clipPath: `polygon(${swipePos}% 0, 100% 0, 100% 100%, ${swipePos}% 100%)`
        }}
        className="h-full z-10"
      />

      {/* 3. Draggable Split-Screen Slider Handle */}
      <div
        style={{ left: `${swipePos}%` }}
        onMouseDown={handleSliderMouseDown}
        className="absolute top-0 bottom-0 w-10 -ml-5 z-30 flex items-center justify-center cursor-ew-resize group"
      >
        {/* Glow Line */}
        <div className="absolute top-0 bottom-0 w-0.5 bg-gradient-to-b from-indigo-500 via-emerald-400 to-indigo-500 shadow-[0_0_12px_rgba(99,102,241,0.6)]"></div>

        {/* Center Circular Handle */}
        <div className="w-8 h-8 rounded-full bg-[#0B1F1A] border-2 border-indigo-400 shadow-xl shadow-black/50 flex items-center justify-center group-hover:scale-110 group-hover:border-emerald-400 transition-all">
          <Sliders className="w-3.5 h-3.5 text-indigo-300 group-hover:text-emerald-300" />
        </div>
      </div>

      {/* 4. Floating Header Pill: Live KPIs (Top Center) */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
        <div className="bg-[#0B1F1A]/95 backdrop-blur-md px-4 py-2 rounded-full border border-slate-700/60 shadow-2xl flex items-center space-x-3 text-xs font-mono font-semibold text-slate-200">
          <div className="flex items-center space-x-1.5">
            <span className="text-indigo-400 font-bold">📍 {sectorInfo?.name || 'Ward 14, Pune'}</span>
            <span className="text-slate-600">|</span>
            <span className="text-white">{totalCount.toLocaleString()} Parcels</span>
          </div>

          <span className="text-slate-700">|</span>

          <div className="flex items-center space-x-1 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{harmonizedRate}% Harmonized</span>
          </div>

          <span className="text-slate-700">|</span>

          <div className="flex items-center space-x-1 text-rose-400">
            <AlertTriangle className="w-3.5 h-3.5 animate-pulse" />
            <span>{conflictCount} Encroachments Flagged</span>
          </div>
        </div>
      </div>

      {/* Floating Split Mode Badges */}
      <div className="absolute top-4 left-4 z-20 pointer-events-none">
        <div className="bg-[#0B1F1A]/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-blue-500/30 text-blue-300 font-mono text-xs font-bold shadow-xl flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
          <span>LEGACY DISTORTED (Shajra)</span>
        </div>
      </div>

      <div className="absolute top-4 right-4 z-20 pointer-events-none">
        <div className="bg-[#0B1F1A]/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-emerald-500/30 text-emerald-300 font-mono text-xs font-bold shadow-xl flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>AI HARMONIZED (SAM-2 + nDSM)</span>
        </div>
      </div>

      {/* 5. Floating Controls: Basemap & 3D Extrusion (Bottom-Left) */}
      <div className="absolute bottom-6 left-6 z-20 flex items-center space-x-2">
        {/* Basemap Switcher */}
        <div className="bg-[#0B1F1A]/95 backdrop-blur-md p-1 rounded-xl border border-slate-700/60 shadow-xl flex items-center space-x-1">
          <button
            onClick={() => handleChangeBasemap('satellite')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeBasemap === 'satellite'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-[#1A463B]'
              }`}
          >
            <Satellite className="w-3.5 h-3.5" />
            <span>Esri Satellite</span>
          </button>

          <button
            onClick={() => handleChangeBasemap('streets')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeBasemap === 'streets'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-[#1A463B]'
              }`}
          >
            <MapIcon className="w-3.5 h-3.5" />
            <span>Carto Positron</span>
          </button>

          <button
            onClick={() => handleChangeBasemap('voyager')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeBasemap === 'voyager'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-[#1A463B]'
              }`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>Voyager</span>
          </button>

          <button
            onClick={() => handleChangeBasemap('dark')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${activeBasemap === 'dark'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-300 hover:bg-[#1A463B]'
              }`}
          >
            <Moon className="w-3.5 h-3.5" />
            <span>Dark Matter</span>
          </button>
        </div>

        {/* 2D / 3D Digital Twin Extrusion Toggle */}
        <button
          onClick={() => onChangeViewMode(viewMode === '2d' ? '3d' : '2d')}
          className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold shadow-xl border backdrop-blur-md transition-all active:scale-95 ${viewMode === '3d'
              ? 'bg-emerald-600 text-white border-emerald-500 shadow-emerald-600/25'
              : 'bg-[#0B1F1A]/95 text-slate-200 border-slate-700/60 hover:bg-[#1A463B]'
            }`}
        >
          <Box className="w-4 h-4 text-emerald-400" />
          <span>{viewMode === '3d' ? '3D Digital Twin (Active)' : 'Enable 3D Extrusion'}</span>
        </button>
      </div>

      {/* 6. Map Zoom & Reset Navigation Toolbar (Bottom-Right) */}
      <div className="absolute bottom-6 right-6 z-20 flex flex-col space-y-1.5">
        <div className="bg-[#0B1F1A]/95 backdrop-blur-md p-1.5 rounded-xl border border-slate-700/60 shadow-xl flex flex-col space-y-1">
          <button
            onClick={() => handleZoom(0.5)}
            className="w-8 h-8 rounded-lg bg-[#16362E] hover:bg-indigo-600 hover:text-white text-slate-200 flex items-center justify-center transition-colors"
            title="Zoom In"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={() => handleZoom(-0.5)}
            className="w-8 h-8 rounded-lg bg-[#16362E] hover:bg-indigo-600 hover:text-white text-slate-200 flex items-center justify-center transition-colors"
            title="Zoom Out"
          >
            <Minus className="w-4 h-4" />
          </button>
          <div className="h-px bg-slate-700/60 my-0.5"></div>
          <button
            onClick={handleResetView}
            className="w-8 h-8 rounded-lg bg-[#16362E] hover:bg-indigo-600 hover:text-white text-slate-200 flex items-center justify-center transition-colors"
            title="Reset Map View"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Hover Tooltip on Parcel */}
      {hoveredInfo && !isDraggingSlider && (
        <div
          style={{
            left: `${hoveredInfo.x + 15}px`,
            top: `${hoveredInfo.y + 15}px`
          }}
          className="absolute z-40 pointer-events-none bg-[#0B1F1A]/95 backdrop-blur-md p-3 rounded-xl border border-slate-700/70 shadow-2xl text-xs min-w-[200px] animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-slate-800">
            <span className="font-mono font-bold text-white">
              {hoveredInfo.props.khasra_no}
            </span>
            <span
              className={`px-1.5 py-0.5 rounded font-mono text-[9px] font-bold ${hoveredInfo.props.status === 'Encroachment'
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                  : hoveredInfo.props.status === 'Review'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                }`}
            >
              {hoveredInfo.props.status_chip || hoveredInfo.props.status}
            </span>
          </div>

          <div className="space-y-1 text-[11px]">
            <div className="font-semibold text-slate-200">
              {hoveredInfo.props.owner_en}
            </div>
            <div className="text-slate-400 font-mono text-[10px]">
              {hoveredInfo.props.ulpin}
            </div>
            <div className="flex justify-between text-slate-400 text-[10px] pt-1 border-t border-slate-800">
              <span>Surveyed: <b className="text-slate-200">{hoveredInfo.props.surveyed_area_sqm} m²</b></span>
              <span>AI Conf: <b className="text-emerald-400">{hoveredInfo.props.confidence_score}%</b></span>
            </div>
            {hoveredInfo.props.is_encroaching && (
              <div className="mt-1.5 p-1.5 rounded-lg bg-rose-950/60 border border-rose-500/40 text-[10px] text-rose-300 font-medium">
                ⚠️ {hoveredInfo.props.encroachment_type} (+{hoveredInfo.props.encroached_area_sqm} m²)
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
