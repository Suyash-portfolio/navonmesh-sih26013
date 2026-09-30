import React, { useState } from 'react';
import { 
  X, Upload, FileText, CheckCircle2, Cpu, Sparkles, 
  Layers, Database, ArrowRight, ShieldCheck, Check,
  Zap, FolderOpen, ClipboardList, MapPin, RefreshCw
} from 'lucide-react';
import confetti from 'canvas-confetti';

const PRESET_SECTORS = [
  {
    id: 'pune_ward14',
    name: 'Ward 14, Pune Urban',
    district: 'Pune',
    taluk: 'Haveli',
    parcels: 1420,
    conflicts: 34,
    density: 'High-Density Urban Core',
    icon: '🏙️',
    files: {
      drone: 'Pune_Ward14_5cm_ORI_Orthomosaic.tif (1.8 GB)',
      legacy: 'Shajra_Cadastral_Vectors_Pune.shp (14.2 MB)',
      khasra: 'Pune_RoR_Khasra_Registry_2026.csv (2.4 MB)',
      elevation: 'Pune_LiDAR_DSM_DTM_Pointcloud.las (840 MB)'
    }
  },
  {
    id: 'nagpur_sec3',
    name: 'Ward 03, Nagpur Peri-Urban',
    district: 'Nagpur',
    taluk: 'Nagpur Urban',
    parcels: 980,
    conflicts: 18,
    density: 'Peri-Urban Agricultural Fringe',
    icon: '🌾',
    files: {
      drone: 'Nagpur_Sec3_5cm_ORI_Orthomosaic.tif (1.2 GB)',
      legacy: 'Shajra_Cadastral_Vectors_Nagpur.shp (9.8 MB)',
      khasra: 'Nagpur_RoR_Khasra_Registry_2026.csv (1.6 MB)',
      elevation: 'Nagpur_LiDAR_DSM_DTM_Pointcloud.las (620 MB)'
    }
  },
  {
    id: 'thane_sec8',
    name: 'Ward 08, Thane Metropolitan',
    district: 'Thane',
    taluk: 'Thane',
    parcels: 2150,
    conflicts: 62,
    density: 'Ultra-Dense Metro Corridors',
    icon: '🏢',
    files: {
      drone: 'Thane_Sec8_5cm_ORI_Orthomosaic.tif (2.4 GB)',
      legacy: 'Shajra_Cadastral_Vectors_Thane.shp (18.6 MB)',
      khasra: 'Thane_RoR_Khasra_Registry_2026.csv (3.1 MB)',
      elevation: 'Thane_LiDAR_DSM_DTM_Pointcloud.las (1.1 GB)'
    }
  }
];

