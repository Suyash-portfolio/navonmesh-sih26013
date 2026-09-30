import React, { useState } from 'react';
import { 
  AlertTriangle, ChevronUp, ChevronDown, Search, Filter, 
  Download, CheckCircle2, FileText
} from 'lucide-react';
import { generateEncroachmentNoticePDF } from '../utils/pdf-generator';

export default function ConflictResolutionTray({
  conflicts,
  onSelectConflict,
  onApproveConflict,
  onOpenNoticeModal
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  const filteredConflicts = conflicts.filter(c => {
    const matchesSearch = 
      c.owner_name.toLowerCase().includes(search.toLowerCase()) ||
      c.parcel_id.toLowerCase().includes(search.toLowerCase()) ||
      c.ulpin.toLowerCase().includes(search.toLowerCase()) ||
      c.khasra_no.toLowerCase().includes(search.toLowerCase());

    const matchesType = 
      typeFilter === 'all' ? true :
      typeFilter === 'drainage' ? c.discrepancy_type.includes('Drainage') :
      typeFilter === 'road' ? c.discrepancy_type.includes('Road') : true;

    return matchesSearch && matchesType;
  });

  const handleExportCsv = () => {
    const headers = ["Conflict ID", "Parcel ID", "ULPIN", "Owner Name", "Vernacular Name", "Khasra No", "Discrepancy Type", "Variance (sq.m)", "Confidence", "Statutory Directive"];
    const rows = conflicts.map(c => [
      c.id, c.parcel_id, c.ulpin, `"${c.owner_name}"`, `"${c.owner_vernacular}"`, c.khasra_no, `"${c.discrepancy_type}"`, c.encroached_area_sqm, c.confidence, `"${c.legal_action_required}"`
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Municipal_Encroachment_Audit_Dossier.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={`bg-surface/95 border-t border-surface-border transition-all duration-300 z-20 flex flex-col select-none shadow-2xl backdrop-blur-xl ${
      isOpen ? 'h-64' : 'h-10'
    }`}>
      {/* Tray Header Bar */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        className="h-10 px-5 bg-surface-raised/80 border-b border-surface-border flex items-center justify-between cursor-pointer hover:bg-[#1A463B] transition-colors"
      >
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 text-rose-400 font-bold text-xs font-mono uppercase">
            <AlertTriangle className="w-3.5 h-3.5 animate-pulse" />
            <span>Conflict Resolution & Encroachment Audit Tray</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
            {conflicts.length} Active Disputes
          </span>
        </div>

        <div className="flex items-center space-x-3">
          {isOpen && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleExportCsv();
              }}
              className="flex items-center space-x-1 text-[11px] font-semibold text-slate-300 hover:text-white px-2.5 py-1 rounded-lg bg-surface hover:bg-[#1A463B] border border-surface-border transition-all"
              title="Download CSV Dossier"
            >
              <Download className="w-3 h-3 text-indigo-400" />
              <span>Export CSV Dossier</span>
            </button>
          )}
          <button className="text-slate-400 hover:text-white">
            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Tray Body: Table & Controls */}
      {isOpen && (
        <div className="flex-1 flex flex-col p-3 overflow-hidden">
          {/* Search & Filter Bar */}
          <div className="flex items-center justify-between gap-3 mb-2">
            <div className="flex items-center space-x-2 flex-1 max-w-sm">
              <div className="relative w-full">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Search by owner, ULPIN, or Khasra..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-surface border border-surface-border rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-[11px] text-slate-400 font-mono">Dispute Type:</span>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-surface border border-surface-border rounded-xl px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option value="all">All Violations ({conflicts.length})</option>
                <option value="drainage">Stormwater Drainage Canals</option>
                <option value="road">Road Right-of-Way (RoW)</option>
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="flex-1 overflow-y-auto rounded-xl border border-surface-border bg-surface/50">
            <table className="w-full text-left text-xs">
              <thead className="bg-surface-raised text-[10px] uppercase font-mono text-slate-400 sticky top-0 border-b border-surface-border">
                <tr>
                  <th className="py-2 px-3">Conflict ID</th>
                  <th className="py-2 px-3">Parcel / Khasra</th>
                  <th className="py-2 px-3">Landowner Details</th>
                  <th className="py-2 px-3">Discrepancy / Violation</th>
                  <th className="py-2 px-3">Variance</th>
                  <th className="py-2 px-3">AI Confidence</th>
                  <th className="py-2 px-3 text-right">Statutory Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50 text-[11px]">
                {filteredConflicts.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => onSelectConflict(c)}
                    className="hover:bg-[#1A463B]/60 cursor-pointer transition-colors group"
                  >
                    <td className="py-2 px-3 font-mono font-bold text-rose-400 flex items-center space-x-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                      <span>{c.id}</span>
                    </td>
                    <td className="py-2 px-3 font-mono">
                      <div className="text-white font-semibold">{c.khasra_no}</div>
                      <div className="text-[10px] text-slate-400">{c.parcel_id}</div>
                    </td>
                    <td className="py-2 px-3">
                      <div className="text-slate-200 font-medium">{c.owner_name}</div>
                      <div className="text-[10px] text-emerald-400 font-sans">{c.owner_vernacular}</div>
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-950/60 text-rose-300 border border-rose-500/40">
                        {c.discrepancy_type}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono font-bold text-rose-400">
                      {c.variance_sqm}
                    </td>
                    <td className="py-2 px-3 font-mono text-emerald-400 font-bold">
                      {c.confidence}
                    </td>
                    <td className="py-2 px-3 text-right space-x-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenNoticeModal(c);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-rose-950/70 hover:bg-rose-900 border border-rose-500/50 text-rose-200 text-[10px] font-bold transition-all active:scale-95"
                        title="Download Section 248 Legal Notice PDF"
                      >
                        Notice
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onApproveConflict(c.parcel_id);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-500/50 text-emerald-300 text-[10px] font-medium transition-all active:scale-95"
                        title="Approve / Dismiss Conflict"
                      >
                        Approve
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
