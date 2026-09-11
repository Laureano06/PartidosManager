import PlayerFace from './PlayerFace';
import React, { useEffect, useState } from 'react';
import Modal from './Modal';

const TEMAS = [
  { key: 'club', label: '¿Cómo te sentís en el club?' },
  { key: 'continuidad', label: '¿Seguirías acá / te sumarías?' },
  { key: 'futuro', label: '¿Qué esperás a futuro?' },
];

const INTERES_LABEL = { alto: 'Muy abierto', medio: 'Tibio', bajo: 'Poco convencido' };
const INTERES_CLASS = {
  alto: 'bg-emerald-950 text-emerald-400 border-emerald-500/40',
  medio: 'bg-amber-950 text-amber-400 border-amber-500/40',
  bajo: 'bg-rose-950 text-rose-400 border-rose-500/40',
};

// "Hablar con el jugador": consulta de solo lectura (no gasta ninguna ronda
// de negociación real) — mismo dato que ya usan los modals de negociación,
// pero acá se puede tantear ANTES de comprometer una oferta. idEquipoInteresado
// es el club del usuario: si coincide con el club actual del jugador, el
// backend responde sobre RENOVAR; si es otro club, sobre SUMARSE ahí.
export default function DialogoJugadorModal({ jugador, open, onClose, API_URL, idEquipoInteresado, onActualizado }) {
  const [intercambios, setIntercambios] = useState([]);
  const [error, setError] = useState(null);
  const [interes, setInteres] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (open) { setIntercambios([]); setInteres(null); }
  }, [open, jugador?.id_jugador]);

  useEffect(() => {
    if (!open || !jugador || jugador.id_equipo !== idEquipoInteresado) return;
    const controller = new AbortController();
    fetch(`${API_URL}/jugadores/${jugador.id_jugador}/conversaciones?id_equipo=${idEquipoInteresado}`, { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error('No se pudo cargar el historial'); return r.json(); })
      .then((rows) => setIntercambios(rows.map((r) => ({ ...r, pregunta: r.tema }))))
      .catch((e) => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [open, jugador?.id_jugador, idEquipoInteresado, API_URL]);

  const conversar = async (tema, pregunta) => {
    setCargando(true); setError(null);
    try {
      const r = await fetch(`${API_URL}/jugadores/${jugador.id_jugador}/conversaciones`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id_equipo: idEquipoInteresado, tema }) });
      const data = await r.json(); if (!r.ok) throw new Error(data.detail || 'No se pudo conversar');
      setIntercambios((prev) => [...prev, { ...data, pregunta }]);
      onActualizado?.(data);
    } catch (e) { setError(e.message); } finally { setCargando(false); }
  };

  if (!jugador) return null;

  const preguntar = async (tema) => {
    setCargando(true);
    try {
      const res = await fetch(
        `${API_URL}/jugadores/${jugador.id_jugador}/dialogo?id_equipo_interesado=${idEquipoInteresado}&tema=${tema}`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'No se pudo consultar al jugador');
      setInteres(data.interes);
      setIntercambios((prev) => [...prev, { pregunta: TEMAS.find((t) => t.key === tema)?.label, frase: data.frase }]);
    } catch (error) {
      setError(error.message || 'Error de conexión');
    } finally {
      setCargando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="fm-conversation">
        <div className="flex items-center gap-5"><PlayerFace player={jugador} API_URL={API_URL} className="editor-face" />
          <div>
            <h3 className="text-2xl font-bold text-white">Hablar con {jugador.nombre}</h3>
            <p className="text-xs text-slate-500 mt-1">Las consultas son informativas. Las charlas de vestuario afectan la moral una vez por día.</p>
          </div>
          {interes && (
            <span className={`text-xs font-bold px-3 py-1 rounded-full border shrink-0 ${INTERES_CLASS[interes]}`}>
              {INTERES_LABEL[interes] || interes}
            </span>
          )}
        </div>

        <div className="fm-conversation-history space-y-3" aria-live="polite">
          {intercambios.length === 0 && (
            <p className="text-sm text-slate-500 italic">Elegí un tema para empezar la charla.</p>
          )}
          {intercambios.map((ex, i) => (
            <div key={i} className="space-y-1.5">
              <p className="text-xs text-sky-400 font-bold">{ex.pregunta}</p>
              <div className="bg-[#0b1326] border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-sm text-slate-200">
                {ex.frase}{ex.delta_moral != null && <p className="text-xs text-sky-300 mt-2">Moral: {ex.delta_moral > 0 ? '+' : ''}{ex.delta_moral} · {ex.fecha}</p>}
              </div>
            </div>
          ))}
        </div>

        <div className="fm-conversation-options gap-2 pt-2 border-t border-slate-800">
          <h4 className="font-bold mb-2">Consultas</h4>
          {TEMAS.map((t) => (
            <button
              key={t.key}
              onClick={() => preguntar(t.key)}
              disabled={cargando}
              className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 text-xs font-bold px-3 py-2 rounded-lg"
            >
              {t.label}
            </button>
          ))}
        </div>

        {jugador.id_equipo === idEquipoInteresado && <div className="fm-panel">
          <h4>Charla de vestuario</h4><p className="text-xs text-slate-400 mb-4">El efecto depende de su moral y su estado físico. Hablar de descanso no modifica el entrenamiento.</p>
          {[["apoyar", "Transmitir confianza"], ["exigir", "Exigir más compromiso"], ["descanso", "Consultar el cansancio"]].map(([tema, label]) => <button key={tema} disabled={cargando} onClick={() => conversar(tema, label)} className="block w-full text-left bg-slate-800 hover:bg-slate-700 disabled:opacity-50 p-3 my-2">{label}</button>)}
        </div>}
        {error && <p role="alert" className="text-rose-300">{error}</p>}
        <button onClick={onClose} className="w-full bg-slate-800 text-slate-300 px-3 py-2.5 rounded-lg text-sm">
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
