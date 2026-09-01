import React from 'react';

// SVGs propios (no emoji: en Windows se ven mal o rotos, sobre todo la de
// Inglaterra). Cubren las 7 nacionalidades que genera engine/data_gen.py.
const BANDERAS = {
  Argentina: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#74ACDF" />
      <rect width="30" height="6.67" y="6.67" fill="#fff" />
      <circle cx="15" cy="10" r="2" fill="#F6B40E" stroke="#85340A" strokeWidth="0.3" />
    </svg>
  ),
  Brasil: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#009739" />
      <polygon points="15,2.5 27,10 15,17.5 3,10" fill="#FEDD00" />
      <circle cx="15" cy="10" r="4.5" fill="#012169" />
    </svg>
  ),
  España: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#AA151B" />
      <rect width="30" height="10" y="5" fill="#F1BF00" />
    </svg>
  ),
  Inglaterra: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="20" fill="#fff" />
      <rect x="12" width="6" height="20" fill="#CE1124" />
      <rect y="7" width="30" height="6" fill="#CE1124" />
    </svg>
  ),
  Italia: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="10" height="20" fill="#009246" />
      <rect x="10" width="10" height="20" fill="#fff" />
      <rect x="20" width="10" height="20" fill="#CE2B37" />
    </svg>
  ),
  Francia: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="10" height="20" fill="#0055A4" />
      <rect x="10" width="10" height="20" fill="#fff" />
      <rect x="20" width="10" height="20" fill="#EF4135" />
    </svg>
  ),
  Alemania: (
    <svg viewBox="0 0 30 20" xmlns="http://www.w3.org/2000/svg">
      <rect width="30" height="6.67" fill="#000" />
      <rect width="30" height="6.67" y="6.67" fill="#DD0000" />
      <rect width="30" height="6.67" y="13.33" fill="#FFCE00" />
    </svg>
  ),
};

export default function Bandera({ pais, className = '' }) {
  const svg = BANDERAS[pais];
  if (!svg) return <span className={className}>{pais}</span>;
  return (
    <span
      title={pais}
      className={`inline-block w-5 h-[14px] rounded-[2px] overflow-hidden align-middle shrink-0 ring-1 ring-white/10 ${className}`}
    >
      {React.cloneElement(svg, { className: 'w-full h-full block' })}
    </span>
  );
}
