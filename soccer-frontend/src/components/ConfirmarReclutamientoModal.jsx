import React, { useState } from 'react';
import Modal from './Modal';

// Reclutar un juvenil de otro club SIN contrato: se puede incorporar directo
// pagando una compensación por formación, sin negociar con nadie — pero
// igual se avisa el costo antes de cobrarlo (a diferencia de un jugador CON
// contrato, que va por NegociacionFichajeModal).
export default function ConfirmarReclutamientoModal({ jugador, open, onClose, onConfirmado, API_URL, idEquipoUsuario }) {
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState('');

  if (!jugador) return null;
  const costo = Math.round(jugador.valor_mercado * 0.2);

  const confirmar = async () => {
    setProcesando(true);
    setError('');
    try {
      const r = await fetch(`${API_URL}/jugadores/${jugador.id_jugador}/reclutar-juvenil`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_equipo_destino: idEquipoUsuario }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data.detail || 'No se pudo reclutar al jugador.');
        return;
      }
      onConfirmado(jugador.id_jugador, data.compensacion);
    } catch (e) {
      setError('No se pudo conectar con el servidor.');
    } finally {
      setProcesando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-lg mx-auto space-y-6">
        <div>
          <h3 className="text-2xl font-bold text-white">Reclutar a {jugador.nombre}</h3>
          <p className="text-sm text-slate-400 mt-1">{jugador.club} · sin contrato — se puede incorporar directo, sin negociar.</p>
        </div>
        <div className="bg-[#0b1326] border border-slate-800 rounded-xl p-4 text-sm space-y-2">
          <div className="flex justify-between"><span className="text-slate-400">Valor estimado</span><span className="font-bold text-slate-200">${jugador.valor_mercado.toLocaleString('es-AR')}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Compensación por formación (20%)</span><span className="font-bold text-amber-300">${costo.toLocaleString('es-AR')}</span></div>
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <div className="flex gap-3">
          <button
            onClick={confirmar}
            disabled={procesando}
            className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl"
          >
            {procesando ? 'Procesando...' : `Confirmar y pagar $${costo.toLocaleString('es-AR')}`}
          </button>
          <button onClick={onClose} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl">
            Cancelar
          </button>
        </div>
      </div>
    </Modal>
  );
}
