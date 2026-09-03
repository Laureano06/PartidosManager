import React, { useState } from 'react';
import Modal from './Modal';

export default function MailModal({ mail, open, onClose, API_URL, onRespondida }) {
  const [procesando, setProcesando] = useState(false);
  const [resultado, setResultado] = useState(null);
  // Aceptar vende un jugador de forma efectivamente irreversible — igual
  // que en Transferencias, pasa por un paso de confirmación explícito en
  // vez de ejecutarse directo al click (antes era el único punto de venta
  // de la app con cero fricción).
  const [confirmandoAceptar, setConfirmandoAceptar] = useState(false);

  if (!mail) return null;

  const responder = async (aceptar) => {
    setProcesando(true);
    try {
      const res = await fetch(`${API_URL}/fichajes/responder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_oferta: mail.id_oferta, aceptar }),
      });
      const data = await res.json();
      setResultado(data.mensaje || data.detail || 'Listo.');
      if (onRespondida) onRespondida();
    } catch (error) {
      console.error('Error respondiendo la oferta:', error);
      setResultado('No se pudo conectar con el servidor.');
    } finally {
      setProcesando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-2xl mx-auto space-y-6">
        <div className="border-b border-slate-800 pb-4">
          <span className="text-sm text-sky-400 font-bold">{mail.remitente} · {mail.fecha}</span>
          <h3 className="text-2xl font-bold text-white mt-2">{mail.asunto}</h3>
        </div>
        <p className="text-base text-slate-300 leading-relaxed">{mail.contenido}</p>

        {mail.tipo === 'MERCADO' && mail.id_oferta && !resultado && !confirmandoAceptar && (
          <div className="flex gap-3 pt-2">
            <button
              disabled={procesando}
              onClick={() => setConfirmandoAceptar(true)}
              className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Aceptar oferta
            </button>
            <button
              disabled={procesando}
              onClick={() => responder(false)}
              className="flex-1 bg-rose-950 hover:bg-rose-900 disabled:opacity-50 border border-rose-500/40 text-rose-300 px-4 py-3 rounded-xl text-sm"
            >
              Rechazar
            </button>
          </div>
        )}

        {confirmandoAceptar && !resultado && (
          <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-4 space-y-3">
            <p className="text-sm text-emerald-300">¿Confirmás aceptar esta oferta? El jugador sale de tu plantel.</p>
            <div className="flex gap-3">
              <button
                disabled={procesando}
                onClick={() => responder(true)}
                className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2.5 rounded-lg text-sm"
              >
                {procesando ? 'Vendiendo...' : 'Sí, vender'}
              </button>
              <button
                disabled={procesando}
                onClick={() => setConfirmandoAceptar(false)}
                className="flex-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 px-4 py-2.5 rounded-lg text-sm"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {resultado && (
          <div className="bg-[#0b1326] border border-sky-500/40 p-4 rounded-xl text-sm text-sky-300">{resultado}</div>
        )}

        <button onClick={onClose} className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm">
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
