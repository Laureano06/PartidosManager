import React from 'react';
import { Link } from 'react-router-dom';
import Modal from './Modal';

export default function FixtureDetailModal({ fixture, open, onClose, esProximo }) {
  if (!fixture) return null;

  return (
    <Modal open={open} onClose={onClose} labelledBy="fixture-modal-title">
      <div className="p-8 sm:p-12 max-w-lg mx-auto space-y-6">
        <div className="text-center border-b border-slate-800 pb-6">
          <span className="text-xs text-slate-400 uppercase font-bold tracking-widest">
            {fixture.tipo === 'COPA'
              ? `${fixture.nombre_competencia || 'Copa'} — ${(fixture.ronda_copa || '').replace(/_/g, ' ')}`
              : `Jornada ${fixture.num_jornada}`}
          </span>
          <h3 id="fixture-modal-title" className="text-2xl font-black text-white mt-2">
            <Link to={`/club/${fixture.id_local}`} onClick={onClose} className="hover:text-sky-400 hover:underline">{fixture.nombre_local}</Link>
            {' '}<span className="text-slate-500">vs</span>{' '}
            <Link to={`/club/${fixture.id_visitante}`} onClick={onClose} className="hover:text-sky-400 hover:underline">{fixture.nombre_visitante}</Link>
          </h3>
          {fixture.jugado ? (
            <p className="text-4xl font-black text-sky-400 mt-4">{fixture.goles_local} - {fixture.goles_visitante}</p>
          ) : (
            <p className="text-sm text-amber-400 font-bold mt-4">Programado para el {fixture.fecha}</p>
          )}
        </div>

        {esProximo && !fixture.jugado && (
          <div className="bg-sky-950/60 border border-sky-500/40 rounded-xl p-4 text-sm text-sky-300 text-center">
            Este es tu próximo partido. Avanzá los días desde el botón "Continuar" hasta la fecha del encuentro para poder jugarlo.
          </div>
        )}

        {fixture.jugado && (
          <div className="text-center text-sm text-slate-400">
            {fixture.goles_local > fixture.goles_visitante && `Ganó ${fixture.nombre_local}.`}
            {fixture.goles_local < fixture.goles_visitante && `Ganó ${fixture.nombre_visitante}.`}
            {fixture.goles_local === fixture.goles_visitante && 'Empate.'}
          </div>
        )}

        <button onClick={onClose} className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm">
          Cerrar
        </button>
      </div>
    </Modal>
  );
}
