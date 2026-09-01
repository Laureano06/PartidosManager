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
export default function DialogoJugadorModal({ jugador, open, onClose, API_URL, idEquipoInteresado }) {
  const [intercambios, setIntercambios] = useState([]);
  const [interes, setInteres] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (open) { setIntercambios([]); setInteres(null); }
  }, [open, jugador?.id_jugador]);

  if (!jugador) return null;

  const preguntar = async (tema) => {
    setCargando(true);
    try {
      const res = await fetch(
        `${API_URL}/jugadores/${jugador.id_jugador}/dialogo?id_equipo_interesado=${idEquipoInteresado}&tema=${tema}`
      );
      const data = await res.json();
      if (!res.ok) return;
      setInteres(data.interes);
      setIntercambios((prev) => [...prev, { pregunta: TEMAS.find((t) => t.key === tema)?.label, frase: data.frase }]);
    } catch (error) {
      console.error('Error consultando al jugador:', error);
    } finally {
      setCargando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-xl mx-auto space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-2xl font-bold text-white">Hablar con {jugador.nombre}</h3>
            <p className="text-xs text-slate-500 mt-1">Solo consulta — no compromete ninguna oferta.</p>
          </div>
          {interes && (
            <span className={`text-xs font-bold px-3 py-1 rounded-full border shrink-0 ${INTERES_CLASS[interes]}`}>
              {INTERES_LABEL[interes] || interes}
            </span>
          )}
        </div>

        <div className="space-y-3 min-h-[80px]">
          {intercambios.length === 0 && (
            <p className="text-sm text-slate-500 italic">Elegí un tema para empezar la charla.</p>
          )}
          {intercambios.map((ex, i) => (
            <div key={i} className="space-y-1.5">
              <p className="text-xs text-sky-400 font-bold">{ex.pregunta}</p>
              <div className="bg-[#0b1326] border border-slate-800 rounded-2xl rounded-tl-none p-3.5 text-sm text-slate-200">
                "{ex.frase}"
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
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

        <button onClick={onClose} className="w-full bg-slate-800 text-slate-300 px-3 py-2.5 rounded-lg text-sm">
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
