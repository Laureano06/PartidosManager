import React, { useEffect, useState } from 'react';

export function faceUrl(player, API_URL = 'http://127.0.0.1:8000') {
  const data = player?.datos_pack || player || {};
  const url = player?.foto_url || data.foto_url || data.datos_fuente?.image;
  if (typeof url !== 'string' || !url) return null;
  if (url.startsWith('/static/')) return `${API_URL}${url}`;
  return /^https?:\/\//.test(url) ? url : null;
}

export default function PlayerFace({ player, API_URL, className = '', ...props }) {
  const url = faceUrl(player, API_URL);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  return <span className={`player-face ${className}`} {...props}>
    {url && !failed ? <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} /> :
      <svg viewBox="0 0 100 110" aria-hidden="true"><circle cx="50" cy="34" r="23" /><path d="M7 110V91C7 60 93 60 93 91V110Z" /></svg>}
  </span>;
}
