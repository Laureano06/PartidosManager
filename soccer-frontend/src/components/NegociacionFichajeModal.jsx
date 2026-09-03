import React, { useEffect, useState } from 'react';
import Modal from './Modal';
import MoneyInput from './MoneyInput';

const RONDAS_MAX = 3;

const ETIQUETA_ESTADO = {
  ACEPTADA: 'Acuerdo cerrado',
  CONTRAOFERTA: 'Contraoferta',
  INTRANSFERIBLE: 'Intransferible',
  NO_INTERESADO: 'No le interesa',
  SIN_MARGEN_SALARIAL: 'Sin margen salarial',
  RECHAZADA: 'Sin acuerdo',
  ERROR: 'Error',
};

// Modal de negociación club-a-club por un jugador ajeno: primero se acuerda
// el precio con el club vendedor y recién después el contrato con el
// jugador. Reutilizable desde cualquier pantalla (Transferencias, Sala de
// Fichajes, etc.) — solo necesita el jugador y el equipo comprador.
export default function NegociacionFichajeModal({ jugador, open, onClose, API_URL, idEquipoUsuario, onResuelto }) {
  const [ofertaMonto, setOfertaMonto] = useState('');
  const [salarioOfrecido, setSalarioOfrecido] = useState('');
  const [procesando, setProcesando] = useState(false);
  const [respuesta, setRespuesta] = useState(null);
  const [ronda, setRonda] = useState(0);
  const [fase, setFase] = useState('precio'); // 'precio' (con el club) | 'contrato' (con el jugador)
  const [montoAcordado, setMontoAcordado] = useState(null);

  useEffect(() => {
    if (!jugador) return;
    setOfertaMonto(String(jugador.valor_mercado));
    setSalarioOfrecido(String(Math.round((jugador.salario || 1000) * 1.1)));
    setRespuesta(null);
    setRonda(0);
    setFase('precio');
    setMontoAcordado(null);
  }, [jugador]);

  if (!jugador) return null;

  const enviarOferta = async (montoOverride) => {
    const monto = montoOverride ?? Number(ofertaMonto);
    if (!monto || !idEquipoUsuario) return;
    setProcesando(true);
    try {
      const res = await fetch(`${API_URL}/fichajes/ofertar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_jugador: jugador.id_jugador, id_equipo_comprador: idEquipoUsuario, monto_oferta: monto, ronda }),
      });
      const data = await res.json();
      setOfertaMonto(String(monto));
      if (data.estado === 'ACEPTADA_CLUB') {
        setMontoAcordado(data.monto_acordado);
        setFase('contrato');
        setRonda(0);
        setRespuesta(null);
      } else {
        setRespuesta(data);
        setRonda((r) => r + 1);
      }
    } catch (error) {
      console.error('Error procesando oferta en la API:', error);
      setRespuesta({ estado: 'ERROR', mensaje: 'No se pudo conectar con el servidor.' });
    } finally {
      setProcesando(false);
    }
  };

  const enviarContrato = async (salarioOverride) => {
    const salario = salarioOverride ?? Number(salarioOfrecido);
    if (!salario || !idEquipoUsuario || montoAcordado == null) return;
    setProcesando(true);
    try {
      const res = await fetch(`${API_URL}/fichajes/negociar-contrato`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_jugador: jugador.id_jugador, id_equipo_comprador: idEquipoUsuario,
          monto_oferta: montoAcordado, salario_ofrecido: salario, ronda,
        }),
      });
      const data = await res.json();
      setRespuesta(data);
      setSalarioOfrecido(String(salario));
      if (data.estado === 'ACEPTADA') { if (onResuelto) onResuelto(); } else { setRonda((r) => r + 1); }
    } catch (error) {
      console.error('Error negociando el contrato:', error);
      setRespuesta({ estado: 'ERROR', mensaje: 'No se pudo conectar con el servidor.' });
    } finally {
      setProcesando(false);
    }
  };

  const aceptarContraoferta = () => {
    if (!respuesta?.contraoferta) return;
    if (fase === 'precio') enviarOferta(respuesta.contraoferta);
    else enviarContrato(respuesta.contraoferta);
  };

  return (
    <Modal open={open} onClose={onClose} labelledBy="negociacion-modal-title">
      <div className="p-8 sm:p-12 max-w-xl mx-auto space-y-6">
        <div>
          <h3 id="negociacion-modal-title" className="text-2xl font-bold text-white">
            {fase === 'precio' ? `Acordar precio por ${jugador.nombre}` : `Contrato con ${jugador.nombre}`}
          </h3>
          <p className="text-sm text-slate-400 mt-1">
            {fase === 'precio' ? `${jugador.club} (club vendedor)` : `Precio ya acordado: $${montoAcordado?.toLocaleString('es-AR')}`}
            {' · '}Ronda {Math.min(ronda + 1, RONDAS_MAX)} de {RONDAS_MAX}
          </p>
          {fase === 'contrato' && (
            <p className="text-xs text-amber-400 mt-2">
              El club ya aceptó el precio — ahora falta que el jugador acepte su nuevo contrato.
            </p>
          )}
        </div>

        {!respuesta ? (
          fase === 'precio' ? (
            <div className="space-y-4 text-sm">
              <p className="text-slate-300">Valor estimado: ${jugador.valor_mercado.toLocaleString('es-AR')}</p>
              <MoneyInput value={ofertaMonto} onChange={setOfertaMonto} className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white" />
              <button
                onClick={() => enviarOferta()}
                disabled={procesando}
                className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl w-full"
              >
                {procesando ? 'Negociando...' : 'Ofertar al club ➔'}
              </button>
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              <p className="text-slate-300">Salario actual del jugador: ${jugador.salario?.toLocaleString('es-AR') || '?'}/semana</p>
              <label htmlFor="negociacion-salario" className="text-xs text-slate-400 block mb-1">Salario semanal ofrecido</label>
              <MoneyInput id="negociacion-salario" value={salarioOfrecido} onChange={setSalarioOfrecido} className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white" />
              <button
                onClick={() => enviarContrato()}
                disabled={procesando}
                className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-3 rounded-xl w-full"
              >
                {procesando ? 'Negociando...' : 'Ofrecer contrato al jugador ➔'}
              </button>
            </div>
          )
        ) : (
          <div className="space-y-4 text-sm">
            <div className={`p-4 rounded-xl border ${
              respuesta.estado === 'ACEPTADA'
                ? 'bg-emerald-950/60 border-emerald-500 text-emerald-300'
                : respuesta.estado === 'CONTRAOFERTA'
                ? 'bg-amber-950/60 border-amber-500 text-amber-300'
                : respuesta.estado === 'INTRANSFERIBLE'
                ? 'bg-slate-800/80 border-slate-500 text-slate-300'
                : 'bg-rose-950/60 border-rose-500 text-rose-300'
            }`}>
              <p className="font-bold uppercase">{ETIQUETA_ESTADO[respuesta.estado] || respuesta.estado}</p>
              <p className="mt-1">{respuesta.mensaje}</p>
              {respuesta.contraoferta && (
                <p className="font-bold mt-2">Pide: ${respuesta.contraoferta.toLocaleString('es-AR')}{fase === 'contrato' ? '/semana' : ''}</p>
              )}
            </div>

            {respuesta.estado === 'CONTRAOFERTA' && ronda < RONDAS_MAX && (
              <div className="flex gap-3">
                <button
                  onClick={aceptarContraoferta}
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
