import React, { useEffect, useState } from 'react';
import { formatearDuracion } from '../utils/formato';

function textoRiesgo(confianza) {
  if (confianza <= 15) return { texto: 'CRÍTICO (Despido inminente)', color: 'text-rose-400' };
  if (confianza <= 35) return { texto: 'ALTO (Riesgo de despido)', color: 'text-red-400' };
  if (confianza <= 60) return { texto: 'MEDIO', color: 'text-amber-400' };
  return { texto: 'BAJO', color: 'text-emerald-400' };
}

export default function DirectivaPage({ API_URL, idPartida, onEstadoCambiado }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [confirmandoRenuncia, setConfirmandoRenuncia] = useState(false);
  const [renunciando, setRenunciando] = useState(false);

  useEffect(() => {
    if (!idPartida) return;
    setCargando(true);
    fetch(`${API_URL}/partidas/${idPartida}/directiva`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando directiva:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idPartida]);

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando...</p>;
  }

  const riesgo = textoRiesgo(datos.confianza_directiva);

  const renunciar = async () => {
    setRenunciando(true);
    try {
      const r = await fetch(`${API_URL}/partidas/${idPartida}/renunciar`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(err.detail || 'No se pudo renunciar.');
        setRenunciando(false);
        return;
      }
      onEstadoCambiado?.();
    } catch (e) {
      console.error('Error renunciando:', e);
      setRenunciando(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white">Evaluación de la Junta Directiva</h2>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between font-bold">
            <span className="text-slate-400">Nivel de riesgo:</span>
            <span className={riesgo.color}>{riesgo.texto}</span>
          </div>
          <div className="flex justify-between font-bold">
            <span className="text-slate-400">Confianza de la Directiva:</span>
            <span className="text-sky-400">{datos.confianza_directiva}%</span>
          </div>
          <div className="w-full bg-[#0b1326] h-3 rounded-full overflow-hidden border border-slate-800">
            <div className="bg-sky-400 h-full" style={{ width: `${datos.confianza_directiva}%` }} />
          </div>
        </div>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
        <h2 className="text-sm font-bold text-white mb-1">Objetivo de la temporada</h2>
        <p className="text-xs text-slate-300">{datos.objetivo_temporada}</p>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
        <h2 className="text-sm font-bold text-white mb-1">Tu contrato</h2>
        <p className="text-xs text-slate-400">
          {datos.contrato_dt_anios} año{datos.contrato_dt_anios === 1 ? '' : 's'} — vence en{' '}
          <span className="text-slate-200 font-bold">{formatearDuracion(datos.dias_restantes_contrato)}</span>
        </p>
        <p className="text-[11px] text-slate-500">Trayectoria como DT (balance): {datos.balance_dt}/100</p>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
        <h2 className="text-sm font-bold text-white">Renunciar al cargo</h2>
        <p className="text-[11px] text-slate-500">
          Dejás el club por tu cuenta. Otros clubes te van a ofrecer un puesto acorde a tu trayectoria como DT, no a tu club actual.
        </p>
        {!confirmandoRenuncia ? (
          <button
            onClick={() => setConfirmandoRenuncia(true)}
            className="bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 font-bold px-4 py-2 rounded-lg text-xs"
          >
            Renunciar
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={renunciar}
              disabled={renunciando}
              className="bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold px-4 py-2 rounded-lg text-xs"
            >
              {renunciando ? 'Renunciando...' : 'Confirmar renuncia'}
            </button>
            <button
              onClick={() => setConfirmandoRenuncia(false)}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg text-xs"
            >
              Cancelar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
