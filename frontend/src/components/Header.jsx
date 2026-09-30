import React from 'react';
import { Upload, Download, MapPin } from 'lucide-react';
import NavonmeshLogo from './NavonmeshLogo';

export default function Header({ 
  onOpenIngest, 
  onExport,
  selectedSector,
  onSelectSector 
}) {
  return (
    <header className="h-16 bg-surface border-b border-surface-border flex items-center justify-between gap-3 px-4 sm:px-5 z-30 select-none">
      {/* Left: Emblem & Platform Brand */}
      <div className="flex items-center space-x-3 min-w-0">
        {/* Container dimensions unchanged (w-10 h-10) so the layout does not shift */}
        <div className="w-10 h-10 shrink-0 rounded-xl bg-gradient-to-tr from-emerald-500 via-teal-600 to-teal-400 p-0.5 shadow-md shadow-emerald-500/10 flex items-center justify-center">
          <div className="w-full h-full bg-[#0B1F1A] rounded-[10px] flex items-center justify-center">
            <NavonmeshLogo className="w-5 h-5" />
          </div>
        </div>
        
        <div className="min-w-0">
          <div className="flex items-center space-x-2.5">
            <h1 className="font-outfit text-base sm:text-lg font-extrabold tracking-[0.18em] text-white flex items-center leading-none">
              <span className="hidden sm:inline text-[10px] font-mono font-semibold tracking-[0.2em] text-slate-400 mr-2">
                PROJECT
              </span>
              <span className="text-emerald-400">NAVONMESH</span>
            </h1>
            <span className="hidden md:inline-flex text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 items-center space-x-1 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              DoLR • NAKSHA
            </span>
          </div>
          <p className="text-[11px] text-slate-400 -mt-0.5 truncate">
            Intelligent Multi-Source Geospatial Harmonization Platform
          </p>
        </div>
      </div>

      {/* Center: Sector Selector */}
      <div className="flex items-center space-x-3 shrink-0 hidden md:flex">
        <div className="flex items-center bg-surface-raised/80 hover:bg-surface-raised border border-surface-border rounded-xl px-3.5 py-1.5 shadow-sm transition-all">
          <MapPin className="w-4 h-4 text-teal-400 mr-2 shrink-0" />
          <div className="flex flex-col text-left">
            <span className="text-[9px] uppercase font-mono font-semibold tracking-wider text-slate-400">Cadastral Sector</span>
            <select 
              value={selectedSector}
              onChange={(e) => onSelectSector(e.target.value)}
              className="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer pr-3 -ml-0.5"
            >
              <option value="pune_ward14" className="bg-[#0B1F1A] text-white">Ward 14, Pune Urban Sector (1,420 Parcels)</option>
              <option value="nagpur_sec3" className="bg-[#0B1F1A] text-white">Ward 03, Nagpur Peri-Urban (980 Parcels)</option>
              <option value="thane_sec8" className="bg-[#0B1F1A] text-white">Ward 08, Thane Metropolitan (2,150 Parcels)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center space-x-2.5 shrink-0">
        <button
          onClick={onOpenIngest}
          className="flex items-center space-x-1.5 text-xs font-semibold px-3 sm:px-3.5 py-2 rounded-xl bg-surface-raised hover:bg-[#1A463B] border border-surface-border text-slate-200 hover:text-white transition-all shadow-sm active:scale-95"
          title="Drag and Drop GeoTIFF / Shapefiles / Khasra CSV"
        >
          <Upload className="w-3.5 h-3.5 text-teal-400" />
          <span className="hidden sm:inline">Ingest Data</span>
        </button>

        <button
          onClick={onExport}
          className="flex items-center space-x-1.5 text-xs font-semibold px-3 sm:px-3.5 py-2 rounded-xl bg-surface-raised hover:bg-[#1A463B] border border-surface-border text-slate-200 hover:text-white transition-all shadow-sm active:scale-95"
          title="Export GeoPackage, Shapefile, GeoJSON & Bhu-Aadhaar PDFs"
        >
          <Download className="w-3.5 h-3.5 text-emerald-400" />
          <span>Export</span>
        </button>
      </div>
    </header>
  );
}

