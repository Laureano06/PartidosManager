import React from 'react';
import { Link } from 'react-router-dom';
import CanchaJugable from '../components/CanchaJugable';

export default function JugarPage() {
  return (
    <div className="h-full min-h-0 flex flex-col gap-4">
      <div className="shrink-0">
        <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
        <h1 className="text-lg font-black text-white mt-1">Motor Jugable (prototipo)</h1>
        <p className="text-[11px] text-slate-400 mt-1">
          Primer paso de un motor en tiempo real, separado de la cancha 3D del partido: acá solo se prueba el
          movimiento de un jugador (aceleración, frenado, sprint), sin pelota ni IA todavía. El resto del plantel
          está parado de referencia.
        </p>
      </div>

      <div className="flex-1 min-h-[320px] bg-[#121e36] border border-slate-800 rounded-2xl p-2">
        <CanchaJugable />
      </div>

      <div className="shrink-0 bg-[#121e36] border border-slate-800 rounded-2xl p-4 flex flex-wrap gap-4 text-xs text-slate-400">
        <span><span className="text-sky-400 font-bold">W A S D</span> — moverse</span>
        <span><span className="text-sky-400 font-bold">Shift</span> — sprint</span>
      </div>
    </div>
  );
}
