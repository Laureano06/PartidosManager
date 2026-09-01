import React, { useEffect, useState } from 'react';
import Modal from './Modal';
import { formatearDuracion } from '../utils/formato';
import { formatOverall, formatPotencial } from '../utils/scouting';

const ROL_LABEL = { TITULAR: 'Titular', SUPLENTE: 'Suplente', RESERVA: 'Reserva' };
const ROL_CLASS = {
  TITULAR: 'bg-emerald-950 text-emerald-400 border-emerald-500/40',
  SUPLENTE: 'bg-amber-950 text-amber-400 border-amber-500/40',
  RESERVA: 'bg-slate-800 text-slate-400 border-slate-700',
};

function Stat({ label, value }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="flex justify-between border-b border-slate-800/60 py-2.5">
      <span className="text-slate-400">{label}</span>
      <span className="font-bold text-slate-100">{value}</span>
    </div>
  );
}

export default function PlayerDetailModal({ jugador, open, onClose, API_URL, onNegociar, onRenovar, onPrecontrato, onFicharLibre, onToggleTransferible, onOfrecer, onCeder, onEnviarOjeador, onHablar }) {
  const [historial, setHistorial] = useState([]);

  useEffect(() => {
    if (!open || !jugador?.id_jugador || !API_URL) { setHistorial([]); return; }
    fetch(`${API_URL}/jugadores/${jugador.id_jugador}/historial`)
      .then((r) => r.json())
      .then((data) => setHistorial(data.historial || []))
      .catch(() => setHistorial([]));
  }, [open, jugador?.id_jugador, API_URL]);

  if (!jugador) return null;

  const esLibre = jugador.es_libre || jugador.club === 'Agente Libre';
  const diasRestantes = jugador.dias_restantes_contrato ?? jugador.dias_restantes;

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-3xl mx-auto space-y-8">
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h3 className="text-3xl font-black text-white">{jugador.nombre}</h3>
            <p className="text-sm text-slate-400 mt-1">{jugador.club || 'Tu plantel'} · {jugador.nacionalidad}</p>
            {jugador.rol && (
              <span className={`inline-block mt-3 text-xs font-bold px-3 py-1 rounded-full border ${ROL_CLASS[jugador.rol] || ROL_CLASS.RESERVA}`}>
                {ROL_LABEL[jugador.rol] || jugador.rol}
              </span>
            )}
            {esLibre ? (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-sky-950 text-sky-300 border-sky-500/40">
                Agente Libre
              </span>
            ) : diasRestantes != null && (
              <span className={`inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border ${
                diasRestantes <= 180 ? 'bg-amber-950 text-amber-300 border-amber-500/40' : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
                Contrato: {formatearDuracion(diasRestantes)}
              </span>
            )}
            {jugador.en_transferible && (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-amber-950 text-amber-300 border-amber-500/40">
                En lista de transferibles
              </span>
            )}
            {jugador.id_equipo_dueno != null && (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-sky-950 text-sky-300 border-sky-500/40">
                A préstamo en {jugador.club_prestamista || '?'}{jugador.fin_cesion ? ` hasta ${new Date(`${jugador.fin_cesion}T00:00:00`).toLocaleDateString('es-AR')}` : ''}
              </span>
            )}
          </div>
          <span className="bg-sky-500 text-slate-950 font-black text-2xl px-4 py-2 rounded-2xl shrink-0">
            {formatOverall(jugador)}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-1 text-sm">
          <Stat
            label="Posición"
            value={jugador.posicion_especifica ? `${jugador.posicion_especifica} (${jugador.pos || jugador.posicion})` : (jugador.pos || jugador.posicion)}
          />
          <Stat label="Edad" value={jugador.edad} />
          <Stat label="Ataque" value={jugador.atq ?? jugador.ataque} />
          <Stat label="Defensa" value={jugador.def ?? jugador.defensa} />
          <Stat label="Pase" value={jugador.pase} />
          <Stat label="Físico" value={jugador.fis ?? jugador.fisico} />
          <Stat label="Energía" value={jugador.energia != null ? `${jugador.energia}%` : null} />
          <Stat label="Moral" value={jugador.moral != null ? `${jugador.moral}%` : null} />
          <Stat label="Valor de mercado" value={`$${(jugador.val ?? jugador.valor_mercado ?? 0).toLocaleString('es-AR')}`} />
          <Stat label="Salario/sem" value={`$${(jugador.sal ?? jugador.salario ?? 0).toLocaleString('es-AR')}`} />
        </div>

        {historial.length > 0 && (
          <div className="border-t border-slate-800 pt-5">
            <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Evolución de carrera</h4>
            <div className="overflow-x-auto scroll-slide">
              <table className="w-full text-xs min-w-[420px]">
                <thead>
                  <tr className="text-slate-500 text-left">
                    <th className="pb-2 pr-4">Temporada</th>
                    <th className="pb-2 pr-4">Club</th>
                    <th className="pb-2 pr-4">Edad</th>
                    <th className="pb-2 pr-4">Ovr</th>
                    <th className="pb-2 pr-4">Pot</th>
                    <th className="pb-2">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((h) => (
                    <tr key={h.temporada} className="border-t border-slate-800/60">
                      <td className="py-1.5 pr-4 text-slate-300 font-bold">{h.temporada}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{h.nombre_equipo}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{h.edad}</td>
                      <td className="py-1.5 pr-4 text-white font-bold">{formatOverall(h)}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{formatPotencial(h)}</td>
                      <td className="py-1.5 text-sky-400 font-bold">${h.valor_mercado.toLocaleString('es-AR')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-4 flex-wrap">
          {onHablar && (
            <button
              onClick={onHablar}
              className="flex-1 bg-slate-800 hover:bg-slate-700 border border-sky-500/40 text-sky-300 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Hablar
            </button>
          )}
          {onNegociar && (
            <button
              onClick={onNegociar}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Negociar fichaje
            </button>
          )}
          {onPrecontrato && (
            <button
              onClick={onPrecontrato}
              className="flex-1 bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Precontrato (firma libre)
            </button>
          )}
          {onFicharLibre && (
            <button
              onClick={onFicharLibre}
              className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Fichar libre
            </button>
          )}
          {onRenovar && (
            <button
              onClick={onRenovar}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Renovar contrato
            </button>
          )}
          {onToggleTransferible && (
            <button
              onClick={onToggleTransferible}
              className={`flex-1 font-bold px-4 py-3 rounded-xl text-sm ${
                jugador.en_transferible
                  ? 'bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300'
                  : 'bg-amber-400 hover:bg-amber-300 text-slate-950'
              }`}
            >
              {jugador.en_transferible ? 'Sacar de la lista de transferibles' : 'Poner en lista de transferibles'}
            </button>
          )}
          {onOfrecer && (
            <button
              onClick={onOfrecer}
              className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Ofrecer a otros equipos
            </button>
          )}
          {onCeder && (
            <button
              onClick={onCeder}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Ceder a préstamo
            </button>
          )}
          {onEnviarOjeador && (
            <button
              onClick={onEnviarOjeador}
              className="flex-1 bg-slate-800 hover:bg-slate-700 border border-sky-500/40 text-sky-300 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Enviar ojeador
            </button>
          )}
          <button onClick={onClose} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm">
            Cerrar
          </button>
        </div>
      </div>
    </Modal>
  );
}
