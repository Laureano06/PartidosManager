import React, { useEffect, useState } from 'react';

const ETIQUETA_DATASET = { ficticia: 'Base Ficticia', personalizada: 'Datos personalizados' };
const CLAVE_ULTIMA_PARTIDA = 'ultima_partida_id';

function formatearFecha(iso) {
  if (!iso) return '';
  // Si es solo fecha (sin hora), se ancla a medianoche LOCAL en vez de UTC
  // para que no se corra un día según el huso horario del navegador.
  const conHora = iso.includes('T') ? iso : `${iso}T00:00:00`;
  return new Date(conHora).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
}

// Fondo de la pantalla de inicio: la foto real (si el usuario la agrega en
// public/FondoPantallaInicial.jpg) se dibuja arriba de un degradé de estadio
// nocturno — si el archivo no existe, esa capa simplemente no se ve y queda
// el degradé solo, sin romper el layout ni necesitar lógica en JS.
const ESTILO_FONDO = {
  backgroundImage: [
    "url('/FondoPantallaInicial.jpg')",
    'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(56,189,248,0.15), transparent 60%)',
    'linear-gradient(180deg, #0b1326 0%, #060a16 100%)',
  ].join(', '),
  backgroundSize: 'cover, cover, cover',
  backgroundPosition: 'center, center, center',
  backgroundRepeat: 'no-repeat, no-repeat, no-repeat',
};

