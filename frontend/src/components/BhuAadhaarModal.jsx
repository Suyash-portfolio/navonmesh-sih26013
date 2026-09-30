import React, { useEffect, useState } from 'react';
import { X, Download, QrCode, ShieldCheck } from 'lucide-react';
import QRCode from 'qrcode';
import { generateBhuAadhaarPDF } from '../utils/pdf-generator';

export default function BhuAadhaarModal({ isOpen, onClose, parcel }) {
  const [qrUrl, setQrUrl] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (parcel) {
      const qrData = `https://bhuaadhaar.gov.in/verify?ulpin=${parcel.ulpin}&owner=${encodeURIComponent(parcel.owner_en)}&khasra=${parcel.khasra_no}&area=${parcel.surveyed_area_sqm}&sig=GOV_IN_DoLR_VERIFIED`;
      QRCode.toDataURL(qrData, { width: 256, margin: 1 })
        .then(url => setQrUrl(url))
        .catch(err => console.error(err));
    }
  }, [parcel]);

  if (!isOpen || !parcel) return null;

  const handleDownload = async () => {
    setIsGenerating(true);
    try {
      await generateBhuAadhaarPDF(parcel);
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 select-none animate-in fade-in duration-200">
      <div className="bg-[#0B1F1A] border border-slate-700/60 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-[#0B1F1A]/90">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <QrCode className="w-5 h-5" />
            </div>
            <h3 className="font-outfit text-sm font-bold text-white">
              Official Bhu-Aadhaar (ULPIN) Digital Property Card
            </h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[#1A463B] text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Card Content */}
        <div className="p-6">
          <div className="bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border border-emerald-500/30 rounded-xl p-5 relative overflow-hidden shadow-2xl">
            {/* NAVONMESH Brand Top Strip (replaces the national tricolour - this is not a Government of India document) */}
            <div className="absolute top-0 left-0 right-0 h-1.5 flex">
              <div className="w-1/3 bg-[#0F766E]"></div>
              <div className="w-1/3 bg-[#14B8A6]"></div>
              <div className="w-1/3 bg-[#34D399]"></div>
            </div>

            {/* Header Titles */}
            <div className="text-center pt-2 pb-3 border-b border-slate-800">
              <div className="text-[11px] font-bold text-white tracking-[0.2em]">NAVONMESH</div>
              <div className="text-[10px] text-slate-400 uppercase">MoRD | Department of Land Resources (DoLR) · SIH26013 Prototype</div>
              <div className="text-xs font-bold text-emerald-400 tracking-wide mt-1">
                DIGITAL PROPERTY REFERENCE CARD
              </div>
            </div>

            {/* ULPIN & QR Section */}
            <div className="grid grid-cols-3 gap-4 my-4 items-center">
              <div className="col-span-2 space-y-2">
                <div className="p-2.5 rounded-xl bg-[#0B1F1A] border border-indigo-500/30">
                  <div className="text-[9px] font-mono uppercase text-slate-400">Unique Land Parcel Identifier (ULPIN)</div>
                  <div className="text-sm font-mono font-bold text-white tracking-wider mt-0.5">
                    {parcel.ulpin}
                  </div>
                </div>

                <div className="space-y-1 text-xs">
                  <div>
                    <span className="text-slate-400 text-[10px]">Landowner: </span>
                    <b className="text-white">{parcel.owner_en}</b>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[10px]">Vernacular Record: </span>
                    <span className="text-emerald-300 font-medium">{parcel.owner_vernacular}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 text-[10px]">Khasra No: </span>
                    <b className="font-mono text-slate-200">{parcel.khasra_no}</b>
                  </div>
                </div>
              </div>

              {/* Scannable QR Code */}
              <div className="flex flex-col items-center justify-center p-2 rounded-xl bg-white shadow-md">
                {qrUrl ? (
                  <img src={qrUrl} alt="Bhu-Aadhaar QR Code" className="w-24 h-24 block" />
                ) : (
                  <div className="w-24 h-24 bg-slate-200 animate-pulse"></div>
                )}
                <span className="text-[8px] font-bold text-slate-800 mt-1 uppercase">Scan to Verify</span>
              </div>
            </div>

            {/* Survey Details & Coordinates */}
            <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-[#16362E]/40 border border-slate-700/50 text-center text-[10px] font-mono">
              <div>
                <div className="text-slate-400">Legal Area</div>
                <div className="text-slate-200 font-bold">{parcel.legal_area_sqm} m²</div>
              </div>
              <div>
                <div className="text-slate-400">Surveyed Area</div>
                <div className="text-emerald-300 font-bold">{parcel.surveyed_area_sqm} m²</div>
              </div>
              <div>
                <div className="text-slate-400">AI Confidence</div>
                <div className="text-emerald-400 font-bold">{parcel.confidence_score}%</div>
              </div>
            </div>

            {/* Digital Stamp Footer */}
            <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-800 text-[9px] text-slate-400">
              <div className="flex items-center space-x-1 text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span className="font-bold">Digitally Sealed & Cryptographically Signed</span>
              </div>
              <span>DoLR • NAKSHA | SIH26013 Prototype</span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-end space-x-3 mt-5">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-[#16362E] hover:bg-[#1E4C40] text-slate-300 text-xs font-semibold transition-all"
            >
              Close
            </button>
            <button
              onClick={handleDownload}
              disabled={isGenerating}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/25 active:scale-95 transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{isGenerating ? 'Generating PDF...' : 'Download Official PDF Card'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
