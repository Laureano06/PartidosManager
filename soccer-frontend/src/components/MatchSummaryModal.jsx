import React from 'react';
import Modal from './Modal';

const ETIQUETA = {
  GOL: { texto: 'GOL', clase: 'bg-emerald-500 text-slate-950' },
  TARJETA_AMARILLA: { texto: 'TA', clase: 'bg-amber-400 text-slate-950' },
  TARJETA_ROJA: { texto: 'TR', clase: 'bg-rose-500 text-white' },
  LESION: { texto: 'LES', clase: 'bg-rose-900 text-rose-200' },
  CAMBIO_TACTICO: { texto: 'TAC', clase: 'bg-sky-500 text-slate-950' },
};

export default function MatchSummaryModal({ resultado, open, onClose }) {
  if (!resultado) return null;
  const eventos = resultado.eventos || [];

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-3xl mx-auto space-y-6">
        <div className="text-center border-b border-slate-800 pb-6">
          <span className="text-xs text-slate-500 uppercase font-bold tracking-widest">Resultado Final</span>
          <h3 className="text-4xl font-black text-white mt-2">
            {resultado.nombre_local} {resultado.goles_local} - {resultado.goles_visitante} {resultado.nombre_visitante}
          </h3>
        </div>

        <div className="max-h-[50vh] overflow-y-auto scroll-slide space-y-2 pr-1">
          {eventos.length === 0 && (
            <p className="text-sm text-slate-500 text-center py-8">Sin eventos destacados.</p>
          )}
          {eventos.map((e, i) => (
            <div key={i} className="flex items-start gap-3 text-sm bg-[#0b1326] border border-slate-800/70 rounded-lg px-4 py-3">
              <span className="text-slate-500 font-bold w-10 shrink-0">{e.minuto}'</span>
              <span className={`shrink-0 text-[9px] font-black px-1.5 py-0.5 rounded mt-0.5 ${ETIQUETA[e.tipo]?.clase || 'bg-slate-800 text-slate-500'}`}>
                {ETIQUETA[e.tipo]?.texto || '•'}
              </span>
              <span className="text-slate-300">
                {e.jugador && <b className="text-slate-100">{e.jugador}: </b>}
                {e.texto || e.tipo}
              </span>
            </div>
          ))}
        </div>

        {resultado.mercado_ia && resultado.mercado_ia.length > 0 && (
          <div className="border-t border-slate-800 pt-4 space-y-1.5">
            <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider">Movimientos del mercado</h4>
            {resultado.mercado_ia.map((linea, i) => (
              <p key={i} className="text-xs text-slate-400">{linea}</p>
            ))}
          </div>
        )}

        <button onClick={onClose} className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm">
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