export default function InicioPage({ API_URL, onContinuar, onNuevaPartida, onAbrirEditor }) {
  const [vista, setVista] = useState('menu'); // 'menu' | 'nueva' | 'cargar'
  const [carreras, setCarreras] = useState(null);
  const [borrando, setBorrando] = useState(null);
  const [idAConfirmarBorrado, setIdAConfirmarBorrado] = useState(null);
  const [packs, setPacks] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/partidas`)
      .then((r) => r.json())
      .then(setCarreras)
      .catch((e) => { console.error('Error cargando carreras:', e); setCarreras([]); });
  }, [API_URL]);

  useEffect(() => {
    fetch(`${API_URL}/paquetes-clubes`)
      .then((r) => r.json())
      .then(setPacks)
      .catch((e) => { console.error('Error cargando Data Packs:', e); setPacks([]); });
  }, [API_URL]);

  const idUltimaPartida = (() => {
    try {
      const guardado = localStorage.getItem(CLAVE_ULTIMA_PARTIDA);
      return guardado ? Number(guardado) : null;
    } catch { return null; }
  })();
  const ultimaPartida = carreras?.find((c) => c.id_partida === idUltimaPartida) || null;

  const borrarCarrera = async (c) => {
    setBorrando(c.id_partida);
    try {
      await fetch(`${API_URL}/partidas/${c.id_partida}`, { method: 'DELETE' });
      setCarreras((prev) => prev.filter((x) => x.id_partida !== c.id_partida));
    } catch (error) {
      console.error('Error borrando la carrera:', error);
    } finally {
      setBorrando(null);
      setIdAConfirmarBorrado(null);
    }
  };

  return (
    <div className="min-h-screen text-slate-100 flex items-center justify-center p-6 font-sans" style={ESTILO_FONDO}>
      <div className="max-w-lg w-full bg-[#121e36]/95 border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-6">
        <div className="text-center space-y-2">
          <img src="/iconoPARTIDOS.png" alt="Logo" className="w-16 h-16 mx-auto rounded-2xl shadow-lg border border-sky-500/30 object-cover" />
          <h1 className="text-2xl font-black text-white">PARTIDOS <span className="text-sky-400">MANAGER</span></h1>
        </div>

        {vista === 'menu' && (
          <div className="space-y-3">
            {ultimaPartida && (
              <button
                onClick={() => onContinuar(ultimaPartida.id_partida)}
                className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 p-4 rounded-xl text-left transition flex justify-between items-center"
              >
                <div className="min-w-0">
                  <p className="text-[10px] font-black uppercase tracking-widest">Última partida</p>
                  <p className="font-bold text-sm truncate">{ultimaPartida.nombre_dt} — {ultimaPartida.nombre_equipo}</p>
                </div>
                <span className="font-black shrink-0 ml-3">Continuar ➔</span>
              </button>
            )}

            <button
              onClick={() => setVista('nueva')}
              className="w-full bg-[#0b1326] hover:bg-sky-950 border border-sky-500/40 p-4 rounded-xl text-left transition flex justify-between items-center"
            >
              <p className="font-bold text-sky-300 text-sm">Comenzar una nueva partida</p>
              <span>➔</span>
            </button>

            <button
              onClick={() => setVista('cargar')}
              className="w-full bg-[#0b1326] hover:bg-slate-800 border border-slate-700 p-4 rounded-xl text-left transition flex justify-between items-center"
            >
              <p className="font-bold text-slate-200 text-sm">Cargar partida</p>
              <span>➔</span>
            </button>

            <button
              onClick={onAbrirEditor}
              className="w-full bg-[#0b1326] hover:bg-slate-800 border border-slate-700 p-4 rounded-xl text-left transition flex justify-between items-center"
            >
              <div>
                <p className="font-bold text-slate-200 text-sm">Editor</p>
                <p className="text-[11px] text-slate-400">Cargá y gestioná paquetes de datos reales (clubes, jugadores, ligas).</p>
              </div>
              <span>➔</span>
            </button>
          </div>
        )}

        {vista === 'nueva' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white">Elegí con qué Data Pack jugar</h2>
              <button onClick={() => setVista('menu')} className="text-xs text-slate-400 hover:text-slate-300">← Volver</button>
            </div>

            {packs === null && <p className="text-sm text-slate-400 text-center py-6">Cargando Data Packs...</p>}

            {packs !== null && (
              <div className="space-y-2 max-h-96 overflow-y-auto scroll-slide pr-1">
                {packs.map((p) => (
                  <button
                    key={p.pack_id}
                    onClick={() => onNuevaPartida(p.tipo === 'PROCEDURAL' ? 'ficticia' : 'personalizada', p.id_paquete)}
                    className={`w-full p-4 rounded-xl text-left transition flex justify-between items-center border ${
                      p.tipo === 'PROCEDURAL' ? 'bg-[#0b1326] hover:bg-sky-950 border-sky-500/40' : 'bg-[#0b1326] hover:bg-sky-950 border-slate-700'
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="font-bold text-sm truncate">
                        <span className={p.tipo === 'PROCEDURAL' ? 'text-sky-300' : 'text-slate-200'}>{p.nombre}</span>
                        {p.es_oficial && <span className="ml-2 text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 align-middle">OFICIAL</span>}
                        {p.version && <span className="ml-2 text-[10px] text-slate-500 align-middle">v{p.version}</span>}
                      </p>
                      <p className="text-xs text-slate-400 truncate">{p.descripcion}</p>
                      {p.tipo !== 'PROCEDURAL' && (
                        <p className="text-[10px] text-slate-500 mt-0.5">
                          {p.numberOfClubs} clubes{p.numberOfPlayers ? ` · ${p.numberOfPlayers} jugadores reales` : ''} · {p.numberOfLeagues} ligas
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 ml-3">➔</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {vista === 'cargar' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white">Tus carreras</h2>
              <button onClick={() => setVista('menu')} className="text-xs text-slate-400 hover:text-slate-300">← Volver</button>
            </div>

            {carreras === null && <p className="text-sm text-slate-400 text-center py-6">Cargando carreras guardadas...</p>}

            {carreras !== null && (
              <div className="space-y-2 max-h-72 overflow-y-auto scroll-slide pr-1">
                {carreras.length === 0 && (
                  <p className="text-sm text-slate-400 text-center py-4">Todavía no tenés ninguna carrera guardada.</p>
                )}
                {carreras.map((c) => (
                  <div key={c.id_partida} className="w-full bg-[#0b1326] border border-slate-700 rounded-xl overflow-hidden">
                    <div
                      onClick={idAConfirmarBorrado === c.id_partida ? undefined : () => onContinuar(c.id_partida)}
                      onKeyDown={(e) => { if (idAConfirmarBorrado !== c.id_partida && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onContinuar(c.id_partida); } }}
                      role="button"
                      tabIndex={0}
                      aria-label={`Continuar carrera ${c.nombre_dt} — ${c.nombre_equipo}`}
                      className="hover:bg-sky-950 hover:border-sky-500/40 p-4 text-left transition flex justify-between items-center cursor-pointer focus-visible:outline focus-visible:outline-sky-500"
                    >
                      <div className="min-w-0">
                        <p className="font-bold text-white text-sm truncate">{c.nombre_dt} — {c.nombre_equipo}</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {ETIQUETA_DATASET[c.dataset] || c.dataset} · {formatearFecha(c.fecha_actual)} · creada el {formatearFecha(c.fecha_creacion)}
                        </p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          {c.cantidad_clubes} clubes · {c.cantidad_jugadores} jugadores
                        </p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 ml-3">
                        <span className="text-sky-400 text-xs font-bold">Continuar ➔</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); setIdAConfirmarBorrado(c.id_partida); }}
                          title="Borrar esta carrera"
                          className="text-rose-400 hover:text-rose-300 text-[11px] font-bold px-2 py-1 rounded-lg hover:bg-rose-950/60"
                        >
                          Borrar
                        </button>
                      </div>
                    </div>
                    {idAConfirmarBorrado === c.id_partida && (
                      <div className="bg-rose-950/40 border-t border-rose-500/40 p-3 flex items-center justify-between gap-3 flex-wrap">
                        <p className="text-xs text-rose-300">¿Borrar "{c.nombre_dt} — {c.nombre_equipo}"? No se puede deshacer.</p>
                        <div className="flex gap-2 shrink-0">
                          <button
                            onClick={() => borrarCarrera(c)}
                            disabled={borrando === c.id_partida}
                            className="bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-[11px]"
                          >
                            {borrando === c.id_partida ? 'Borrando...' : 'Sí, borrar'}
                          </button>
                          <button
                            onClick={() => setIdAConfirmarBorrado(null)}
                            disabled={borrando === c.id_partida}
                            className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 px-3 py-1.5 rounded-lg text-[11px]"
                          >
                            Cancelar
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
