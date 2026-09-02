import React, { useMemo } from 'react';
import { FORMACIONES_SLOTS } from '../utils/formaciones';

// Posición genérica (x=centro, y por línea) para cuando la posición
// específica del jugador no aparece en ninguna de las formaciones
// conocidas (por ejemplo, categorías juveniles con datos incompletos).
const Y_GENERICO = { POR: 8, DEF: 25, MED: 50, DEL: 80 };

function coordenadas(posicion, posicionEspecifica) {
  if (posicionEspecifica) {
    for (const slots of Object.values(FORMACIONES_SLOTS)) {
      const slot = slots.find((s) => s.posEspecifica === posicionEspecifica);
      if (slot) return { x: slot.x, y: slot.y };
    }
  }
  return { x: 50, y: Y_GENERICO[posicion] ?? 50 };
}

export default function MiniPitchPosicion({ posicion, posicionEspecifica }) {
  const { x, y } = useMemo(() => coordenadas(posicion, posicionEspecifica), [posicion, posicionEspecifica]);

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-3 relative overflow-hidden aspect-[3/4] w-full max-w-[160px]">
      <div className="absolute inset-2 border-2 border-emerald-800/40 rounded-lg" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-1/2 aspect-square rounded-full border-2 border-emerald-800/40" />
      <div className="absolute left-1/2 top-[8%] -translate-x-1/2 w-1/3 h-[8%] border-2 border-t-0 border-emerald-800/40" />
      <div className="absolute left-1/2 bottom-[8%] -translate-x-1/2 w-1/3 h-[8%] border-2 border-b-0 border-emerald-800/40" />

      <div style={{ left: `${x}%`, top: `${y}%` }} className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center">
        <div className="w-4 h-4 rounded-full bg-sky-500 border-2 border-sky-300 shadow-[0_0_8px_rgba(56,189,248,0.7)]" />
        {posicionEspecifica && (
          <span className="mt-1 text-[9px] font-black text-sky-300 bg-[#0b1326]/90 px-1 rounded">{posicionEspecifica}</span>
        )}
      </div>
    </div>
  );
}
