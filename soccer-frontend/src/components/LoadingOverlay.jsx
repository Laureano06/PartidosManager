import React from 'react';

// Overlay de carga para operaciones lentas (avanzar día, simular un tiempo,
// etc — llamadas que pueden tardar por la latencia de la base de datos).
// Se ve un anillo girando alrededor del logo del juego para que quede claro
// que se está procesando y no que la app se colgó.
export default function LoadingOverlay({ show, mensaje = 'Procesando...' }) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 z-50 bg-[#0b1326]/90 backdrop-blur-sm flex items-center justify-center">
      <div className="flex flex-col items-center gap-5">
        <div className="relative w-24 h-24 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-4 border-slate-800" />
          <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-sky-400 border-r-sky-400 animate-spin" />
          <img src="/iconoPARTIDOS.png" alt="" className="w-12 h-12 rounded-full object-cover" />
        </div>
        <p className="text-sm font-bold text-slate-200 animate-pulse">{mensaje}</p>
      </div>
    </div>
  );
}
