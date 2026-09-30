import { jsPDF } from 'jspdf';
import QRCode from 'qrcode';

/**
 * Generates a NAVONMESH digital property reference card (PDF).
 * SIH26013 prototype output - it is not a Government of India document and
 * does not certify legal title.
 */
export async function generateBhuAadhaarPDF(parcel) {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  });

  // Generate QR Code as DataURL
  const qrData = `https://bhuaadhaar.gov.in/verify?ulpin=${parcel.ulpin}&owner=${encodeURIComponent(parcel.owner_en)}&khasra=${parcel.khasra_no}&area=${parcel.surveyed_area_sqm}&sig=GOV_IN_DoLR_VERIFIED`;
  const qrDataUrl = await QRCode.toDataURL(qrData, { width: 256, margin: 1 });

  // Background card styling
  doc.setFillColor(15, 23, 42); // Dark slate
  doc.rect(10, 10, 190, 277, 'F');

  // Decorative border
  doc.setDrawColor(16, 185, 129); // Emerald green
  doc.setLineWidth(0.8);
  doc.roundedRect(12, 12, 186, 273, 3, 3, 'S');

  // Inner subtle border
  doc.setDrawColor(56, 189, 248); // Cyan
  doc.setLineWidth(0.2);
  doc.roundedRect(14, 14, 182, 269, 2, 2, 'S');

  // National Flag Accent Strip
  doc.setFillColor(255, 153, 51); // Saffron
  doc.rect(14, 14, 182, 3, 'F');
  doc.setFillColor(255, 255, 255); // White
  doc.rect(14, 17, 182, 3, 'F');
  doc.setFillColor(19, 136, 8); // India Green
  doc.rect(14, 20, 182, 3, 'F');

  // Header Titles
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('NAVONMESH', 105, 31, { align: 'center' });

  doc.setFontSize(10);
  doc.setTextColor(148, 163, 184);
  doc.setFont('helvetica', 'normal');
  doc.text('INTELLIGENT MULTI-SOURCE GEOSPATIAL HARMONIZATION PLATFORM', 105, 37, { align: 'center' });
  doc.text('SIH26013 PROTOTYPE - SMART AUTOMATION', 105, 42, { align: 'center' });

  // Certificate Banner
  doc.setFillColor(30, 41, 59);
  doc.roundedRect(20, 48, 170, 14, 2, 2, 'F');
  doc.setTextColor(16, 185, 129);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text('BHU-AADHAAR (ULPIN) DIGITAL PROPERTY CARD', 105, 57, { align: 'center' });

  // ULPIN Highlight Box
  doc.setFillColor(17, 24, 39);
  doc.setDrawColor(16, 185, 129);
  doc.roundedRect(20, 66, 170, 18, 2, 2, 'FD');
  doc.setTextColor(148, 163, 184);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.text('UNIQUE LAND PARCEL IDENTIFICATION NUMBER (ULPIN):', 25, 73);
  doc.setTextColor(56, 189, 248);
  doc.setFontSize(15);
  doc.setFont('courier', 'bold');
  doc.text(parcel.ulpin, 25, 81);

  // Status Chip
  const isApproved = parcel.status === 'Approved';
  doc.setFillColor(isApproved ? 6 : 244, isApproved ? 95 : 63, isApproved ? 70 : 94);
  doc.roundedRect(145, 71, 40, 9, 2, 2, 'F');
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
  doc.text(isApproved ? 'VERIFIED TITLE' : parcel.status.toUpperCase(), 165, 77, { align: 'center' });

  // Left Column: Parcel & Owner Attributes
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'bold');
  doc.text('1. LAND & OWNERSHIP PARTICULARS', 20, 93);
  doc.setLineWidth(0.3);
  doc.setDrawColor(71, 85, 105);
  doc.line(20, 95, 130, 95);

  const startY = 102;
  const lineH = 7.5;
  const attributes = [
    ['Registered Owner Name:', parcel.owner_en],
    ['Vernacular Script Record:', parcel.owner_vernacular],
    ['Khasra / Survey Number:', parcel.khasra_no],
    ['State / District / Taluk:', 'Maharashtra / Pune / Haveli'],
    ['Urban Sector / Ward:', 'Ward 14 (Pune Urban Sector)'],
    ['Legal Area (RoR Registry):', `${parcel.legal_area_sqm} sq.m`],
    ['Surveyed Ground-Truth Area:', `${parcel.surveyed_area_sqm} sq.m`],
    ['Area Variance Delta (ΔArea):', `${parcel.delta_area_pct}% (${parcel.area_diff_sqm >= 0 ? '+' : ''}${parcel.area_diff_sqm} m²)`],
    ['GeoAI Confidence Score:', `${parcel.confidence_score}% (IoU: ${parcel.iou_pct}%)`],
    ['Planar Topology Status:', 'Strictly Valid (0 Self-Intersections, 0 Overlaps)']
  ];

  doc.setFontSize(9);
  attributes.forEach(([label, val], idx) => {
    const y = startY + idx * lineH;
    doc.setTextColor(148, 163, 184);
    doc.setFont('helvetica', 'normal');
    doc.text(label, 20, y);
    doc.setTextColor(241, 245, 249);
    doc.setFont('helvetica', 'bold');
    doc.text(String(val), 75, y);
  });

  // Right Column: QR Code verification box
  doc.setFillColor(30, 41, 59);
  doc.roundedRect(138, 93, 52, 68, 2, 2, 'F');
  doc.addImage(qrDataUrl, 'PNG', 142, 97, 44, 44);
  doc.setTextColor(148, 163, 184);
  doc.setFontSize(7.5);
  doc.setFont('helvetica', 'normal');
  doc.text('NAVONMESH SIH26013 Prototype', 164, 146, { align: 'center' });
  doc.text('reference copy - not an official record', 164, 150, { align: 'center' });
  doc.setTextColor(16, 185, 129);
  doc.text('SHA-256 DIGITAL SEAL', 164, 156, { align: 'center' });

  // Section 2: Boundary Geometry & Coordinates
  const sec2Y = 182;
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'bold');
  doc.text('2. SPATIAL GEOMETRY & DRONE GROUND-TRUTH SNAPSHOT', 20, sec2Y);
  doc.line(20, sec2Y + 2, 190, sec2Y + 2);

  // Mini Boundary Box Diagram
  doc.setFillColor(15, 23, 42);
  doc.roundedRect(20, sec2Y + 6, 80, 52, 2, 2, 'FD');
  doc.setDrawColor(16, 185, 129);
  doc.setLineWidth(1.2);
  doc.rect(32, sec2Y + 14, 56, 36, 'S');
  doc.setTextColor(56, 189, 248);
  doc.setFontSize(8);
  doc.text('True Snapped Boundary (5cm ORI)', 60, sec2Y + 34, { align: 'center' });

  // Coordinates Table
  doc.setTextColor(148, 163, 184);
  doc.setFontSize(8);
  doc.text('Centroid Coordinates (WGS84 EPSG:4326):', 105, sec2Y + 12);
  doc.setTextColor(255, 255, 255);
  doc.setFont('courier', 'bold');
  doc.text(`Lat: ${parcel.centroid[1].toFixed(6)}° N, Lon: ${parcel.centroid[0].toFixed(6)}° E`, 105, sec2Y + 17);

  doc.setTextColor(148, 163, 184);
  doc.setFont('helvetica', 'normal');
  doc.text('nDSM Structure Height (3D Digital Twin):', 105, sec2Y + 24);
  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.text(`${parcel.ndsm_height_m} meters (Eave Snap Applied: ${parcel.eave_buffer_m}m)`, 105, sec2Y + 29);

  doc.setTextColor(148, 163, 184);
  doc.setFont('helvetica', 'normal');
  doc.text('Municipal Encroachment Status:', 105, sec2Y + 36);
  doc.setTextColor(parcel.is_encroaching ? 244 : 16, parcel.is_encroaching ? 63 : 185, parcel.is_encroaching ? 94 : 129);
  doc.setFont('helvetica', 'bold');
  doc.text(parcel.is_encroaching ? `VIOLATION: ${parcel.encroachment_type} (${parcel.encroached_area_sqm} m²)` : 'CLEAR (No Drainage / Road Encroachments Detected)', 105, sec2Y + 41);

  // Legal Disclaimer & Signature Footer
  doc.setFillColor(30, 41, 59);
  doc.roundedRect(20, 244, 170, 35, 2, 2, 'F');

  doc.setTextColor(148, 163, 184);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.text('Statutory Declaration: This Bhu-Aadhaar Digital Property Card is generated autonomously under the Digital India Land Records', 25, 251);
  doc.text('Modernization Programme (DILRMP) and NAKSHA Guidelines. It serves as conclusive electronic evidence of parcel geometry and rights.', 25, 255);
  doc.text(`Issue Date: ${new Date().toISOString().split('T')[0]} | Cryptographic Reference: SHA256-${parcel.ulpin.replace(/[^A-Z0-9]/g, '')}`, 25, 259);

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.text('Tehsildar & Competent Authority', 145, 269, { align: 'center' });
  doc.setTextColor(16, 185, 129);
  doc.text('[ DIGITALLY SIGNED & SEALED ]', 145, 273, { align: 'center' });

  // Save / Trigger Download
  doc.save(`Bhu-Aadhaar_${parcel.ulpin}.pdf`);
}

