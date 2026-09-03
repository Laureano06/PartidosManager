import React, { useEffect, useRef, useState } from 'react';

export default function Header({ fechaActual, diaNumero, avanzarDia, esDiaDePartido, simularHasta, resultadoSimulacion }) {
  const [mostrarSelector, setMostrarSelector] = useState(false);
  const [fechaElegida, setFechaElegida] = useState('');
  const popoverRef = useRef(null);

  // Cierra con click afuera o Escape — presente en cada pantalla de la app,
  // así que sin esto quedaba como el único popover del proyecto sin ninguna
  // de las dos formas estándar de descartarlo.
  useEffect(() => {
    if (!mostrarSelector) return;
    const onPointerDown = (e) => { if (popoverRef.current && !popoverRef.current.contains(e.target)) setMostrarSelector(false); };
    const onKey = (e) => { if (e.key === 'Escape') setMostrarSelector(false); };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [mostrarSelector]);

  const formatearFecha = (date) => {
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
  };

  const fechaMinima = new Date(fechaActual.getTime() + 86400000).toISOString().slice(0, 10);

  const confirmarSimulacion = async () => {
    if (!fechaElegida || !simularHasta) return;
    await simularHasta(fechaElegida);
    setMostrarSelector(false);
  };

  return (
    <header className="bg-[#121e36] border-b border-slate-800 p-3 sticky top-0 z-50 flex justify-between items-center px-6">
      <div className="flex items-center gap-3">
        <img src="/iconoPARTIDOS.png" alt="Logo" className="w-8 h-8 rounded-lg border border-sky-500/30 object-cover" />
        <span className="font-black text-white text-sm tracking-wider">
          PARTIDOS <span className="text-sky-400 text-xs">MANAGER</span>
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-xs text-sky-400 font-bold">{formatearFecha(fechaActual)}</p>
          <p className="text-[10px] text-slate-400">Día {diaNumero} de Gestión</p>
        </div>

        <button
          onClick={avanzarDia}
          disabled={esDiaDePartido}
          className={`font-black px-5 py-2 rounded-xl text-xs uppercase tracking-wider transition shadow-lg ${
            esDiaDePartido
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
              : 'bg-sky-500 hover:bg-sky-400 text-slate-950 shadow-sky-950/50 cursor-pointer'
          }`}
        >
          {esDiaDePartido ? 'Partido Pendiente' : 'CONTINUAR ➔'}
        </button>

        {simularHasta && (
          <div className="relative" ref={popoverRef}>
            <button
              onClick={() => setMostrarSelector((v) => !v)}
              aria-expanded={mostrarSelector}
              className="font-black px-3 py-2 rounded-xl text-xs uppercase tracking-wider bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 cursor-pointer"
              title="Simular varios días de una hasta una fecha elegida"
            >
              Ir a fecha ➔
            </button>

            {mostrarSelector && (
              <div className="absolute right-0 top-full mt-2 bg-[#121e36] border border-slate-700 rounded-xl p-3 w-64 shadow-xl z-50 space-y-2">
                <p className="text-[11px] text-slate-400">
                  Simula día a día hasta la fecha elegida. Si en el camino tenés un partido, se resuelve solo con simulación rápida.
                </p>
                <input
                  type="date"
                  value={fechaElegida}
                  min={fechaMinima}
                  onChange={(e) => setFechaElegida(e.target.value)}
                  aria-label="Fecha hasta la que simular"
                  className="w-full bg-[#0b1326] border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white"
                />
                <div className="flex gap-2">
                  <button
                    onClick={confirmarSimulacion}
                    disabled={!fechaElegida}
                    className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-40 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-[11px]"
                  >
                    Simular
                  </button>
                  <button
                    onClick={() => setMostrarSelector(false)}
                    className="px-3 py-1.5 rounded-lg text-[11px] text-slate-400 hover:text-slate-200"
                  >
                    Cancelar
                  </button>
                </div>
                {resultadoSimulacion && (
                  resultadoSimulacion.error ? (
                    <p className="text-[11px] text-rose-400">{resultadoSimulacion.error}</p>
                  ) : (
                    <p className="text-[11px] text-emerald-400">
                      Llegaste al {resultadoSimulacion.fechaActual}
                      {resultadoSimulacion.partidosJugados?.length > 0 &&
                        ` — se jugaron ${resultadoSimulacion.partidosJugados.length} partido(s) tuyo(s) en el camino.`}
                      {resultadoSimulacion.nuevaTemporada && ' Además arrancó una nueva temporada.'}
                    </p>
                  )
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}