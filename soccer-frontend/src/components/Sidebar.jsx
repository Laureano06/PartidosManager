import React, { useEffect, useState } from 'react';
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

// Secciones agrupadas: la carrera del usuario (siempre atada a su propio
// club) separada de las pantallas de gestión (que operan sobre `clubActivo`,
// que puede ser un club afiliado) — antes era una lista plana de 13 ítems
// sin ninguna jerarquía.
const SECCIONES_MENU = [
  {
    titulo: 'Tu carrera',
    items: [
      { path: '/panel', label: 'Panel de Control' },
      { path: '/calendario', label: 'Calendario' },
      { path: '/multiclub', label: 'Multiclub' },
      { path: '/directiva', label: 'Directiva' },
    ],
  },
  {
    titulo: 'Gestión de club',
    items: [
      { path: '/equipo', label: 'Plantel del Equipo' },
      { path: '/tacticas', label: 'Tácticas' },
      { path: '/transferencias', label: 'Transferencias' },
      { path: '/mercado', label: 'Sala de Fichajes' },
      { path: '/desarrollo', label: 'Centro de Desarrollo' },
      { path: '/academia', label: 'Academia' },
      { path: '/cuerpo-tecnico', label: 'Cuerpo Técnico' },
      { path: '/economia', label: 'Economía' },
    ],
  },
  {
    titulo: 'Experimental',
    items: [
      { path: '/jugar', label: 'Motor Jugable (prototipo)' },
    ],
  },
];

function SidebarContenido({
  nombreClub, escudoUrl, afiliadosPipeline, clubActivo, idEquipoUsuario, setClubActivo,
  presupuesto, confianzaDirectiva, cambiarDeCarrera, volverAlInicio, onNavegar, idSelectorGestion,
}) {
  const navLinkClase = ({ isActive }) =>
    `w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-bold text-xs transition text-left ${
      isActive
        ? 'bg-sky-500 text-slate-950 shadow-md'
        : 'text-slate-300 hover:bg-[#0b1326] hover:text-white'
    }`;

  return (
    <>
      <div className="space-y-3">
        {nombreClub && (
          <div className="flex items-center gap-2.5 px-2 pb-3 border-b border-slate-800">
            <EscudoClub nombreClub={nombreClub} escudoUrl={escudoUrl} />
            <p className="text-xs font-bold text-white leading-tight truncate">{nombreClub}</p>
          </div>
        )}
        {afiliadosPipeline.length > 0 && setClubActivo && (
          <div className="px-2 pb-3 border-b border-slate-800">
            <label htmlFor={idSelectorGestion} className="text-[10px] text-slate-400 block mb-1">Gestionando</label>
            <select
              id={idSelectorGestion}
              value={clubActivo || ''}
              onChange={(e) => setClubActivo(Number(e.target.value))}
              className="w-full bg-[#0b1326] border border-slate-700 text-xs text-white px-2 py-1.5 rounded-lg font-bold"
            >
              <option value={idEquipoUsuario}>{nombreClub} (tu club)</option>
              {afiliadosPipeline.map((a) => (
                <option key={a.id_equipo} value={a.id_equipo}>{a.nombre}</option>
              ))}
            </select>
          </div>
        )}
        {SECCIONES_MENU.map((seccion) => (
          <div key={seccion.titulo} className="space-y-1">
            <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">{seccion.titulo}</p>
            {seccion.items.map((item) => (
              <NavLink key={item.path} to={item.path} className={navLinkClase} onClick={onNavegar}>
                {item.label}
              </NavLink>
            ))}
          </div>
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
            className="w-full text-left text-[10px] text-slate-400 hover:text-slate-200 mt-3 pt-2 border-t border-slate-800"
          >
            Cambiar de carrera
          </button>
        )}
        {volverAlInicio && (
          <button
            onClick={volverAlInicio}
            className="w-full text-left text-[10px] text-slate-400 hover:text-slate-200 mt-1"
          >
            Volver al inicio
          </button>
        )}
      </div>
    </>
  );
}

export default function Sidebar({ presupuesto, nombreClub, escudoUrl, confianzaDirectiva, cambiarDeCarrera, volverAlInicio, API_URL, idEquipoUsuario, clubActivo, setClubActivo }) {
  const [afiliadosPipeline, setAfiliadosPipeline] = useState([]);
  const [menuMovilAbierto, setMenuMovilAbierto] = useState(false);

  useEffect(() => {
    if (!API_URL || !idEquipoUsuario) return;
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/multiclub`)
      .then((r) => r.json())
      .then((mc) => {
        const propios = (mc.tus_participaciones || []).filter((a) => a.pipeline_habilitado && a.influencia_habilitada);
        setAfiliadosPipeline(propios);
      })
      .catch(() => {});
  }, [API_URL, idEquipoUsuario, clubActivo]);

  // Debajo de 640px el <aside> desaparece del todo (ver className del
  // <aside>) — sin este menú no habría ninguna forma de navegar entre
  // pantallas en un viewport de celular.
  useEffect(() => {
    if (!menuMovilAbierto) return;
    const onKey = (e) => { if (e.key === 'Escape') setMenuMovilAbierto(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuMovilAbierto]);

  const contenidoProps = {
    nombreClub, escudoUrl, afiliadosPipeline, clubActivo, idEquipoUsuario, setClubActivo,
    presupuesto, confianzaDirectiva, cambiarDeCarrera, volverAlInicio,
  };

  return (
    <>
      <button
        onClick={() => setMenuMovilAbierto(true)}
        aria-label="Abrir menú de navegación"
        aria-expanded={menuMovilAbierto}
        className="sm:hidden fixed top-3 left-3 z-[60] bg-[#121e36] border border-slate-700 text-white w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
      >
        <span aria-hidden="true" className="text-lg leading-none">☰</span>
      </button>

      <aside className="w-64 bg-[#121e36]/90 border-r border-slate-800 p-4 flex-col justify-between hidden sm:flex overflow-y-auto scroll-slide">
        <SidebarContenido {...contenidoProps} idSelectorGestion="sidebar-gestionando" />
      </aside>

      {menuMovilAbierto && (
        <div className="sm:hidden fixed inset-0 z-[60] flex" onClick={() => setMenuMovilAbierto(false)}>
          <div className="absolute inset-0 bg-black/70" />
          <nav
            aria-label="Navegación principal"
            className="relative w-72 max-w-[85vw] h-full bg-[#121e36] border-r border-slate-800 flex flex-col overflow-y-auto scroll-slide"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between p-4 pb-0">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Menú</span>
              <button
                onClick={() => setMenuMovilAbierto(false)}
                aria-label="Cerrar menú de navegación"
                className="text-slate-400 hover:text-white text-xl leading-none w-8 h-8 flex items-center justify-center"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 flex flex-col justify-between p-4 pt-3">
              <SidebarContenido {...contenidoProps} onNavegar={() => setMenuMovilAbierto(false)} idSelectorGestion="sidebar-movil-gestionando" />
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
