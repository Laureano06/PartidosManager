import React, { useEffect, useState } from 'react';

const ETIQUETA_DATASET = { ficticia: 'Base Ficticia', personalizada: 'Datos personalizados' };

function formatearFecha(iso) {
  if (!iso) return '';
  // Si es solo fecha (sin hora), se ancla a medianoche LOCAL en vez de UTC
  // para que no se corra un día según el huso horario del navegador.
  const conHora = iso.includes('T') ? iso : `${iso}T00:00:00`;
  return new Date(conHora).toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function RoadmapPage({ API_URL, dataset, onContinuar, onCrearNueva, onCambiarDataset }) {
  const [carreras, setCarreras] = useState(null);
  const [borrando, setBorrando] = useState(null); // id_partida en proceso de borrado

  useEffect(() => {
    fetch(`${API_URL}/partidas?dataset=${dataset}`)
      .then((r) => r.json())
      .then(setCarreras)
      .catch((e) => { console.error('Error cargando carreras:', e); setCarreras([]); });
  }, [API_URL, dataset]);

  const borrarCarrera = async (e, c) => {
    e.stopPropagation();
    if (!window.confirm(`¿Borrar la carrera "${c.nombre_dt} — ${c.nombre_equipo}"? Esta acción no se puede deshacer.`)) return;
    setBorrando(c.id_partida);
    try {
      await fetch(`${API_URL}/partidas/${c.id_partida}`, { method: 'DELETE' });
      setCarreras((prev) => prev.filter((x) => x.id_partida !== c.id_partida));
    } catch (error) {
      console.error('Error borrando la carrera:', error);
    } finally {
      setBorrando(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-lg w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-sky-400 font-bold uppercase">{ETIQUETA_DATASET[dataset] || dataset}</p>
            <h1 className="text-xl font-black text-white mt-1">Hoja de ruta</h1>
          </div>
          <button onClick={onCambiarDataset} className="text-xs text-slate-500 hover:text-slate-300">Cambiar datos</button>
        </div>

        {carreras === null && <p className="text-sm text-slate-400 text-center py-6">Cargando carreras guardadas...</p>}

        {carreras !== null && (
          <div className="space-y-2 max-h-72 overflow-y-auto scroll-slide pr-1">
            {carreras.length === 0 && (
              <p className="text-sm text-slate-500 text-center py-4">Todavía no tenés ninguna carrera con estos datos.</p>
            )}
            {carreras.map((c) => (
              <div
                key={c.id_partida}
                onClick={() => onContinuar(c.id_partida)}
                className="w-full bg-[#0b1326] hover:bg-sky-950 border border-slate-700 hover:border-sky-500/40 p-4 rounded-xl text-left transition flex justify-between items-center cursor-pointer"
              >
                <div className="min-w-0">
                  <p className="font-bold text-white text-sm truncate">{c.nombre_dt} — {c.nombre_equipo}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {formatearFecha(c.fecha_actual)} · creada el {formatearFecha(c.fecha_creacion)}
                  </p>
                  <p className="text-[10px] text-slate-600 mt-0.5">
                    {c.cantidad_clubes} clubes · {c.cantidad_jugadores} jugadores
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-3">
                  <span className="text-sky-400 text-xs font-bold">Continuar ➔</span>
                  <button
                    onClick={(e) => borrarCarrera(e, c)}
                    disabled={borrando === c.id_partida}
                    title="Borrar esta carrera"
                    className="text-rose-400 hover:text-rose-300 disabled:opacity-40 text-[11px] font-bold px-2 py-1 rounded-lg hover:bg-rose-950/60"
                  >
                    {borrando === c.id_partida ? '...' : 'Borrar'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <button
          onClick={onCrearNueva}
          className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
        >
          + Crear carrera nueva
        </button>
      </div>
    </div>
  );
}
