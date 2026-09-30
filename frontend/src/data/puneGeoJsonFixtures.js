/**
 * Real-World Cadastral GeoJSON Fixture for Pune Urban Sector (Ward 14, Shaniwar/Kasba Peth, Pune)
 * Center Coordinates: [73.8567, 18.5204] (EPSG:4326 WGS84)
 * Overlays accurately onto Esri World Imagery Satellite Tiles
 */

export const PUNE_CENTER = [73.8567, 18.5204];
export const DEFAULT_ZOOM = 18;

// Primary 10 Detailed Real-World Parcels aligned with Pune Urban Building Footprints
export const realWorldParcelsGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: 1,
      properties: {
        parcel_id: "MH-PUN-104/1",
        ulpin: "IN-MH-27-014-98210-2026",
        khasra_no: "104/1-A",
        owner_en: "Ramesh S. Kulkarni",
        owner_vernacular: "रमेश शंकरराव कुलकर्णी",
        legal_area_sqm: 250.0,
        surveyed_area_sqm: 248.8,
        delta_area_pct: -0.48,
        confidence_score: 96.8,
        status: "Approved",
        status_chip: "APPROVED",
        ndsm_height_m: 8.5,
        eave_buffer_m: 0.40,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 97.4,
        tps_rmse_cm: 3.8
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85620, 18.52010],
          [73.85655, 18.52012],
          [73.85653, 18.52045],
          [73.85618, 18.52043],
          [73.85620, 18.52010]
        ]]
      },
      // Distorted legacy cloth map geometry (offset by 3-5m into street/neighbor)
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85616, 18.52006],
          [73.85651, 18.52008],
          [73.85661, 18.52049],
          [73.85624, 18.52048],
          [73.85616, 18.52006]
        ]]
      }
    },
    {
      type: "Feature",
      id: 2,
      properties: {
        parcel_id: "MH-PUN-104/2",
        ulpin: "IN-MH-27-014-98211-2026",
        khasra_no: "104/2-B",
        owner_en: "Suresh M. Patil",
        owner_vernacular: "सुरेश महादेव पाटील",
        legal_area_sqm: 310.0,
        surveyed_area_sqm: 324.6,
        delta_area_pct: 4.71,
        confidence_score: 42.1,
        status: "Encroachment",
        status_chip: "ENCROACHMENT",
        ndsm_height_m: 6.2,
        eave_buffer_m: 0.35,
        is_encroaching: true,
        encroachment_type: "Stormwater Drainage Canal Encroachment",
        encroached_area_sqm: 14.6,
        iou_pct: 78.2,
        tps_rmse_cm: 5.1
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85660, 18.52013],
          [73.85702, 18.52015],
          [73.85700, 18.52050],
          [73.85658, 18.52048],
          [73.85660, 18.52013]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85655, 18.52008],
          [73.85695, 18.52010],
          [73.85708, 18.52055],
          [73.85665, 18.52053],
          [73.85655, 18.52008]
        ]]
      }
    },
    {
      type: "Feature",
      id: 3,
      properties: {
        parcel_id: "MH-PUN-104/3",
        ulpin: "IN-MH-27-014-98212-2026",
        khasra_no: "104/3",
        owner_en: "Anita V. Joshi",
        owner_vernacular: "अनिता विठ्ठल जोशी",
        legal_area_sqm: 180.0,
        surveyed_area_sqm: 179.2,
        delta_area_pct: -0.44,
        confidence_score: 98.2,
        status: "Approved",
        status_chip: "APPROVED",
        ndsm_height_m: 12.0,
        eave_buffer_m: 0.45,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 98.6,
        tps_rmse_cm: 3.2
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85708, 18.52016],
          [73.85742, 18.52017],
          [73.85740, 18.52049],
          [73.85706, 18.52047],
          [73.85708, 18.52016]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85704, 18.52012],
          [73.85737, 18.52013],
          [73.85746, 18.52054],
          [73.85712, 18.52052],
          [73.85704, 18.52012]
        ]]
      }
    },
    {
      type: "Feature",
      id: 4,
      properties: {
        parcel_id: "MH-PUN-105/1",
        ulpin: "IN-MH-27-014-98213-2026",
        khasra_no: "105/1",
        owner_en: "Dattatraya B. Jadhav",
        owner_vernacular: "दत्तात्रय बाबुराव जाधव",
        legal_area_sqm: 290.0,
        surveyed_area_sqm: 284.5,
        delta_area_pct: -1.89,
        confidence_score: 82.4,
        status: "Review",
        status_chip: "REVIEW",
        ndsm_height_m: 9.4,
        eave_buffer_m: 0.40,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 88.5,
        tps_rmse_cm: 4.6
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85617, 18.52052],
          [73.85654, 18.52054],
          [73.85651, 18.52090],
          [73.85614, 18.52088],
          [73.85617, 18.52052]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85623, 18.52048],
          [73.85660, 18.52050],
          [73.85645, 18.52095],
          [73.85608, 18.52093],
          [73.85623, 18.52048]
        ]]
      }
    },
    {
      type: "Feature",
      id: 5,
      properties: {
        parcel_id: "MH-PUN-105/2",
        ulpin: "IN-MH-27-014-98214-2026",
        khasra_no: "105/2-A",
        owner_en: "Sunita P. Deshmukh",
        owner_vernacular: "सुनीता प्रकाश देशमुख",
        legal_area_sqm: 220.0,
        surveyed_area_sqm: 219.1,
        delta_area_pct: -0.41,
        confidence_score: 97.9,
        status: "Approved",
        status_chip: "APPROVED",
        ndsm_height_m: 7.8,
        eave_buffer_m: 0.40,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 98.1,
        tps_rmse_cm: 3.5
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85658, 18.52055],
          [73.85698, 18.52057],
          [73.85695, 18.52091],
          [73.85655, 18.52089],
          [73.85658, 18.52055]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85652, 18.52050],
          [73.85691, 18.52052],
          [73.85702, 18.52096],
          [73.85661, 18.52094],
          [73.85652, 18.52050]
        ]]
      }
    },
    {
      type: "Feature",
      id: 6,
      properties: {
        parcel_id: "MH-PUN-105/3",
        ulpin: "IN-MH-27-014-98215-2026",
        khasra_no: "105/3",
        owner_en: "Vijay R. Shinde",
        owner_vernacular: "विजय रामचंद्र शिंदे",
        legal_area_sqm: 275.0,
        surveyed_area_sqm: 293.2,
        delta_area_pct: 6.62,
        confidence_score: 39.5,
        status: "Encroachment",
        status_chip: "ENCROACHMENT",
        ndsm_height_m: 5.5,
        eave_buffer_m: 0.35,
        is_encroaching: true,
        encroachment_type: "Municipal Road Right-of-Way (RoW) Encroachment",
        encroached_area_sqm: 18.2,
        iou_pct: 75.4,
        tps_rmse_cm: 5.8
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85705, 18.52056],
          [73.85746, 18.52058],
          [73.85744, 18.52093],
          [73.85702, 18.52091],
          [73.85705, 18.52056]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85710, 18.52051],
          [73.85752, 18.52053],
          [73.85738, 18.52098],
          [73.85697, 18.52096],
          [73.85710, 18.52051]
        ]]
      }
    },
    {
      type: "Feature",
      id: 7,
      properties: {
        parcel_id: "MH-PUN-106/1",
        ulpin: "IN-MH-27-014-98216-2026",
        khasra_no: "106/1",
        owner_en: "Deepak G. Pawar",
        owner_vernacular: "दीपक गोविंद पवार",
        legal_area_sqm: 340.0,
        surveyed_area_sqm: 338.4,
        delta_area_pct: -0.47,
        confidence_score: 96.5,
        status: "Approved",
        status_chip: "APPROVED",
        ndsm_height_m: 14.5,
        eave_buffer_m: 0.50,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 96.9,
        tps_rmse_cm: 3.9
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85612, 18.52095],
          [73.85650, 18.52097],
          [73.85647, 18.52134],
          [73.85609, 18.52132],
          [73.85612, 18.52095]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85608, 18.52090],
          [73.85646, 18.52092],
          [73.85655, 18.52139],
          [73.85617, 18.52137],
          [73.85608, 18.52090]
        ]]
      }
    },
    {
      type: "Feature",
      id: 8,
      properties: {
        parcel_id: "MH-PUN-106/2",
        ulpin: "IN-MH-27-014-98217-2026",
        khasra_no: "106/2",
        owner_en: "Sanjay A. Gaikwad",
        owner_vernacular: "संजय आनंदराव गायकवाड",
        legal_area_sqm: 260.0,
        surveyed_area_sqm: 258.9,
        delta_area_pct: -0.42,
        confidence_score: 97.4,
        status: "Approved",
        status_chip: "APPROVED",
        ndsm_height_m: 10.2,
        eave_buffer_m: 0.40,
        is_encroaching: false,
        encroachment_type: null,
        encroached_area_sqm: 0,
        iou_pct: 97.8,
        tps_rmse_cm: 3.4
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [73.85655, 18.52098],
          [73.85695, 18.52100],
          [73.85692, 18.52135],
          [73.85652, 18.52133],
          [73.85655, 18.52098]
        ]]
      },
      legacyGeometry: {
        type: "Polygon",
        coordinates: [[
          [73.85661, 18.52094],
          [73.85701, 18.52096],
          [73.85686, 18.52140],
          [73.85646, 18.52138],
          [73.85661, 18.52094]
        ]]
      }
    }
  ]
};

