import React, { useState } from 'react';
import {
  X, FileText, AlertTriangle, CheckCircle2,
  Copy, Check, Download, QrCode, Building
} from 'lucide-react';
import { generateBhuAadhaarPDF } from '../utils/pdf-generator';

export default function ParcelInspectorSheet({
  parcel,
  onClose,
  onOpenBhuAadhaarModal,
  onOpenNoticeModal,
  onApproveParcel
}) {
  const [copied, setCopied] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  if (!parcel) return null;

  const handleCopyUlpin = () => {
    navigator.clipboard.writeText(parcel.ulpin);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadPdf = async () => {
    setIsGeneratingPdf(true);
    try {
      await generateBhuAadhaarPDF(parcel);
    } catch (err) {
      console.error("PDF generation error:", err);
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const isApproved = parcel.status === 'Approved';
  const isEncroaching = !!(parcel.is_encroaching || parcel.status === 'Encroachment');

  return (
    <aside className="w-96 h-full bg-surface/95 border-l border-surface-border flex flex-col z-20 shadow-2xl backdrop-blur-xl animate-in slide-in-from-right duration-200 select-none">
      {/* Header */}
      <div className="p-4 border-b border-surface-border flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="p-1 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <FileText className="w-4 h-4" />
          </div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
            Bhu-Aadhaar Inspector
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg hover:bg-[#1A463B] text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* ULPIN Badge Card */}
        <div className="gis-glass-card rounded-xl p-3.5 border border-indigo-500/25 bg-gradient-to-b from-indigo-950/20 to-surface">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase text-slate-400 mb-1">
            <span>Bhu-Aadhaar Number (ULPIN)</span>
            <span className={`px-2 py-0.5 rounded-full font-bold text-[9px] ${
              isEncroaching 
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' 
                : parcel.status === 'Review'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
            }`}>
              {isEncroaching ? 'DISPUTED' : parcel.status_chip || parcel.status}
            </span>
          </div>

          <div className="flex items-center justify-between mt-1">
            <span className="font-mono text-sm font-bold text-white tracking-wider">
              {parcel.ulpin}
            </span>
            <button
              onClick={handleCopyUlpin}
              className="p-1.5 rounded-md bg-surface-raised hover:bg-[#1E4C40] text-slate-400 hover:text-white transition-all"
              title="Copy ULPIN"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Ownership & Multilingual Record */}
        <div className="gis-glass-card rounded-xl p-3.5 space-y-2 border border-surface-border">
          <div className="text-[10px] font-mono uppercase text-slate-400 font-semibold">
            Land Title & Registry
          </div>

          <div>
            <div className="text-[11px] text-slate-400">Registered Owner (English)</div>
            <div className="text-xs font-bold text-white">{parcel.owner_en || parcel.owner_name}</div>
          </div>

          <div>
            <div className="text-[11px] text-slate-400">Vernacular RoR Record (Marathi)</div>
            <div className="text-xs font-semibold text-emerald-300 font-sans">{parcel.owner_vernacular}</div>
          </div>

          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-surface-border/50 text-[11px]">
            <div>
              <span className="text-slate-400">Khasra No:</span>
              <div className="font-mono font-bold text-slate-200">{parcel.khasra_no}</div>
            </div>
            <div>
              <span className="text-slate-400">Parcel ID:</span>
              <div className="font-mono font-bold text-slate-200">{parcel.parcel_id}</div>
            </div>
          </div>
        </div>

        {/* Legal vs Surveyed Area Delta Bar Chart */}
        <div className="gis-glass-card rounded-xl p-3.5 space-y-2.5 border border-surface-border">
          <div className="flex items-center justify-between text-[10px] font-mono uppercase text-slate-400 font-semibold">
            <span>Area Harmonization Delta</span>
            <span className={`font-bold font-mono ${isEncroaching ? 'text-rose-400' : parcel.area_diff_sqm >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
              Δ {parcel.delta_area_pct}% ({parcel.area_diff_sqm >= 0 ? '+' : ''}{parcel.area_diff_sqm} m²)
            </span>
          </div>

          {/* Comparative visual bar */}
          {(() => {
            const maxVal = Math.max(parcel.legal_area_sqm || 1, parcel.surveyed_area_sqm || 1);
            const legalWidth = `${Math.min(100, Math.max(15, ((parcel.legal_area_sqm || 0) / maxVal) * 96)).toFixed(1)}%`;
            const surveyedWidth = `${Math.min(100, Math.max(15, ((parcel.surveyed_area_sqm || 0) / maxVal) * 96)).toFixed(1)}%`;
            return (
              <div className="space-y-1.5 text-[11px]">
                <div>
                  <div className="flex justify-between text-slate-400 text-[10px] mb-0.5">
                    <span>Legal RoR Area</span>
                    <span className="font-mono text-slate-200 font-bold">{parcel.legal_area_sqm} m²</span>
                  </div>
                  <div className="w-full h-2 bg-[#16362E] rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: legalWidth }}></div>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-slate-400 text-[10px] mb-0.5">
                    <span>Surveyed 5cm Ground Truth</span>
                    <span className={`font-mono font-bold ${isEncroaching ? 'text-rose-400' : 'text-emerald-300'}`}>
                      {parcel.surveyed_area_sqm} m²
                    </span>
                  </div>
                  <div className="w-full h-2 bg-[#16362E] rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${isEncroaching ? 'bg-rose-500' : 'bg-emerald-400'}`}
                      style={{ width: surveyedWidth }}
                    ></div>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* AI Confidence Formula Breakdown */}
        <div className="gis-glass-card rounded-xl p-3.5 space-y-2 border border-surface-border">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase text-slate-400 font-semibold">
              GeoAI Confidence Score
            </span>
            <span className={`text-sm font-mono font-bold ${
              isEncroaching ? 'text-rose-400' : parcel.confidence_score >= 90 ? 'text-emerald-400' : 'text-amber-400'
            }`}>
              {parcel.confidence_score}%
            </span>
          </div>

          <div className="w-full h-2 bg-[#16362E] rounded-full overflow-hidden">
            <div 
              className={`h-full rounded-full ${
                isEncroaching
                  ? 'bg-rose-500'
                  : parcel.confidence_score >= 90 
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-400' 
                  : 'bg-amber-500'
              }`}
              style={{ width: `${parcel.confidence_score}%` }}
            ></div>
          </div>

          {/* Exact Formula Breakdown items */}
          <div className="grid grid-cols-2 gap-1.5 pt-2 text-[10px] font-mono text-slate-400">
            <div className="p-1.5 bg-surface rounded-lg border border-surface-border">
              <div>IoU Weight (40%)</div>
              <div className="text-white font-bold">{isEncroaching ? '64.2%' : `${parcel.iou_pct || 96.2}%`}</div>
            </div>
            <div className="p-1.5 bg-surface rounded-lg border border-surface-border">
              <div>Area Delta (35%)</div>
              <div className="text-white font-bold">{parcel.delta_area_pct}%</div>
            </div>
            <div className="p-1.5 bg-surface rounded-lg border border-surface-border">
              <div>Topology (15%)</div>
              <div className={`font-bold ${isEncroaching ? 'text-rose-400' : 'text-emerald-400'}`}>
                {isEncroaching ? 'Buffer Overlap' : '100% Planar'}
              </div>
            </div>
            <div className="p-1.5 bg-surface rounded-lg border border-surface-border">
              <div>IndicSoundex (10%)</div>
              <div className="text-emerald-400 font-bold">96.0% Match</div>
            </div>
          </div>
        </div>

        {/* 3D Digital Twin nDSM Metrics */}
        <div className="gis-glass-card rounded-xl p-3 border border-surface-border flex items-center justify-between text-[11px]">
          <div className="flex items-center space-x-2 text-slate-300">
            <Building className="w-4 h-4 text-indigo-400" />
            <span>nDSM Structure Height:</span>
          </div>
          <span className="font-mono font-bold text-white">{parcel.ndsm_height_m} m</span>
        </div>

        {/* Encroachment Alert Box if Disputed */}
        {isEncroaching && (
          <div className="rounded-xl p-3.5 bg-rose-950/40 border border-rose-500/50 space-y-2">
            <div className="flex items-center space-x-2 text-rose-400 font-bold text-xs">
              <AlertTriangle className="w-4 h-4 flex-shrink-0 animate-pulse" />
              <span>Municipal Encroachment Detected</span>
            </div>
            <div className="text-[11px] text-rose-200">
              {parcel.encroachment_type || parcel.discrepancy_type || 'Stormwater Drainage Canal Encroachment'}
            </div>
            <div className="text-[10px] font-mono text-rose-300/80">
              Measured Buffer Overlap: <b className="text-rose-300">{parcel.variance_sqm || `+${parcel.encroached_area_sqm} sq.m`}</b>
            </div>
            <div className="text-[10px] text-rose-300 font-medium">
              Statutory Clause: Section 248 Maharashtra Land Revenue Code
            </div>
          </div>
        )}
      </div>

      {/* Footer Action Buttons */}
      <div className="p-4 border-t border-surface-border space-y-2 bg-surface">
        <button
          onClick={handleDownloadPdf}
          disabled={isGeneratingPdf}
          className="w-full flex items-center justify-center space-x-2 py-2.5 px-3 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold transition-all shadow-lg shadow-emerald-600/20 active:scale-95"
        >
          <Download className="w-3.5 h-3.5" />
          <span>{isGeneratingPdf ? 'Generating PDF Title Card...' : 'Download Bhu-Aadhaar PDF'}</span>
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onOpenBhuAadhaarModal(parcel)}
            className="flex items-center justify-center space-x-1.5 py-2 px-2.5 rounded-xl bg-surface-raised hover:bg-[#1A463B] border border-surface-border text-slate-200 text-[11px] font-semibold transition-all active:scale-95"
          >
            <QrCode className="w-3 h-3 text-indigo-400" />
            <span>Digital Card</span>
          </button>

          {isEncroaching ? (
            <button
              onClick={() => onOpenNoticeModal(parcel)}
              className="flex items-center justify-center space-x-1.5 py-2 px-2.5 rounded-xl bg-rose-950/60 hover:bg-rose-900/80 border border-rose-500/50 text-rose-200 text-[11px] font-bold transition-all active:scale-95"
            >
              <AlertTriangle className="w-3 h-3 text-rose-400" />
              <span>Legal Notice</span>
            </button>
          ) : (
            <button
              onClick={() => onApproveParcel(parcel.parcel_id)}
              className="flex items-center justify-center space-x-1.5 py-2 px-2.5 rounded-xl bg-emerald-950/60 hover:bg-emerald-900/80 border border-emerald-500/50 text-emerald-200 text-[11px] font-bold transition-all active:scale-95"
            >
              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              <span>Approve</span>
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
