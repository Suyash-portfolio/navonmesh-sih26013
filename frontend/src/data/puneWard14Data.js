/**
 * NAVONMESH - Multi-Sector Cadastral Datasets (Pune, Nagpur, Thane)
 * Enables zero-latency rendering and 100% offline air-gapped hackathon demo evaluation.
 */

const firstNamesVernacular = ["रमेश", "सुरेश", "गणेश", "अनिता", "दत्तात्रय", "प्रकाश", "सुनीता", "विजय", "दीपक", "संजय", "मंगेश", "प्रवीण", "सविता", "अमोल", "संदीप"];
const middleNamesVernacular = ["शंकरराव", "महादेव", "विठ्ठल", "बाबुराव", "रामचंद्र", "दत्तात्रय", "गोविंद", "आनंदराव", "भास्कर", "नारायण"];
const lastNamesVernacular = ["कुलकर्णी", "पाटील", "जोशी", "जाधव", "देशमुख", "शिंदे", "पवार", "गायकवाड", "मोरे", "कदम", "भोसले", "चव्हाण", "सावंत"];

const firstNamesEn = ["Ramesh", "Suresh", "Ganesh", "Anita", "Dattatraya", "Prakash", "Sunita", "Vijay", "Deepak", "Sanjay", "Mangesh", "Pravin", "Savita", "Amol", "Sandeep"];
const middleNamesEn = ["S.", "M.", "V.", "B.", "R.", "D.", "G.", "A.", "Bhaskar", "N."];
const lastNamesEn = ["Kulkarni", "Patil", "Joshi", "Jadhav", "Deshmukh", "Shinde", "Pawar", "Gaikwad", "More", "Kadam", "Bhosle", "Chavan", "Sawant"];

