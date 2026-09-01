import React from 'react';

export default function DbSelectorPage({ onSelectDataset }) {
  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6 font-sans">
      <div className="max-w-md w-full bg-[#121e36] border border-slate-700/60 rounded-3xl p-8 shadow-2xl text-center space-y-6">
        <img src="/iconoPARTIDOS.png" alt="Logo" className="w-20 h-20 mx-auto rounded-2xl shadow-lg border border-sky-500/30 object-cover" />
        <div>
          <h1 className="text-2xl font-black text-white">PARTIDOS <span className="text-sky-400">SOCCER MANAGER</span></h1>
          <p className="text-xs text-slate-400 mt-1">Elegí con qué datos jugar</p>
        </div>

        <div className="space-y-3">
          <button
            onClick={() => onSelectDataset('ficticia')}
            className="w-full bg-[#0b1326] hover:bg-sky-950 border border-sky-500/40 p-4 rounded-xl text-left transition flex justify-between items-center"
          >
            <div>
              <p className="font-bold text-sky-300 text-sm">Base Ficticia</p>
              <p className="text-xs text-slate-400">Ligas, clubes y jugadores generados automáticamente. Sin nombres reales.</p>
            </div>
            <span>➔</span>
          </button>

          <button
            onClick={() => onSelectDataset('personalizada')}
            className="w-full bg-[#0b1326] hover:bg-sky-950 border border-slate-700 p-4 rounded-xl text-left transition flex justify-between items-center"
          >
            <div>
              <p className="font-bold text-slate-200 text-sm">Datos personalizados</p>
              <p className="text-xs text-slate-400">Subís tu propia lista de nombres de club (los jugadores igual se generan).</p>
            </div>
            <span>➔</span>
          </button>
        </div>

        <p className="text-[10px] text-slate-600">
          Cada set de datos puede tener varias carreras guardadas en paralelo.
        </p>
      </div>
    </div>
  );
}