// Generate the full sector GeoJSON (AI Harmonized layer and Legacy layer)
export function getHarmonizedGeoJSON(featuresList = realWorldParcelsGeoJSON.features) {
  return {
    type: "FeatureCollection",
    features: featuresList.map(f => ({
      type: "Feature",
      id: f.id,
      properties: f.properties,
      geometry: f.geometry
    }))
  };
}

export function getLegacyGeoJSON(featuresList = realWorldParcelsGeoJSON.features) {
  return {
    type: "FeatureCollection",
    features: featuresList.map(f => ({
      type: "Feature",
      id: f.id,
      properties: {
        ...f.properties,
        isLegacyDistorted: true
      },
      geometry: f.legacyGeometry || f.geometry
    }))
  };
}

// Municipal Infrastructure Lines for Pune Shaniwar/Kasba Peth
export const municipalInfrastructureGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {
        id: "INFRA-DRAIN-01",
        name: "Shaniwar Peth Stormwater Drainage Canal",
        type: "Drainage",
        buffer_meters: 3.0
      },
      geometry: {
        type: "LineString",
        coordinates: [
          [73.85600, 18.52025],
          [73.85670, 18.52030],
          [73.85760, 18.52035]
        ]
      }
    },
    {
      type: "Feature",
      properties: {
        id: "INFRA-ROAD-14M",
        name: "Municipal 14m Public Right-of-Way Corridor",
        type: "Road_ROW",
        buffer_meters: 7.0
      },
      geometry: {
        type: "LineString",
        coordinates: [
          [73.85600, 18.52075],
          [73.85680, 18.52078],
          [73.85760, 18.52080]
        ]
      }
    }
  ]
};
