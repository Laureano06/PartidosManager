import React, { useEffect, useState } from 'react';
import Modal from './Modal';
import MoneyInput from './MoneyInput';

const TITULOS = {
  renovar: (j) => `Renovar contrato de ${j.nombre}`,
  precontrato: (j) => `Precontrato con ${j.nombre}`,
  libre: (j) => `Fichar libre a ${j.nombre}`,
};

const RONDAS_MAX = 3;

const ETIQUETA_ESTADO = {
  ACEPTADA: 'Acuerdo cerrado',
  CONTRAOFERTA: 'Contraoferta',
  INFLEXIBLE: 'No negocia',
  QUIERE_IRSE: 'Quiere irse',
  NO_INTERESADO: 'No le interesa',
  SIN_MARGEN_SALARIAL: 'Sin margen salarial',
  RECHAZADA: 'Sin acuerdo',
  ERROR: 'Error',
};

export default function ContractModal({ open, onClose, jugador, modo, API_URL, idEquipoUsuario, onResuelto }) {
  const [salario, setSalario] = useState('');
  const [anios, setAnios] = useState(3);
  const [ronda, setRonda] = useState(0);
  const [procesando, setProcesando] = useState(false);
  const [respuesta, setRespuesta] = useState(null);

  useEffect(() => {
    if (jugador) {
      const sugerido = modo === 'renovar' ? Math.round(jugador.salario * 1.15) : Math.round(jugador.salario * 1.1) || 1000;
      setSalario(String(sugerido));
      setRonda(0);
      setRespuesta(null);
    }
  }, [jugador, modo]);

  if (!jugador) return null;

  const enviar = async (montoOverride) => {
    const monto = montoOverride ?? Number(salario);
    if (!monto) return;
    setProcesando(true);
    try {
      const endpoint = modo === 'renovar' ? '/contratos/renovar' : modo === 'precontrato' ? '/fichajes/precontrato' : '/fichajes/fichar-libre';
      const body = modo === 'renovar'
        ? { id_jugador: jugador.id_jugador, salario_propuesto: monto, anios, ronda }
        : modo === 'precontrato'
        ? { id_jugador: jugador.id_jugador, id_equipo_destino: idEquipoUsuario, salario_ofrecido: monto, ronda }
        : { id_jugador: jugador.id_jugador, id_equipo: idEquipoUsuario, salario_ofrecido: monto, ronda };

      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setRespuesta(data);
      setSalario(String(monto));
      if (data.estado === 'ACEPTADA' && onResuelto) onResuelto();
      if (data.estado !== 'ACEPTADA') setRonda((r) => r + 1);
    } catch (error) {
      console.error('Error en la negociación de contrato:', error);
      setRespuesta({ estado: 'ERROR', mensaje: 'No se pudo conectar con el servidor.' });
    } finally {
      setProcesando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} labelledBy="contrato-modal-title">
      <div className="p-8 sm:p-12 max-w-xl mx-auto space-y-6">
        <div>
          <h3 id="contrato-modal-title" className="text-2xl font-bold text-white">{TITULOS[modo](jugador)}</h3>
          <p className="text-sm text-slate-400 mt-1">
            {jugador.club ? `${jugador.club} · ` : ''}Ronda {Math.min(ronda + 1, RONDAS_MAX)} de {RONDAS_MAX}
          </p>
        </div>

        {!respuesta ? (
          <div className="space-y-4 text-sm">
            <p className="text-slate-300">Salario actual: ${jugador.salario.toLocaleString('es-AR')}/semana</p>
            <div>
              <label htmlFor="contrato-salario" className="text-xs text-slate-400 block mb-1">Salario semanal ofrecido</label>
              <MoneyInput
                id="contrato-salario"
                value={salario}
                onChange={setSalario}
                className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white"
              />
            </div>
            {modo === 'renovar' && (
              <div>
                <label htmlFor="contrato-anios" className="text-xs text-slate-400 block mb-1">Duración (años)</label>
                <select id="contrato-anios" value={anios} onChange={(e) => setAnios(Number(e.target.value))} className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white">
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} año{n > 1 ? 's' : ''}</option>)}
                </select>
              </div>
            )}
            <button
              onClick={() => enviar()}
              disabled={procesando}
              className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl w-full"
            >
              {procesando ? 'Negociando...' : 'Ofrecer ➔'}
            </button>
          </div>
        ) : (
          <div className="space-y-4 text-sm">
            <div className={`p-4 rounded-xl border ${
              respuesta.estado === 'ACEPTADA'
                ? 'bg-emerald-950/60 border-emerald-500 text-emerald-300'
                : respuesta.estado === 'CONTRAOFERTA'
                ? 'bg-amber-950/60 border-amber-500 text-amber-300'
                : respuesta.estado === 'INFLEXIBLE'
                ? 'bg-slate-800/80 border-slate-500 text-slate-300'
                : 'bg-rose-950/60 border-rose-500 text-rose-300'
            }`}>
              <p className="font-bold uppercase">{ETIQUETA_ESTADO[respuesta.estado] || respuesta.estado}</p>
              <p className="mt-1">{respuesta.mensaje}</p>
              {respuesta.contraoferta && (
                <p className="font-bold mt-2">Pide: ${respuesta.contraoferta.toLocaleString('es-AR')}/semana</p>
              )}
            </div>

            {respuesta.estado === 'CONTRAOFERTA' && ronda < RONDAS_MAX && (
              <div className="flex gap-3">
                <button
                  onClick={() => enviar(respuesta.contraoferta)}
                  disabled={procesando}
                  className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl"
                >
                  Aceptar
                </button>
                <button
                  onClick={() => setRespuesta(null)}
                  disabled={procesando}
                  className="flex-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 px-4 py-3 rounded-xl"
                >
                  Hacer otra oferta
                </button>
              </div>
            )}

            {respuesta.estado === 'CONTRAOFERTA' && ronda >= RONDAS_MAX && (
              <p className="text-xs text-slate-400">
                No llegaron a un acuerdo — se agotaron las {RONDAS_MAX} rondas de negociación.
              </p>
            )}

            <button onClick={onClose} className="w-full bg-slate-800 text-slate-300 px-3 py-2.5 rounded-lg">
              Cerrar
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