export function generateSectorData(sectorId = 'pune_ward14') {
  let centerLon = 73.8567;
  let centerLat = 18.5204;
  let sectorName = "Ward 14, Pune Urban Sector";
  let district = "Pune";
  let taluk = "Haveli";
  let code = "PUN";
  let total = 1420;
  let defaultZoom = 17.2;

  if (sectorId === 'nagpur_sec3') {
    centerLon = 79.0882;
    centerLat = 21.1458;
    sectorName = "Ward 03, Nagpur Peri-Urban";
    district = "Nagpur";
    taluk = "Nagpur Urban";
    code = "NGP";
    total = 980;
    defaultZoom = 17.0;
  } else if (sectorId === 'thane_sec8') {
    centerLon = 72.9781;
    centerLat = 19.2183;
    sectorName = "Ward 08, Thane Metropolitan";
    district = "Thane";
    taluk = "Thane";
    code = "THN";
    total = 2150;
    defaultZoom = 16.8;
  }

  const rows = Math.ceil(Math.sqrt(total));
  const cols = rows;

  const cellW = 0.00026;
  const cellH = 0.00022;
  const originLon = centerLon - (cols * cellW) / 2;
  const originLat = centerLat - (rows * cellH) / 2;

  const drainage = [
    [centerLon - 0.0047, centerLat - 0.0034],
    [centerLon - 0.0022, centerLat - 0.0012],
    [centerLon + 0.0003, centerLat + 0.0011],
    [centerLon + 0.0028, centerLat + 0.0034],
    [centerLon + 0.0048, centerLat + 0.0051]
  ];

  const road = [
    [centerLon - 0.0057, centerLat + 0.0016],
    [centerLon - 0.0027, centerLat + 0.0014],
    [centerLon + 0.0013, centerLat + 0.0008],
    [centerLon + 0.0053, centerLat + 0.0004]
  ];

  const parcels = [];
  const conflicts = [];

  // Calculate realistic dispute / encroachment count proportional to sector parcel size & urban density
  let conflictRate = 0.0239; // Default: ~34 disputes for 1,420 parcels (Pune Urban)
  if (sectorId === 'nagpur_sec3') {
    conflictRate = 0.0184; // ~18 disputes for 980 parcels (Nagpur Peri-Urban)
  } else if (sectorId === 'thane_sec8') {
    conflictRate = 0.0289; // ~62 disputes for 2,150 parcels (Thane Metropolitan)
  }

  const numConflicts = Math.round(total * conflictRate);
  const step = Math.max(1, Math.floor(total / (numConflicts + 2)));
  const encroachmentIndices = new Set(
    Array.from({ length: numConflicts }, (_, i) => Math.min(total - 2, (i + 1) * step + ((i * 7) % 5)))
  );

  let parcelIdx = 0;
  let conflictCounter = 1;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (parcelIdx >= total) break;
      parcelIdx++;

      const parcelId = `MH-${code}-${100 + Math.floor(parcelIdx / 10)}/${(parcelIdx % 10) + 1}`;
      const khasraNo = `${100 + Math.floor(parcelIdx / 10)}/${(parcelIdx % 10) + 1}${parcelIdx % 3 === 0 ? '-A' : ''}`;
      
      const jitterX = Math.sin(parcelIdx * 12.3) * 0.000015;
      const jitterY = Math.cos(parcelIdx * 9.7) * 0.000015;
      const x0 = originLon + c * cellW + jitterX;
      const y0 = originLat + r * cellH + jitterY;
      const w = cellW * (0.86 + Math.sin(parcelIdx * 3.1) * 0.06);
      const h = cellH * (0.86 + Math.cos(parcelIdx * 4.2) * 0.06);

      // AI Ground-truth harmonized geometry (Green snapped wall)
      const aiCoords = [
        [x0, y0],
        [x0 + w, y0],
        [x0 + w, y0 + h],
        [x0, y0 + h],
        [x0, y0]
      ];

      // Distorted legacy geometry (Crooked blue cloth map lines)
      const shear = 0.000042 * Math.sin(r * 0.35);
      const shrink = 0.94 + 0.07 * Math.cos(c * 0.45);
      const legacyCoords = [
        [x0 - shear, y0 - shear],
        [x0 + w * shrink + shear * 0.5, y0 - shear * 0.8],
        [x0 + w * shrink + shear * 1.2, y0 + h * shrink + shear * 0.6],
        [x0 - shear * 0.7, y0 + h * shrink - shear * 0.4],
        [x0 - shear, y0 - shear]
      ];

      const surveyedArea = +(w * h * 111000 * 111000).toFixed(1);
      const isEncroaching = encroachmentIndices.has(parcelIdx);
      let encroachmentType = null;
      let encroachedArea = 0;
      let status = "Approved";
      let statusChip = "APPROVED";
      let confidence = +(94.0 + (Math.sin(parcelIdx) * 4.5)).toFixed(1);

      let legalArea;
      if (isEncroaching) {
        status = "Encroachment";
        statusChip = "ENCROACHMENT";
        encroachmentType = parcelIdx % 2 === 0 
          ? "Stormwater Drainage Canal Encroachment" 
          : "Municipal Road Right-of-Way (RoW) Encroachment";
        // Encroachment violation area scaled dynamically relative to parcel's surveyed size (6% - 15%)
        const encroachmentRatio = 0.065 + ((parcelIdx % 8) * 0.012);
        encroachedArea = +(surveyedArea * encroachmentRatio).toFixed(1);
        confidence = +(41.0 + (parcelIdx % 18)).toFixed(1);
        // Legal deed area is smaller than surveyed ground truth due to illegal buffer overlap
        legalArea = +(surveyedArea - encroachedArea).toFixed(1);
      } else {
        // Realistic historical chain survey variance (±0.8% to ±3.4%)
        const varianceFactor = 0.968 + (((parcelIdx * 13) % 45) * 0.0014);
        legalArea = +(surveyedArea * (varianceFactor === 1.0 ? 0.985 : varianceFactor)).toFixed(1);
      }

      const deltaArea = Math.abs(legalArea - surveyedArea) / legalArea;
      const areaDiff = +(surveyedArea - legalArea).toFixed(1);

      const fnIdx = (r * 7 + c * 3) % firstNamesVernacular.length;
      const mnIdx = (r * 3 + c * 5) % middleNamesVernacular.length;
      const lnIdx = (r * 11 + c * 13) % lastNamesVernacular.length;

      const ownerVernacular = `${firstNamesVernacular[fnIdx]} ${middleNamesVernacular[mnIdx]} ${lastNamesVernacular[lnIdx]}`;
      const ownerEn = `${firstNamesEn[fnIdx]} ${middleNamesEn[mnIdx]} ${lastNamesEn[lnIdx]}`;

      if (!isEncroaching && (deltaArea > 0.028 || parcelIdx % 19 === 0)) {
        status = "Review";
        statusChip = "REVIEW";
        confidence = +(78.0 + (parcelIdx % 10)).toFixed(1);
      }

      const seqStr = String((parcelIdx % 99) + 1).padStart(2, '0');
      const ulpin = `IN-MH-${code === 'PUN' ? '27' : code === 'NGP' ? '31' : '21'}-014-982${seqStr}`;
      const ndsmHeight = +(3.2 + (parcelIdx % 5) * 3.1 + (parcelIdx % 3) * 0.8).toFixed(1);

      const parcelObj = {
        parcel_id: parcelId,
        ulpin,
        khasra_no: khasraNo,
        owner_vernacular: ownerVernacular,
        owner_en: ownerEn,
        owner_name: ownerEn,
        legal_area_sqm: legalArea,
        surveyed_area_sqm: surveyedArea,
        area_diff_sqm: areaDiff,
        delta_area_pct: +(deltaArea * 100).toFixed(2),
        confidence_score: confidence,
        status,
        status_chip: statusChip,
        ndsm_height_m: ndsmHeight,
        eave_buffer_m: ndsmHeight >= 3.0 ? 0.40 : 0.0,
        is_encroaching: isEncroaching,
        encroachment_type: encroachmentType,
        discrepancy_type: encroachmentType,
        encroached_area_sqm: encroachedArea,
        variance_sqm: `+${encroachedArea} sq.m`,
        coordinates_ai: aiCoords,
        coordinates_legacy: legacyCoords,
        centroid: [+(x0 + w/2).toFixed(6), +(y0 + h/2).toFixed(6)],
        iou_pct: isEncroaching ? +(62.5 + (parcelIdx % 8) * 1.5).toFixed(1) : +(96.2 + Math.cos(parcelIdx) * 2.1).toFixed(1)
      };

      parcels.push(parcelObj);

      if (isEncroaching && conflicts.length < numConflicts) {
        conflicts.push({
          id: `ENC-${String(conflictCounter).padStart(3, '0')}`,
          parcel_id: parcelId,
          ulpin,
          owner_name: ownerEn,
          owner_en: ownerEn,
          owner_vernacular: ownerVernacular,
          khasra_no: khasraNo,
          discrepancy_type: encroachmentType,
          encroachment_type: encroachmentType,
          variance_sqm: `+${encroachedArea} sq.m`,
          encroached_area_sqm: encroachedArea,
          legal_area_sqm: legalArea,
          surveyed_area_sqm: surveyedArea,
          confidence: `${confidence}%`,
          confidence_score: confidence,
          confidence_num: confidence,
          centroid: parcelObj.centroid,
          coordinates_ai: aiCoords,
          coordinates_legacy: legacyCoords,
          legal_action_required: "Issue Notice u/s 248 MLRC"
        });
        conflictCounter++;
      }
    }
  }

  const harmonizedCount = parcels.filter(p => p.status === "Approved").length;
  const harmonizationRate = +((harmonizedCount / parcels.length) * 100).toFixed(1);
  const avgConfidence = +(parcels.reduce((acc, p) => acc + p.confidence_score, 0) / parcels.length).toFixed(1);

  return {
    sectorInfo: {
      name: sectorName,
      state: "Maharashtra",
      district,
      taluk,
      crs: "EPSG:4326 (WGS84) / EPSG:32643 (UTM 43N)",
      center: [centerLon, centerLat],
      zoom: defaultZoom
    },
    kpiMetrics: {
      totalParcels: parcels.length,
      harmonizationRatePct: harmonizationRate,
      activeEncroachments: conflicts.length,
      avgConfidencePct: avgConfidence,
      gcpTiePoints: 64,
      tpsWarpRmseCm: 4.2
    },
    parcels,
    conflicts,
    infrastructure: {
      drainage,
      road
    }
  };
}

export function generateWard14Parcels() {
  return generateSectorData('pune_ward14');
}

export const defaultSectorData = generateWard14Parcels();

export const drainageLine = [
  [73.8520, 18.5170],
  [73.8545, 18.5192],
  [73.8570, 18.5215],
  [73.8595, 18.5238],
  [73.8615, 18.5255]
];

export const roadLine = [
  [73.8510, 18.5220],
  [73.8540, 18.5218],
  [73.8580, 18.5212],
  [73.8620, 18.5208]
];
