import React, { useEffect, useState } from 'react';
import Modal from './Modal';

export default function OfrecerJugadorModal({ jugador, open, onClose, API_URL, idEquipoUsuario, idPartida, onResuelto }) {
  const [equipos, setEquipos] = useState([]);
  const [modo, setModo] = useState('todos'); // 'todos' | 'elegir'
  const [seleccionados, setSeleccionados] = useState(new Set());
  const [filtroClub, setFiltroClub] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);

  useEffect(() => {
    if (!open) return;
    setModo('todos');
    setSeleccionados(new Set());
    setFiltroClub('');
    setResultado(null);
    if (!idPartida) return;
    fetch(`${API_URL}/equipos?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((data) => setEquipos(data.filter((e) => e.id_equipo !== idEquipoUsuario)))
      .catch((e) => console.error('Error cargando equipos:', e));
  }, [open, API_URL, idEquipoUsuario, idPartida]);

  if (!jugador) return null;

  const toggleEquipo = (id) => {
    setSeleccionados((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const clubesFiltrados = equipos.filter((e) => e.nombre.toLowerCase().includes(filtroClub.toLowerCase()));

  const enviar = async () => {
    if (modo === 'elegir' && seleccionados.size === 0) return;
    setEnviando(true);
    try {
      const res = await fetch(`${API_URL}/fichajes/ofrecer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_jugador: jugador.id_jugador,
          id_equipos: modo === 'elegir' ? Array.from(seleccionados) : null,
        }),
      });
      const data = await res.json();
      setResultado(data);
      if (onResuelto) onResuelto();
    } catch (error) {
      console.error('Error ofreciendo el jugador:', error);
      setResultado({ mensaje: 'No se pudo conectar con el servidor.', ofertas_recibidas: [], sin_interes: [] });
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-xl mx-auto space-y-6">
        <div>
          <h3 className="text-2xl font-bold text-white">Ofrecer a {jugador.nombre}</h3>
          <p className="text-sm text-slate-400 mt-1">Cada club evalúa por su cuenta si le interesa — puede que ninguno ofrezca nada.</p>
        </div>

        {!resultado ? (
          <div className="space-y-4 text-sm">
            <div className="flex gap-3">
              <button
                onClick={() => setModo('todos')}
                className={`flex-1 px-3 py-2.5 rounded-xl font-bold text-xs ${modo === 'todos' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
              >
                Ofrecer a todos los rivales
              </button>
              <button
                onClick={() => setModo('elegir')}
                className={`flex-1 px-3 py-2.5 rounded-xl font-bold text-xs ${modo === 'elegir' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
              >
                Elegir equipos puntuales
              </button>
            </div>

            {modo === 'elegir' && (
              <div className="space-y-2">
                <input
                  type="text"
                  value={filtroClub}
                  onChange={(e) => setFiltroClub(e.target.value)}
                  placeholder="Buscar club..."
                  className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-white text-xs"
                />
                <div className="max-h-56 overflow-y-auto scroll-slide space-y-1 border border-slate-800 rounded-xl p-2">
                  {clubesFiltrados.map((e) => (
                    <label key={e.id_equipo} className="flex items-center gap-2 text-xs px-2 py-1.5 rounded-lg hover:bg-[#0b1326] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={seleccionados.has(e.id_equipo)}
                        onChange={() => toggleEquipo(e.id_equipo)}
                        className="accent-sky-500"
                      />
                      <span className="text-slate-200">{e.nombre}</span>
                    </label>
                  ))}
                  {clubesFiltrados.length === 0 && <p className="text-xs text-slate-600 p-2">Sin resultados.</p>}
                </div>
                <p className="text-[11px] text-slate-500">{seleccionados.size} club(es) seleccionados.</p>
              </div>
            )}

            <button
              onClick={enviar}
              disabled={enviando || (modo === 'elegir' && seleccionados.size === 0)}
              className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl w-full"
            >
              {enviando ? 'Ofreciendo...' : 'Ofrecer jugador ➔'}
            </button>
          </div>
        ) : (
          <div className="space-y-4 text-sm">
            <div className="p-4 rounded-xl border bg-sky-950/60 border-sky-500/40 text-sky-300">
              <p>{resultado.mensaje}</p>
            </div>

            {resultado.ofertas_recibidas?.length > 0 && (
              <div>
                <p className="text-xs font-bold text-emerald-400 uppercase mb-2">Ofertas recibidas</p>
                <div className="space-y-1.5">
                  {resultado.ofertas_recibidas.map((o) => (
                    <div key={o.id_equipo} className="flex justify-between text-xs bg-[#0b1326] border border-emerald-500/30 rounded-lg px-3 py-2">
                      <span className="text-slate-200">{o.nombre}</span>
                      <span className="font-bold text-emerald-400">${o.monto_oferta.toLocaleString('es-AR')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {resultado.sin_interes?.length > 0 && (
              <div>
                <p className="text-xs font-bold text-slate-500 uppercase mb-2">Sin interés</p>
                <div className="space-y-1.5 max-h-40 overflow-y-auto scroll-slide">
                  {resultado.sin_interes.map((o) => (
                    <div key={o.id_equipo} className="flex justify-between text-xs bg-[#0b1326] border border-slate-800 rounded-lg px-3 py-2">
                      <span className="text-slate-400">{o.nombre}</span>
                      <span className="text-slate-600">{o.motivo}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button onClick={onClose} className="w-full bg-slate-800 text-slate-300 px-3 py-2.5 rounded-lg">
              Cerrar
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
