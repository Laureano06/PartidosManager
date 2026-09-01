import React, { useState } from 'react';

const TITULOS = {
  DESPEDIDO: 'Te despidieron',
  CONTRATO_FIN_EXITO: 'Tu contrato terminó — cumpliste el objetivo',
  CONTRATO_FIN_SIN_RENOVACION: 'Tu contrato terminó sin renovación',
  CONTRATO_FIN_RENOVACION_OFRECIDA: 'La directiva te ofrece renovar',
  RENUNCIO: 'Presentaste tu renuncia',
};

const SUBTITULOS = {
  DESPEDIDO: 'La directiva perdió la confianza en tu proyecto. Tenés 3 propuestas de otros clubes, de un nivel más bajo que el que dejás.',
  CONTRATO_FIN_EXITO: 'Tu ciclo llegó a su fin natural con el objetivo cumplido. Podés renovar en el mismo club o firmar con uno de mayor nivel.',
  CONTRATO_FIN_SIN_RENOVACION: 'La directiva decidió no renovarte. Tenés 3 propuestas de clubes de un nivel similar.',
  CONTRATO_FIN_RENOVACION_OFRECIDA: 'Pese a no cumplir el objetivo, la directiva te da una nueva oportunidad.',
  RENUNCIO: 'Tenés 3 propuestas de clubes, acordes a tu trayectoria como DT.',
};

function TarjetaOferta({ oferta, onElegir, procesando }) {
  return (
    <button
      onClick={() => onElegir(`id_equipo:${oferta.id_equipo}`)}
      disabled={procesando}
      className="bg-[#0b1326] border border-slate-800 hover:border-sky-500/60 disabled:opacity-50 rounded-2xl p-5 text-left transition space-y-2 w-full"
    >
      <h3 className="text-sm font-bold text-white">{oferta.nombre}</h3>
      <p className="text-xs text-slate-500">{oferta.pais}</p>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-slate-800 h-1.5 rounded-full overflow-hidden">
          <div className="bg-amber-400 h-full" style={{ width: `${oferta.reputacion}%` }} />
        </div>
        <span className="text-xs font-bold text-amber-300">{oferta.reputacion}</span>
      </div>
      <p className="text-[11px] text-sky-400">Firmar contrato →</p>
    </button>
  );
}

export default function DecisionDTPage({ API_URL, idPartida, nombreClubActual, estadoDt, ofertas, onResuelto }) {
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState('');

  const elegir = async (opcion) => {
    setProcesando(true);
    setError('');
    try {
      const r = await fetch(`${API_URL}/partidas/${idPartida}/elegir-destino`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opcion }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data.detail || 'No se pudo procesar la decisión.');
        setProcesando(false);
        return;
      }
      onResuelto();
    } catch (e) {
      setError('No se pudo conectar con el servidor.');
      setProcesando(false);
    }
  };

  const puedeRenovar = estadoDt === 'CONTRATO_FIN_EXITO' || estadoDt === 'CONTRATO_FIN_RENOVACION_OFRECIDA';

  return (
    <div className="min-h-screen bg-[#0b1326] text-slate-100 flex items-center justify-center p-6">
      <div className="max-w-2xl w-full space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-black text-white">{TITULOS[estadoDt] || 'Decisión pendiente'}</h1>
          <p className="text-sm text-slate-400">{SUBTITULOS[estadoDt]}</p>
        </div>

        {error && <p className="text-xs text-rose-400 text-center">{error}</p>}

        {puedeRenovar && (
          <button
            onClick={() => elegir('renovar')}
            disabled={procesando}
            className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-4 rounded-2xl text-sm"
          >
            Renovar con {nombreClubActual}
          </button>
        )}

        {ofertas.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {ofertas.map((o) => (
              <TarjetaOferta key={o.id_oferta} oferta={o} onElegir={elegir} procesando={procesando} />
            ))}
          </div>
        )}

        {estadoDt === 'CONTRATO_FIN_RENOVACION_OFRECIDA' && (
          <p className="text-center text-[11px] text-slate-500">
            Si no aceptás la renovación, podés renunciar más adelante desde Directiva para buscar otro club.
          </p>
        )}
      </div>
    </div>
  );
}
