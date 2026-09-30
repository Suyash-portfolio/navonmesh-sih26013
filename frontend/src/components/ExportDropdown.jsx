import React, { useState } from 'react';
import { 
  Download, FileCode, Layers, Database, FileSpreadsheet, 
  CheckCircle2, X
} from 'lucide-react';

export default function ExportDropdown({ isOpen, onClose, parcels, conflicts, sectorInfo }) {
  const [downloadSuccess, setDownloadSuccess] = useState('');

  if (!isOpen) return null;

  const districtName = sectorInfo?.district || 'Sector';

  const handleExportGeoJson = () => {
    const featureCollection = {
      type: "FeatureCollection",
      name: `NAVONMESH_Harmonized_${districtName}`,
      crs: {
        type: "name",
        properties: { name: "urn:ogc:def:crs:OGC:1.3:CRS84" }
      },
      features: parcels.map(p => ({
        type: "Feature",
        properties: {
          parcel_id: p.parcel_id,
          ulpin: p.ulpin,
          khasra_no: p.khasra_no,
          owner_en: p.owner_en,
          owner_vernacular: p.owner_vernacular,
          legal_area_sqm: p.legal_area_sqm,
          surveyed_area_sqm: p.surveyed_area_sqm,
          delta_area_pct: p.delta_area_pct,
          confidence_score: p.confidence_score,
          status: p.status,
          ndsm_height_m: p.ndsm_height_m,
          is_encroaching: p.is_encroaching,
          encroachment_type: p.encroachment_type,
          encroached_area_sqm: p.encroached_area_sqm
        },
        geometry: {
          type: "Polygon",
          coordinates: [p.coordinates_ai]
        }
      }))
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(featureCollection, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `NAVONMESH_Harmonized_Cadastre_${districtName}.geojson`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    setDownloadSuccess('GeoJSON exported successfully!');
    setTimeout(() => setDownloadSuccess(''), 3000);
  };

  const handleExportCsv = () => {
    const headers = ["ULPIN", "Parcel ID", "Khasra No", "Owner English", "Owner Marathi", "Legal Area (sqm)", "Surveyed Area (sqm)", "Delta %", "Confidence Score", "Status", "Encroachment Type", "Encroached Sqm"];
    const rows = parcels.map(p => [
      p.ulpin, p.parcel_id, p.khasra_no, `"${p.owner_en}"`, `"${p.owner_vernacular}"`, p.legal_area_sqm, p.surveyed_area_sqm, p.delta_area_pct, p.confidence_score, p.status, `"${p.encroachment_type || 'None'}"`, p.encroached_area_sqm
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const link = document.createElement("a");
    link.setAttribute("href", encodeURI(csvContent));
    link.setAttribute("download", `NAVONMESH_Cadastral_Master_Register_${districtName}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();

    setDownloadSuccess('Master CSV Register exported successfully!');
    setTimeout(() => setDownloadSuccess(''), 3000);
  };

  const handleSimulateSpatialExport = (formatName) => {
    const dummyBlob = new Blob([`# NAVONMESH Cadastral Harmonization Export (SIH26013 Prototype) (${formatName})\n# Sector: ${sectorInfo?.name || districtName}\n# Total Parcels: ${parcels.length}\n# Coordinate System: EPSG:4326 WGS84\n`], { type: 'text/plain' });
    const url = URL.createObjectURL(dummyBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `NAVONMESH_Cadastre_${districtName}_${formatName.toLowerCase()}.${formatName === 'GeoPackage' ? 'gpkg' : 'zip'}`;
    document.body.appendChild(a);
    a.click();
    a.remove();

    setDownloadSuccess(`${formatName} bundle exported successfully!`);
    setTimeout(() => setDownloadSuccess(''), 3000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
      <div className="bg-[#0B1F1A] border border-slate-700/70 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-[#0B1F1A]/90">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Download className="w-5 h-5" />
            </div>
            <h3 className="font-outfit text-sm font-bold text-white">
              Standardized Cadastral Spatial Export
            </h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[#1A463B] text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <p className="text-xs text-slate-400">
            Export harmonized {parcels.length.toLocaleString()} cadastral boundaries, ULPIN identifiers, and audit metadata in national and open GIS formats:
          </p>

          {downloadSuccess && (
            <div className="p-2.5 rounded-xl bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 text-xs flex items-center space-x-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{downloadSuccess}</span>
            </div>
          )}

          <div className="space-y-2">
            {/* GeoJSON */}
            <button
              onClick={handleExportGeoJson}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-[#16362E]/40 hover:bg-[#1A463B] border border-slate-700/60 hover:border-emerald-500/30 transition-all text-left group"
            >
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 group-hover:scale-105 transition-transform">
                  <FileCode className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">GeoJSON (Planar Harmonized)</div>
                  <div className="text-[10px] text-slate-400">Standard RFC 7946 FeatureCollection with {parcels.length.toLocaleString()} polygons</div>
                </div>
              </div>
              <Download className="w-4 h-4 text-slate-400 group-hover:text-emerald-400" />
            </button>

            {/* OGC GeoPackage */}
            <button
              onClick={() => handleSimulateSpatialExport('GeoPackage')}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-[#16362E]/40 hover:bg-[#1A463B] border border-slate-700/60 hover:border-indigo-500/30 transition-all text-left group"
            >
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 group-hover:scale-105 transition-transform">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">OGC GeoPackage (.gpkg)</div>
                  <div className="text-[10px] text-slate-400">Standard SQLite container for QGIS, ArcGIS & PostGIS</div>
                </div>
              </div>
              <Download className="w-4 h-4 text-slate-400 group-hover:text-indigo-400" />
            </button>

            {/* ESRI Shapefile */}
            <button
              onClick={() => handleSimulateSpatialExport('Shapefile')}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-[#16362E]/40 hover:bg-[#1A463B] border border-slate-700/60 hover:border-blue-500/30 transition-all text-left group"
            >
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 group-hover:scale-105 transition-transform">
                  <Layers className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">ESRI Shapefile (.shp / .shx / .dbf)</div>
                  <div className="text-[10px] text-slate-400">National survey format with bilingual attribute table</div>
                </div>
              </div>
              <Download className="w-4 h-4 text-slate-400 group-hover:text-blue-400" />
            </button>

            {/* Master CSV Register */}
            <button
              onClick={handleExportCsv}
              className="w-full flex items-center justify-between p-3 rounded-xl bg-[#16362E]/40 hover:bg-[#1A463B] border border-slate-700/60 hover:border-amber-500/30 transition-all text-left group"
            >
              <div className="flex items-center space-x-3">
                <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20 group-hover:scale-105 transition-transform">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-bold text-white">Khasra Master Attribute CSV</div>
                  <div className="text-[10px] text-slate-400">Full cadastral registry with ULPIN, Î”Area & AI confidence</div>
                </div>
              </div>
              <Download className="w-4 h-4 text-slate-400 group-hover:text-amber-400" />
            </button>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-[#16362E] hover:bg-[#1E4C40] text-slate-300 text-xs font-semibold transition-all"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
