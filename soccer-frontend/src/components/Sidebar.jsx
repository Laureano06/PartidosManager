import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';

function EscudoClub({ nombreClub, escudoUrl }) {
  const [fallo, setFallo] = useState(false);
  const inicial = (nombreClub || '?').replace(/^.*-\s*/, '').trim().charAt(0).toUpperCase() || '?';

  if (escudoUrl && !fallo) {
    return (
      <img
        src={escudoUrl}
        alt={nombreClub}
        onError={() => setFallo(true)}
        className="w-9 h-9 rounded-lg object-contain bg-[#0b1326] border border-slate-800 shrink-0"
      />
    );
  }
  return (
    <div className="w-9 h-9 rounded-lg bg-sky-950 border border-sky-500/40 text-sky-300 font-black text-sm flex items-center justify-center shrink-0">
      {inicial}
    </div>
  );
}

export default function Sidebar({ presupuesto, nombreClub, escudoUrl, confianzaDirectiva, cambiarDeCarrera, volverAlInicio }) {
  const menuItems = [
    { path: '/panel', label: 'Panel de Control' },
    { path: '/calendario', label: 'Calendario' },
    { path: '/equipo', label: 'Plantel del Equipo' },
    { path: '/tacticas', label: 'Tácticas' },
    { path: '/transferencias', label: 'Transferencias' },
    { path: '/mercado', label: 'Sala de Fichajes' },
    { path: '/desarrollo', label: 'Centro de Desarrollo' },
    { path: '/academia', label: 'Academia' },
    { path: '/cuerpo-tecnico', label: 'Cuerpo Técnico' },
    { path: '/multiclub', label: 'Multiclub' },
    { path: '/economia', label: 'Economía' },
    { path: '/directiva', label: 'Directiva' },
    { path: '/jugar', label: 'Motor Jugable (proto)' },
  ];

  return (
    <aside className="w-64 bg-[#121e36]/90 border-r border-slate-800 p-4 flex flex-col justify-between hidden sm:flex overflow-y-auto scroll-slide">
      <div className="space-y-1">
        {nombreClub && (
          <div className="flex items-center gap-2.5 px-2 pb-3 mb-2 border-b border-slate-800">
            <EscudoClub nombreClub={nombreClub} escudoUrl={escudoUrl} />
            <p className="text-xs font-bold text-white leading-tight truncate">{nombreClub}</p>
          </div>
        )}
        {menuItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-bold text-xs transition text-left ${
                isActive
                  ? 'bg-sky-500 text-slate-950 shadow-md'
                  : 'text-slate-300 hover:bg-[#0b1326] hover:text-white'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </div>

      <div className="p-3 bg-[#0b1326] rounded-xl border border-slate-800 text-xs space-y-1">
        <p className="text-slate-400">Presupuesto:</p>
        <p className="font-bold text-sky-400">${presupuesto.toLocaleString('es-AR')}</p>
        <p className="text-slate-400 mt-2">Confianza Junta:</p>
        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
          <div className="bg-sky-400 h-full" style={{ width: `${confianzaDirectiva}%` }} />
        </div>
        {cambiarDeCarrera && (
          <button
            onClick={cambiarDeCarrera}
            className="w-full text-left text-[10px] text-slate-500 hover:text-slate-300 mt-3 pt-2 border-t border-slate-800"
          >
            Cambiar de carrera
          </button>
        )}
        {volverAlInicio && (
          <button
            onClick={volverAlInicio}
            className="w-full text-left text-[10px] text-slate-500 hover:text-slate-300 mt-1"
          >
            Volver al inicio
          </button>
        )}
      </div>
    </aside>
  );
}