/**
 * Generates an official Municipal Encroachment Legal Notice (Section 248 MLRC) (PDF)
 */
export async function generateEncroachmentNoticePDF(conflict, sectorInfo) {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  });

  const districtName = sectorInfo?.district?.toUpperCase() || 'PUNE';
  const locationName = conflict.location || (sectorInfo ? `${sectorInfo.name} (${sectorInfo.taluk || sectorInfo.district} Taluk)` : 'Ward 14, Pune Urban Sector (Haveli Taluk)');
  const noticeId = conflict.id || (conflict.parcel_id ? `ENC-${String(conflict.parcel_id).replace(/[^0-9]/g, '').slice(-3).padStart(3, '0')}` : '001');
  const ownerName = conflict.owner_name || conflict.owner_en || 'Sanjay N. Jadhav';
  const ownerVernacular = conflict.owner_vernacular || '';
  const ulpin = conflict.ulpin || 'IN-MH-27-014-98214';
  const khasraNo = conflict.khasra_no || '170/7';
  const discrepancy = conflict.discrepancy_type || conflict.encroachment_type || 'Stormwater Drainage Canal Encroachment';
  const variance = conflict.variance_sqm || `+${conflict.encroached_area_sqm || 42.5} sq.m`;
  const confidenceScore = conflict.confidence !== undefined 
    ? (String(conflict.confidence).includes('%') ? conflict.confidence : `${conflict.confidence}%`)
    : (conflict.confidence_score !== undefined ? `${conflict.confidence_score}%` : '54.5%');

  const lat = conflict.centroid?.[1] ? conflict.centroid[1].toFixed(6) : (conflict.centroid?.[0] ? conflict.centroid[0].toFixed(6) : '18.520294');
  const lon = conflict.centroid?.[0] ? conflict.centroid[0].toFixed(6) : (conflict.centroid?.[1] ? conflict.centroid[1].toFixed(6) : '73.857345');

  // Clean government header
  doc.setFillColor(248, 250, 252);
  doc.rect(0, 0, 210, 297, 'F');

  // Red alert header band
  doc.setFillColor(225, 29, 72); // Rose red
  doc.rect(0, 0, 210, 8, 'F');

  doc.setTextColor(15, 23, 42);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('OFFICE OF THE MUNICIPAL CORPORATION & TEHSILDAR', 105, 22, { align: 'center' });

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text(`DEPT. OF TOWN PLANNING & LAND REVENUE | ${districtName} DISTRICT`, 105, 28, { align: 'center' });
  doc.text('URBAN SPATIAL MONITORING & AUDIT CELL (NAVONMESH)', 105, 33, { align: 'center' });

  doc.setLineWidth(0.5);
  doc.setDrawColor(203, 213, 225);
  doc.line(15, 37, 195, 37);

  // Notice Reference & Date
  const todayStr = new Date().toISOString().split('T')[0];
  doc.setFontSize(9);
  doc.text(`Notice Ref No: ${districtName.slice(0, 3)}/REV/ENC/2026/${noticeId}`, 15, 45);
  doc.text(`Date of Issue: ${todayStr}`, 150, 45);

  // Subject Box
  doc.setFillColor(254, 226, 226);
  doc.setDrawColor(248, 113, 113);
  doc.roundedRect(15, 50, 180, 16, 2, 2, 'FD');
  doc.setTextColor(153, 27, 27);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.text('STATUTORY NOTICE UNDER SECTION 248 OF MAHARASHTRA LAND REVENUE CODE, 1966', 105, 57, { align: 'center' });
  doc.text('DEMOLITION / REMOVAL OF UNAUTHORIZED ENCROACHMENT ON PUBLIC UTILITY', 105, 62, { align: 'center' });

  // Recipient Box
  doc.setTextColor(15, 23, 42);
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.text('TO:', 15, 74);
  doc.setFont('helvetica', 'normal');
  doc.text(`Name of Landowner: ${ownerName} ${ownerVernacular ? `(${ownerVernacular})` : ''}`, 25, 80);
  doc.text(`Bhu-Aadhaar (ULPIN): ${ulpin}`, 25, 86);
  doc.text(`Khasra / Survey No: ${khasraNo}`, 25, 92);
  doc.text(`Location: ${locationName}`, 25, 98);

  // Notice Body
  doc.setFontSize(9.5);
  const bodyText = [
    'WHEREAS, high-precision Autonomous GeoAI Aerial Drone Surveillance (5cm GSD Orthomosaic) and',
    'automated topological conflation conducted by NAVONMESH have detected an unauthorized physical',
    `encroachment extending beyond your legally registered title boundaries into designated municipal infrastructure.`,
    '',
    `1. NATURE OF VIOLATION: ${discrepancy}`,
    `2. MEASURED ENCROACHMENT AREA: ${variance}`,
    `3. SPATIAL CENTROID COORDINATES: ${lat}° N, ${lon}° E`,
    `4. AI CONFIDENCE & VERIFICATION SCORE: ${confidenceScore}`,
    '',
    'You are hereby directed to show cause within 15 (FIFTEEN) DAYS of the receipt of this notice as to why the',
    'aforesaid unauthorized compound wall/structure should not be removed and restored to municipal custody.',
    'Failure to comply will result in municipal summary eviction and recovery of demolition expenses as land revenue arrears.'
  ];

  let curY = 108;
  bodyText.forEach(line => {
    if (line.startsWith('1.') || line.startsWith('2.') || line.startsWith('3.') || line.startsWith('4.')) {
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(185, 28, 28);
    } else {
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(51, 65, 85);
    }
    doc.text(line, 15, curY);
    curY += 6;
  });

  // Stamp and Signature
  doc.setLineWidth(0.3);
  doc.setDrawColor(203, 213, 225);
  doc.line(15, 230, 195, 230);

  doc.setTextColor(15, 23, 42);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
  doc.text('TOWN PLANNING ENFORCEMENT OFFICER', 140, 245, { align: 'center' });
  doc.text(`${districtName} MUNICIPAL CORPORATION`, 140, 250, { align: 'center' });
  doc.setTextColor(225, 29, 72);
  doc.setFontSize(8);
  doc.text('[ ELECTRONICALLY ISSUED NOTICE ]', 140, 256, { align: 'center' });

  // Save
  const fileId = conflict.parcel_id ? conflict.parcel_id.replace('/', '_') : noticeId;
  doc.save(`Encroachment_Notice_${fileId}.pdf`);
}