export default function IngestionModal({ 
  isOpen, 
  onClose, 
  onCompleteIngest, 
  sectorInfo, 
  totalParcels = 1420, 
  conflictsCount = 34, 
  kpiMetrics,
  selectedSector = 'pune_ward14',
  onSelectSector
}) {
  const [tab, setTab] = useState('presets'); // 'presets' | 'upload' | 'paste'
  const [stage, setStage] = useState('upload'); // 'upload' | 'processing' | 'done'
  const [activeStep, setActiveStep] = useState(0);
  const [activePreset, setActivePreset] = useState(selectedSector || 'pune_ward14');

  // Custom uploaded files state
  const [customFiles, setCustomFiles] = useState({
    drone: `${sectorInfo?.district || 'Sector'}_5cm_ORI_Orthomosaic.tif (1.8 GB)`,
    legacy: `Shajra_Cadastral_Vectors_${sectorInfo?.district || 'Revenue'}.shp (14.2 MB)`,
    khasra: `${sectorInfo?.district || 'State'}_RoR_Khasra_Registry_2026.csv (2.4 MB)`,
    elevation: `${sectorInfo?.district || 'Sector'}_LiDAR_DSM_DTM_Pointcloud.las (840 MB)`
  });

  // Raw GeoJSON / CSV paste state
  const [pastedData, setPastedData] = useState('');
  const [pasteType, setPasteType] = useState('geojson');

  if (!isOpen) return null;

  const currentSectorObj = PRESET_SECTORS.find(s => s.id === activePreset) || PRESET_SECTORS[0];
  const wardName = currentSectorObj.name;
  const activeParcelsCount = currentSectorObj.parcels;
  const activeDisputesCount = currentSectorObj.conflicts;
  const executionTimeSec = +((activeParcelsCount * 0.00028) + 0.12).toFixed(3);

  const pipelineSteps = [
    { title: "1. Deep Keypoint Matching", desc: "SuperPoint + SIFT invariant landmark extraction with TPS elastic homography warping", time: "0.8s" },
    { title: "2. Zero-Shot Physical Segmentation", desc: "SAM-2 boundary segmentation with automated nDSM eave contraction (0.4m)", time: "1.2s" },
    { title: "3. Topological Conflation & Planarization", desc: "Vertex snap-rounding (ε=15cm), sliver elimination (<2.0m²), 0 overlaps enforced", time: "0.6s" },
    { title: "4. Multilingual Semantic Attribute Linkage", desc: "IndicSoundex phonetic tokenization + Levenshtein distance across Devanagari records", time: "0.5s" },
    { title: "5. Bhu-Aadhaar (ULPIN) Minting", desc: `Generating ${activeParcelsCount.toLocaleString()} ISO 19152 compliant 14-char ULPINs & cryptographic QR hashes`, time: "0.4s" }
  ];

  const handleSelectPresetCard = (presetId) => {
    setActivePreset(presetId);
    if (onSelectSector) {
      onSelectSector(presetId);
    }
  };

  const handleFileUpload = (channel, e) => {
    const file = e.target.files?.[0];
    if (file) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
      setCustomFiles(prev => ({
        ...prev,
        [channel]: `${file.name} (${sizeMB} MB)`
      }));
    }
  };

  const handleLoadSamplePaste = () => {
    if (pasteType === 'geojson') {
      setPastedData(JSON.stringify({
        type: "FeatureCollection",
        name: `Cadastral_${currentSectorObj.district}`,
        features: [
          {
            type: "Feature",
            properties: { khasra_no: "101/1", owner_name: "Sanjay D. Kulkarni", legal_area_sqm: 320.5 },
            geometry: { type: "Polygon", coordinates: [[[73.856, 18.520], [73.858, 18.520], [73.858, 18.522], [73.856, 18.522], [73.856, 18.520]]] }
          }
        ]
      }, null, 2));
    } else {
      setPastedData(
`khasra_no,owner_en,owner_vernacular,legal_area_sqm
101/1,Sanjay D. Kulkarni,संजय दत्तात्रय कुलकर्णी,320.5
102/2,Anita S. Patil,अनिता सुरेश पाटील,285.0
103/3,Ganesh M. Jadhav,गणेश महादेव जाधव,410.2`
      );
    }
  };

  const handleStartProcessing = () => {
    setStage('processing');
    setActiveStep(0);

    // Simulate real-time progress steps
    const interval = setInterval(() => {
      setActiveStep(prev => {
        if (prev < pipelineSteps.length - 1) {
          return prev + 1;
        } else {
          clearInterval(interval);
          setStage('done');
          confetti({
            particleCount: 80,
            spread: 70,
            origin: { y: 0.6 }
          });
          return prev;
        }
      });
    }, 700);
  };

  const handleFinish = () => {
    if (onCompleteIngest) {
      onCompleteIngest();
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
      <div className="bg-[#0B1F1A] border border-slate-700/70 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-[#0B1F1A]/90">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-outfit text-sm font-bold text-white flex items-center gap-2">
                Multi-Source Ingestion & GeoAI Engine
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono">
                  Ready
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Easily insert or select cadastral datasets for automated spatial conflation
              </p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-1.5 rounded-lg hover:bg-[#1A463B] text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content based on stage */}
        <div className="p-5">
          {stage === 'upload' && (
            <div className="space-y-4">
              {/* Tab Navigation */}
              <div className="flex items-center space-x-1 p-1 bg-[#16362E]/50 rounded-xl border border-slate-700/50">
                <button
                  onClick={() => setTab('presets')}
                  className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all ${
                    tab === 'presets'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#1A463B]'
                  }`}
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>1-Click Presets</span>
                </button>

                <button
                  onClick={() => setTab('upload')}
                  className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all ${
                    tab === 'upload'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#1A463B]'
                  }`}
                >
                  <FolderOpen className="w-3.5 h-3.5" />
                  <span>Upload Files</span>
                </button>

                <button
                  onClick={() => setTab('paste')}
                  className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1.5 transition-all ${
                    tab === 'paste'
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#1A463B]'
                  }`}
                >
                  <ClipboardList className="w-3.5 h-3.5" />
                  <span>Paste Data</span>
                </button>
              </div>

              {/* TAB 1: Quick 1-Click Preset Selection */}
              {tab === 'presets' && (
                <div className="space-y-2.5">
                  <div className="text-[11px] text-slate-400">
                    Select a pre-configured multi-source cadastral sector to ingest instantly:
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                    {PRESET_SECTORS.map((preset) => {
                      const isSelected = activePreset === preset.id;
                      return (
                        <div
                          key={preset.id}
                          onClick={() => handleSelectPresetCard(preset.id)}
                          className={`cursor-pointer rounded-xl p-3 border transition-all relative ${
                            isSelected
                              ? 'bg-indigo-950/40 border-indigo-400 shadow-lg shadow-indigo-500/10 ring-1 ring-indigo-400/30'
                              : 'bg-[#16362E]/40 border-slate-700/60 hover:border-slate-600 hover:bg-[#1A463B]/70'
                          }`}
                        >
                          {isSelected && (
                            <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-indigo-500 text-white flex items-center justify-center text-[10px] font-bold shadow">
                              ✓
                            </div>
                          )}
                          <div className="text-xl mb-1">{preset.icon}</div>
                          <div className="text-xs font-bold text-white truncate">{preset.name}</div>
                          <div className="text-[10px] text-indigo-300 font-mono mt-0.5">{preset.density}</div>
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 mt-2 pt-1.5 border-t border-slate-700/50">
                            <span>{preset.parcels.toLocaleString()} Parcels</span>
                            <span className="text-rose-400">{preset.conflicts} Disputes</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Summary of Active Preset Files */}
                  <div className="p-3 bg-[#16362E]/30 rounded-xl border border-slate-700/50 space-y-1.5">
                    <div className="text-[10px] font-mono uppercase text-slate-400 font-semibold flex items-center justify-between">
                      <span>Loaded Channels for {currentSectorObj.name}</span>
                      <span className="text-emerald-400">● 4/4 Verified</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                      <div className="flex items-center space-x-1.5 text-indigo-300 truncate">
                        <Layers className="w-3 h-3 shrink-0" />
                        <span className="truncate">{currentSectorObj.files.drone}</span>
                      </div>
                      <div className="flex items-center space-x-1.5 text-blue-300 truncate">
                        <FileText className="w-3 h-3 shrink-0" />
                        <span className="truncate">{currentSectorObj.files.legacy}</span>
                      </div>
                      <div className="flex items-center space-x-1.5 text-emerald-300 truncate">
                        <Database className="w-3 h-3 shrink-0" />
                        <span className="truncate">{currentSectorObj.files.khasra}</span>
                      </div>
                      <div className="flex items-center space-x-1.5 text-amber-300 truncate">
                        <Cpu className="w-3 h-3 shrink-0" />
                        <span className="truncate">{currentSectorObj.files.elevation}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: Upload Custom Files */}
              {tab === 'upload' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2.5">
                    {/* Drone File */}
                    <div className="p-2.5 rounded-xl bg-[#16362E]/40 border border-indigo-500/20 flex items-center justify-between">
                      <div className="flex items-center space-x-2 truncate">
                        <Layers className="w-4 h-4 text-indigo-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-[11px] font-semibold text-white">Drone Orthomosaic (5cm)</div>
                          <div className="text-[9px] text-indigo-300 font-mono truncate">{customFiles.drone}</div>
                        </div>
                      </div>
                      <label className="cursor-pointer px-2.5 py-1 bg-[#16362E] hover:bg-[#1E4C40] text-indigo-300 rounded-lg text-[10px] font-medium border border-slate-700 shrink-0">
                        Browse
                        <input type="file" accept=".tif,.tiff,.cog" className="hidden" onChange={(e) => handleFileUpload('drone', e)} />
                      </label>
                    </div>

                    {/* Legacy Shajra File */}
                    <div className="p-2.5 rounded-xl bg-[#16362E]/40 border border-blue-500/20 flex items-center justify-between">
                      <div className="flex items-center space-x-2 truncate">
                        <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-[11px] font-semibold text-white">Legacy Cadastre (Shajra)</div>
                          <div className="text-[9px] text-blue-300 font-mono truncate">{customFiles.legacy}</div>
                        </div>
                      </div>
                      <label className="cursor-pointer px-2.5 py-1 bg-[#16362E] hover:bg-[#1E4C40] text-blue-300 rounded-lg text-[10px] font-medium border border-slate-700 shrink-0">
                        Browse
                        <input type="file" accept=".shp,.geojson,.json,.dxf" className="hidden" onChange={(e) => handleFileUpload('legacy', e)} />
                      </label>
                    </div>

                    {/* Khasra CSV */}
                    <div className="p-2.5 rounded-xl bg-[#16362E]/40 border border-emerald-500/20 flex items-center justify-between">
                      <div className="flex items-center space-x-2 truncate">
                        <Database className="w-4 h-4 text-emerald-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-[11px] font-semibold text-white">Khasra Title Registry</div>
                          <div className="text-[9px] text-emerald-300 font-mono truncate">{customFiles.khasra}</div>
                        </div>
                      </div>
                      <label className="cursor-pointer px-2.5 py-1 bg-[#16362E] hover:bg-[#1E4C40] text-emerald-300 rounded-lg text-[10px] font-medium border border-slate-700 shrink-0">
                        Browse
                        <input type="file" accept=".csv,.xlsx,.tsv" className="hidden" onChange={(e) => handleFileUpload('khasra', e)} />
                      </label>
                    </div>

                    {/* Elevation Surface Model */}
                    <div className="p-2.5 rounded-xl bg-[#16362E]/40 border border-amber-500/20 flex items-center justify-between">
                      <div className="flex items-center space-x-2 truncate">
                        <Cpu className="w-4 h-4 text-amber-400 shrink-0" />
                        <div className="truncate">
                          <div className="text-[11px] font-semibold text-white">Elevation Surface Model</div>
                          <div className="text-[9px] text-amber-300 font-mono truncate">{customFiles.elevation}</div>
                        </div>
                      </div>
                      <label className="cursor-pointer px-2.5 py-1 bg-[#16362E] hover:bg-[#1E4C40] text-amber-300 rounded-lg text-[10px] font-medium border border-slate-700 shrink-0">
                        Browse
                        <input type="file" accept=".las,.laz,.tif" className="hidden" onChange={(e) => handleFileUpload('elevation', e)} />
                      </label>
                    </div>
                  </div>

                  <div className="border border-dashed border-slate-700 hover:border-indigo-400 rounded-xl p-4 text-center cursor-pointer bg-[#16362E]/20 transition-colors">
                    <Upload className="w-5 h-5 text-slate-400 mx-auto mb-1" />
                    <div className="text-xs text-slate-300 font-medium">Or drag & drop any spatial package (.zip, .shp, .geojson, .tif) here</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Supports automated multi-layer package extraction</div>
                  </div>
                </div>
              )}

              {/* TAB 3: Direct Data Paste */}
              {tab === 'paste' && (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setPasteType('geojson')}
                        className={`text-xs px-2.5 py-1 rounded-lg font-semibold ${
                          pasteType === 'geojson' ? 'bg-indigo-600 text-white' : 'bg-[#16362E] text-slate-400'
                        }`}
                      >
                        GeoJSON
                      </button>
                      <button
                        onClick={() => setPasteType('csv')}
                        className={`text-xs px-2.5 py-1 rounded-lg font-semibold ${
                          pasteType === 'csv' ? 'bg-indigo-600 text-white' : 'bg-[#16362E] text-slate-400'
                        }`}
                      >
                        Khasra CSV
                      </button>
                    </div>
                    <button
                      onClick={handleLoadSamplePaste}
                      className="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Insert Sample Template</span>
                    </button>
                  </div>

                  <textarea
                    rows={6}
                    placeholder={pasteType === 'geojson' ? 'Paste raw GeoJSON FeatureCollection here...' : 'Paste Khasra CSV lines here (khasra_no,owner_name,area)...'}
                    value={pastedData}
                    onChange={(e) => setPastedData(e.target.value)}
                    className="w-full bg-[#16362E]/50 border border-slate-700/60 rounded-xl p-3 text-xs font-mono text-indigo-200 placeholder-slate-500 focus:outline-none focus:border-indigo-400"
                  />
                </div>
              )}

              {/* Bottom Execution Bar */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-800">
                <div className="flex items-center space-x-2">
                  <MapPin className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-mono text-slate-300 font-semibold">
                    {wardName} <span className="text-slate-500 font-normal">({activeParcelsCount.toLocaleString()} Parcels)</span>
                  </span>
                </div>

                <button
                  onClick={handleStartProcessing}
                  className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/25 active:scale-95 transition-all"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Execute GeoAI Harmonization Pipeline</span>
                </button>
              </div>
            </div>
          )}

          {stage === 'processing' && (
            <div className="space-y-4">
              <div className="text-center py-2">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 mb-2 animate-bounce">
                  <Sparkles className="w-6 h-6 animate-spin" />
                </div>
                <h4 className="font-outfit text-sm font-bold text-white">
                  Executing 5-Stage Autonomous GeoAI Pipeline
                </h4>
                <p className="text-[11px] text-slate-400">
                  Processing {activeParcelsCount.toLocaleString()} cadastral parcels across {wardName}
                </p>
              </div>

              {/* Stepper Progress */}
              <div className="space-y-2.5 bg-[#16362E]/40 p-3.5 rounded-xl border border-slate-700/50">
                {pipelineSteps.map((step, idx) => {
                  const isDone = idx < activeStep;
                  const isCurrent = idx === activeStep;
                  return (
                    <div 
                      key={idx} 
                      className={`flex items-start space-x-3 p-2 rounded-lg transition-all ${
                        isCurrent ? 'bg-indigo-950/40 border border-indigo-500/30' : 'opacity-70'
                      }`}
                    >
                      <div className="mt-0.5">
                        {isDone ? (
                          <div className="w-5 h-5 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold">
                            ✓
                          </div>
                        ) : isCurrent ? (
                          <div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin"></div>
                        ) : (
                          <div className="w-5 h-5 rounded-full bg-slate-700 text-slate-400 flex items-center justify-center text-[10px] font-mono">
                            {idx + 1}
                          </div>
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <span className={`text-xs font-bold ${isCurrent ? 'text-indigo-300' : isDone ? 'text-emerald-400' : 'text-slate-300'}`}>
                            {step.title}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">{step.time}</span>
                        </div>
                        <p className="text-[10px] text-slate-400">{step.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {stage === 'done' && (
            <div className="text-center py-4 space-y-4">
              <div className="w-14 h-14 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 mx-auto flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8" />
              </div>

              <div>
                <h4 className="font-outfit text-base font-bold text-white">
                  {wardName} Successfully Harmonized!
                </h4>
                <p className="text-xs text-slate-400 max-w-md mx-auto mt-1">
                  {activeParcelsCount.toLocaleString()} parcels co-registered with millimeter-precision TPS warping. {activeDisputesCount} encroachment disputes flagged with Section 248 legal notices ready.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3 p-3 bg-[#16362E]/40 rounded-xl border border-slate-700/50 max-w-lg mx-auto text-center font-mono">
                <div>
                  <div className="text-[10px] text-slate-400">Total Parcels</div>
                  <div className="text-sm font-bold text-white">{activeParcelsCount.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Execution Time</div>
                  <div className="text-sm font-bold text-emerald-400">{executionTimeSec} s</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400">Mean Confidence</div>
                  <div className="text-sm font-bold text-indigo-300">{kpiMetrics?.avgConfidencePct || 94.8}%</div>
                </div>
              </div>

              <button
                onClick={handleFinish}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/25 transition-all active:scale-95"
              >
                Launch Harmonized Split-Screen Canvas
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
