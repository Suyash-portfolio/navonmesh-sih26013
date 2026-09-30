import React, { useState } from 'react';
import { X, Download, AlertTriangle, ShieldAlert, FileText, CheckCircle2, MapPin, Scale } from 'lucide-react';
import { generateEncroachmentNoticePDF } from '../utils/pdf-generator';

export default function EncroachmentNoticeModal({ isOpen, onClose, conflict, sectorInfo }) {
  const [isGenerating, setIsGenerating] = useState(false);

  if (!isOpen || !conflict) return null;

  const ownerName = conflict.owner_name || conflict.owner_en || 'Sanjay N. Jadhav';
  const ownerVernacular = conflict.owner_vernacular || '';
  const ulpin = conflict.ulpin || 'IN-MH-27-014-98214';
  const khasraNo = conflict.khasra_no || '170/7';
  const noticeId = conflict.id || (conflict.parcel_id ? `ENC-${String(conflict.parcel_id).replace(/[^0-9]/g, '').slice(-3).padStart(3, '0')}` : '001');
  const discrepancy = conflict.discrepancy_type || conflict.encroachment_type || 'Stormwater Drainage Canal Encroachment';
  const variance = conflict.variance_sqm || `+${conflict.encroached_area_sqm || 42.5} sq.m`;
  
  // Format Confidence accurately
  const confidenceScore = conflict.confidence !== undefined 
    ? (String(conflict.confidence).includes('%') ? conflict.confidence : `${conflict.confidence}%`)
    : (conflict.confidence_score !== undefined ? `${conflict.confidence_score}%` : '54.5%');

  // Format Centroid Coordinates
  const lat = conflict.centroid?.[1] ? conflict.centroid[1].toFixed(6) : (conflict.centroid?.[0] ? conflict.centroid[0].toFixed(6) : '18.520294');
  const lon = conflict.centroid?.[0] ? conflict.centroid[0].toFixed(6) : (conflict.centroid?.[1] ? conflict.centroid[1].toFixed(6) : '73.857345');

  const locationText = conflict.location || (sectorInfo ? `${sectorInfo.name} (${sectorInfo.taluk || sectorInfo.district} Taluk)` : 'Ward 14, Pune Urban Sector (Haveli Taluk)');

  const handleDownload = async () => {
    setIsGenerating(true);
    try {
      await generateEncroachmentNoticePDF({
        ...conflict,
        id: noticeId,
        owner_name: ownerName,
        owner_vernacular: ownerVernacular,
        ulpin,
        khasra_no: khasraNo,
        discrepancy_type: discrepancy,
        variance_sqm: variance,
        confidence: confidenceScore,
        location: locationText,
        centroid: [parseFloat(lon), parseFloat(lat)]
      }, sectorInfo);
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
      <div className="bg-[#0B1F1A] border border-rose-500/30 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="p-4 border-b border-rose-500/20 flex items-center justify-between bg-rose-950/40">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-outfit text-sm font-bold text-white flex items-center gap-2">
                Official Municipal Encroachment Notice
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  Section 248 MLRC
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Statutory directive for unauthorized public utility buffer infringement
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-rose-900/50 text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Notice Preview Body */}
        <div className="p-5 space-y-4 text-xs">
          <div className="p-3.5 bg-rose-950/20 border border-rose-500/20 rounded-xl space-y-1.5 font-mono text-[11px]">
            <div className="text-rose-400 font-bold tracking-wide">NOTICE REF: PMC/REV/ENC/2026/{noticeId}</div>
            <div className="text-slate-200">
              TO: <b className="text-white">{ownerName}</b> {ownerVernacular && <span className="text-slate-300 font-normal">({ownerVernacular})</span>}
            </div>
            <div className="text-slate-400 flex items-center gap-3">
              <span>ULPIN: <b className="text-slate-300">{ulpin}</b></span>
              <span>|</span>
              <span>Khasra: <b className="text-slate-300">{khasraNo}</b></span>
            </div>
            <div className="text-slate-400 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-rose-400" />
              <span>Location: {locationText}</span>
            </div>
          </div>

          <div className="space-y-2.5 text-slate-300 leading-relaxed bg-[#16362E]/40 p-4 rounded-xl border border-slate-700/50">
            <div className="text-xs font-bold text-white flex items-center gap-1.5">
              <Scale className="w-4 h-4 text-amber-400" />
              <span>STATUTORY VIOLATION SUMMARY:</span>
            </div>
            <p className="text-[11.5px] text-slate-300">
              Autonomous GeoAI drone surveillance (5cm GSD) and topological conflation have detected an unauthorized physical structure encroaching beyond legally registered boundaries:
            </p>
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 font-mono text-[11px] text-rose-200 space-y-1.5">
              <div className="flex items-start">
                <span className="text-rose-400 mr-1.5">•</span>
                <span>Violation: <b className="text-white">{discrepancy}</b></span>
              </div>
              <div className="flex items-start">
                <span className="text-rose-400 mr-1.5">•</span>
                <span>Measured Encroachment Area: <b className="text-rose-300">{variance}</b></span>
              </div>
              <div className="flex items-start">
                <span className="text-rose-400 mr-1.5">•</span>
                <span>Centroid: <b className="text-slate-200">{lat}° N, {lon}° E</b></span>
              </div>
              <div className="flex items-start">
                <span className="text-rose-400 mr-1.5">•</span>
                <span>AI Confidence: <b className="text-emerald-400">{confidenceScore}</b></span>
              </div>
            </div>
            <p className="text-[11px] text-slate-400 italic">
              You are required to show cause within 15 days or remove the structure, failing which summary municipal demolition will be executed.
            </p>
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end space-x-3 pt-2 border-t border-slate-800">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-[#16362E] hover:bg-[#1E4C40] text-slate-300 text-xs font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDownload}
              disabled={isGenerating}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 text-white text-xs font-bold shadow-lg shadow-rose-600/25 active:scale-95 transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{isGenerating ? 'Generating Notice...' : 'Export Official PDF Notice'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
