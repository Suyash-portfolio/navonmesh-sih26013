import React from 'react';

/**
 * NAVONMESH identity mark.
 *
 * Reads as, in order of prominence at favicon size:
 *   1. a stack of layered GIS planes (the extruded bottom two edges)
 *   2. a subdivided cadastral parcel (the diamond face with its cross-join)
 *   3. connected survey nodes (the four vertices plus the centre control point)
 *
 * Deliberately not a brain, chat bubble or coin - it has to read as
 * survey / GIS / parcel integration.
 */
export default function NavonmeshLogo({ className = 'w-5 h-5', title = 'NAVONMESH' }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label={title}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Rear GIS plane */}
      <path
        d="M4 19.5 L16 13 L28 19.5 L16 26 Z"
        fill="#0D9488"
        fillOpacity="0.22"
        stroke="#0F766E"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      {/* Middle GIS plane */}
      <path
        d="M4 15.5 L16 9 L28 15.5 L16 22 Z"
        fill="#14B8A6"
        fillOpacity="0.26"
        stroke="#2DD4BF"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      {/* Top parcel face */}
      <path
        d="M4 11.5 L16 5 L28 11.5 L16 18 Z"
        fill="#14B8A6"
        fillOpacity="0.16"
        stroke="#34D399"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      {/* Parcel subdivision join */}
      <path
        d="M10 8.25 L22 14.75 M22 8.25 L10 14.75"
        stroke="#34D399"
        strokeWidth="1.1"
        strokeLinecap="round"
        strokeOpacity="0.75"
      />
      {/* Connected survey nodes */}
      <circle cx="4" cy="11.5" r="1.9" fill="#34D399" />
      <circle cx="28" cy="11.5" r="1.9" fill="#34D399" />
      <circle cx="16" cy="5" r="1.9" fill="#5EEAD4" />
      <circle cx="16" cy="18" r="1.5" fill="#0D9488" />
    </svg>
  );
}
