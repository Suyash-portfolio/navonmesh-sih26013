import React from 'react';
import { CheckCircle2, AlertTriangle, ShieldCheck, Cpu, Compass } from 'lucide-react';

export default function MetricRibbon({ metrics, isHarmonizing }) {
  return (
    <div className="bg-surface/90 border-b border-surface-border px-5 py-2.5 flex items-center justify-between gap-4 overflow-x-auto select-none backdrop-blur-md">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 w-full max-w-7xl mx-auto">
        {/* KPI 1: Total Parcels */}
        <div className="gis-glass-card rounded-xl p-2.5 flex items-center space-x-3 border border-slate-700/40">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Total Parcels</div>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-base font-bold font-mono text-white">
                {metrics?.totalParcels?.toLocaleString() || '1,420'}
              </span>
              <span className="text-[9px] font-semibold text-emerald-400 font-mono px-1.5 py-0.2 rounded bg-emerald-500/10">100% Indexed</span>
            </div>
          </div>
        </div>

        {/* KPI 2: Harmonization Rate */}
        <div className="gis-glass-card rounded-xl p-2.5 flex items-center space-x-3 border border-emerald-500/20">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Harmonization Rate</div>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-base font-bold font-mono text-emerald-400">
                {metrics?.harmonizationRatePct || 96.4}%
              </span>
              <span className="text-[10px] font-medium text-slate-400 font-mono">Planar Clean</span>
            </div>
          </div>
        </div>

        {/* KPI 3: Active Encroachments */}
        <div className="gis-glass-card rounded-xl p-2.5 flex items-center space-x-3 border-rose-500/30 bg-rose-950/20">
          <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400 animate-pulse">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-rose-300">Active Conflicts</div>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-base font-bold font-mono text-rose-400">
                {metrics?.activeEncroachments ?? 0}
              </span>
              <span className="text-[10px] font-medium text-rose-300 font-mono">Drainage / RoW</span>
            </div>
          </div>
        </div>

        {/* KPI 4: Avg AI Confidence */}
        <div className="gis-glass-card rounded-xl p-2.5 flex items-center space-x-3 border border-teal-500/20">
          <div className="w-8 h-8 rounded-lg bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Mean AI Confidence</div>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-base font-bold font-mono text-teal-300">
                {metrics?.avgConfidencePct || 94.8}%
              </span>
              <span className="text-[10px] font-medium text-slate-400 font-mono">SAM-2 + Soundex</span>
            </div>
          </div>
        </div>

        {/* KPI 5: TPS Warping Precision */}
        <div className="gis-glass-card rounded-xl p-2.5 flex items-center space-x-3 border border-amber-500/20">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">TPS Warp Precision</div>
            <div className="flex items-baseline space-x-1.5">
              <span className="text-base font-bold font-mono text-amber-300">
                {metrics?.tpsWarpRmseCm || 4.2} cm
              </span>
              <span className="text-[10px] font-medium text-slate-400 font-mono">64 Tie-Points</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
