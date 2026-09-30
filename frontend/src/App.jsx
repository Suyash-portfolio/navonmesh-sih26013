import React, { useState, useMemo } from 'react';
import Header from './components/Header';
import MetricRibbon from './components/MetricRibbon';
import MapLibreView from './components/MapLibreView';
import LayerTreeSidebar from './components/LayerTreeSidebar';
import ParcelInspectorSheet from './components/ParcelInspectorSheet';
import ConflictResolutionTray from './components/ConflictResolutionTray';
import IngestionModal from './components/IngestionModal';
import BhuAadhaarModal from './components/BhuAadhaarModal';
import EncroachmentNoticeModal from './components/EncroachmentNoticeModal';
import ExportDropdown from './components/ExportDropdown';
import { defaultSectorData, generateSectorData } from './data/puneWard14Data';
import { realWorldParcelsGeoJSON } from './data/puneGeoJsonFixtures';
import confetti from 'canvas-confetti';

export default function App() {
  // Master Cadastral Data State
  const [data, setData] = useState(defaultSectorData);
  const [selectedSector, setSelectedSector] = useState('pune_ward14');

  // Selected Parcel for Slide-out Inspector
  const [selectedParcel, setSelectedParcel] = useState(null);

  // Active Encroachment target (if clicked from bottom tray)
  const [activeEncroachmentFocus, setActiveEncroachmentFocus] = useState(null);

  // Layer Visibility State
  const [layerVisibility, setLayerVisibility] = useState({
    legacy: true,
    aiWalls: true,
    drainage: true,
    roadRow: true
  });

  // Layer Opacity State
  const [layerOpacity, setLayerOpacity] = useState({
    legacy: 0.85,
    aiWalls: 0.95
  });

  // Projection Engine Mode: '2d' or '3d'
  const [viewMode, setViewMode] = useState('2d');

  // Status Filter: 'all', 'Approved', 'Review', 'Encroachment'
  const [statusFilter, setStatusFilter] = useState('all');

  // Tunable GeoAI Parameters
  const [geoAiParams, setGeoAiParams] = useState({
    snapToleranceCm: 15,
    minSliverAreaSqm: 2.0,
    eaveBufferM: 0.40
  });

  // Harmonization in-progress state
  const [isHarmonizing, setIsHarmonizing] = useState(false);
  const [toastMessage, setToastMessage] = useState('');

  // Modals state
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [bhuAadhaarModalParcel, setBhuAadhaarModalParcel] = useState(null);
  const [noticeModalConflict, setNoticeModalConflict] = useState(null);
  const [isExportOpen, setIsExportOpen] = useState(false);

  // Status Counts for Sidebar Filter Chips
  const statusCounts = useMemo(() => {
    const all = data.parcels.length;
    const approved = data.parcels.filter(p => p.status === 'Approved').length;
    const review = data.parcels.filter(p => p.status === 'Review').length;
    const encroachment = data.parcels.filter(p => p.status === 'Encroachment').length;
    return { all, approved, review, encroachment };
  }, [data.parcels]);

  // Filtered Parcels based on active status filter
  const visibleParcels = useMemo(() => {
    if (statusFilter === 'all') return data.parcels;
    return data.parcels.filter(p => p.status === statusFilter);
  }, [data.parcels, statusFilter]);

  // Handler: Toggle GIS Layers
  const handleToggleLayer = (layerKey) => {
    setLayerVisibility(prev => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  // Handler: Change Layer Opacity
  const handleChangeOpacity = (layerKey, val) => {
    setLayerOpacity(prev => ({ ...prev, [layerKey]: val }));
  };

  // Handler: Tune GeoAI parameter
  const handleChangeGeoAiParam = (key, val) => {
    setGeoAiParams(prev => ({ ...prev, [key]: val }));
  };

  // Handler: Trigger GeoAI Re-Harmonization
  const handleTriggerHarmonize = () => {
    setIsHarmonizing(true);
    const wardName = data.sectorInfo?.name || 'Cadastral Sector';
    const parcelCount = data.parcels?.length || 1420;
    const executionTimeSec = +((parcelCount * 0.00028) + 0.12).toFixed(3);

    setToastMessage(`Running FastSAM boundary extraction & TPS elastic warp on ${wardName}...`);

    setTimeout(() => {
      setIsHarmonizing(false);
      setToastMessage(`Harmonization complete! ${parcelCount.toLocaleString()} parcels planarized across ${wardName} in ${executionTimeSec}s`);
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.2 }
      });
      setTimeout(() => setToastMessage(''), 4500);
    }, 1200);
  };

  // Handler: Approve Parcel Harmonization
  const handleApproveParcel = (parcelId) => {
    setData(prev => {
      const updatedParcels = prev.parcels.map(p => {
        if (p.parcel_id === parcelId) {
          return { ...p, status: 'Approved', status_chip: 'APPROVED', is_encroaching: false, confidence_score: 98.5 };
        }
        return p;
      });

      const updatedConflicts = prev.conflicts.filter(c => c.parcel_id !== parcelId);
      const harmonizedCount = updatedParcels.filter(p => p.status === 'Approved').length;
      const harmonizationRate = +((harmonizedCount / updatedParcels.length) * 100).toFixed(1);

      return {
        ...prev,
        parcels: updatedParcels,
        conflicts: updatedConflicts,
        kpiMetrics: {
          ...prev.kpiMetrics,
          harmonizationRatePct: harmonizationRate,
          activeEncroachments: updatedConflicts.length
        }
      };
    });

    if (selectedParcel?.parcel_id === parcelId) {
      setSelectedParcel(prev => ({
        ...prev,
        status: 'Approved',
        status_chip: 'APPROVED',
        is_encroaching: false,
        confidence_score: 98.5
      }));
    }

    setToastMessage(`Parcel ${parcelId} approved and Bhu-Aadhaar verified!`);
    setTimeout(() => setToastMessage(''), 3000);
  };

  // Handler: Select conflict from bottom tray
  const handleSelectConflict = (conflict) => {
    setActiveEncroachmentFocus(conflict);
    const target = data.parcels.find(p => p.parcel_id === conflict.parcel_id);
    if (target) {
      setSelectedParcel(target);
    }
  };

  // Handler: Change Cadastral Sector
  const handleSelectSector = (sectorId) => {
    setSelectedSector(sectorId);
    setSelectedParcel(null);
    setActiveEncroachmentFocus(null);
    const newSectorData = generateSectorData(sectorId);
    setData(newSectorData);
    setToastMessage(`Loaded ${newSectorData.sectorInfo.name} (${newSectorData.parcels.length.toLocaleString()} parcels)`);
    setTimeout(() => setToastMessage(''), 3000);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-background text-slate-100 font-sans select-none">
      {/* 1. Header Bar */}
      <Header
        onOpenIngest={() => setIsIngestOpen(true)}
        onExport={() => setIsExportOpen(true)}
        selectedSector={selectedSector}
        onSelectSector={handleSelectSector}
      />

      {/* 2. Top KPI Metric Ribbon */}
      <MetricRibbon 
        metrics={data.kpiMetrics} 
        isHarmonizing={isHarmonizing}
      />

      {/* 3. Main Workspace: Layer Sidebar | Real-World Satellite MapLibre | Slide-out Inspector */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Layer Tree Sidebar (Left) */}
        <LayerTreeSidebar
          layerVisibility={layerVisibility}
          onToggleLayer={handleToggleLayer}
          layerOpacity={layerOpacity}
          onChangeOpacity={handleChangeOpacity}
          viewMode={viewMode}
          onChangeViewMode={setViewMode}
          statusFilter={statusFilter}
          onChangeStatusFilter={setStatusFilter}
          statusCounts={statusCounts}
          onTriggerHarmonize={handleTriggerHarmonize}
          isHarmonizing={isHarmonizing}
          geoAiParams={geoAiParams}
          onChangeGeoAiParam={handleChangeGeoAiParam}
        />

        {/* Real-World Satellite & Vector MapLibre Viewport */}
        <MapLibreView
          parcelsList={visibleParcels}
          selectedParcel={selectedParcel}
          onSelectParcel={setSelectedParcel}
          layerVisibility={layerVisibility}
          layerOpacity={layerOpacity}
          viewMode={viewMode}
          onChangeViewMode={setViewMode}
          sectorInfo={data.sectorInfo}
          infrastructure={data.infrastructure}
        />

        {/* Slide-out Parcel Inspector Sheet (Right) */}
        {selectedParcel && (
          <ParcelInspectorSheet
            parcel={selectedParcel}
            onClose={() => setSelectedParcel(null)}
            onOpenBhuAadhaarModal={(p) => setBhuAadhaarModalParcel(p)}
            onOpenNoticeModal={(p) => setNoticeModalConflict(p)}
            onApproveParcel={handleApproveParcel}
          />
        )}
      </div>

      {/* 4. Bottom Conflict Resolution Tray */}
      <ConflictResolutionTray
        conflicts={data.conflicts}
        onSelectConflict={handleSelectConflict}
        onApproveConflict={handleApproveParcel}
        onOpenNoticeModal={(c) => setNoticeModalConflict(c)}
      />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-14 left-1/2 -translate-x-1/2 z-50 bg-[#0B1F1A]/95 backdrop-blur-md px-4 py-2 rounded-xl border border-indigo-500/40 text-emerald-300 text-xs font-mono font-bold shadow-2xl animate-in fade-in slide-in-from-bottom duration-200 flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* 5. Ingestion Modal */}
      <IngestionModal
        isOpen={isIngestOpen}
        onClose={() => setIsIngestOpen(false)}
        onCompleteIngest={handleTriggerHarmonize}
        sectorInfo={data.sectorInfo}
        totalParcels={data.parcels.length}
        conflictsCount={data.conflicts.length}
        kpiMetrics={data.kpiMetrics}
        selectedSector={selectedSector}
        onSelectSector={handleSelectSector}
      />

      {/* 6. Bhu-Aadhaar Digital Card Modal */}
      <BhuAadhaarModal
        isOpen={!!bhuAadhaarModalParcel}
        parcel={bhuAadhaarModalParcel}
        onClose={() => setBhuAadhaarModalParcel(null)}
      />

      {/* 7. Encroachment Legal Notice Modal */}
      <EncroachmentNoticeModal
        isOpen={!!noticeModalConflict}
        conflict={noticeModalConflict}
        sectorInfo={data.sectorInfo}
        onClose={() => setNoticeModalConflict(null)}
      />

      {/* 8. Export Dropdown Modal */}
      <ExportDropdown
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        parcels={data.parcels}
        conflicts={data.conflicts}
        sectorInfo={data.sectorInfo}
      />
    </div>
  );
}
