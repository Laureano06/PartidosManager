import PlayerFace from './PlayerFace';
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
  const [anios, setAnios] = useState(3);
  const [clausula, setClausula] = useState('');
  const [historial, setHistorial] = useState([]);
  const [salarioOfrecido, setSalarioOfrecido] = useState('');
  const [procesando, setProcesando] = useState(false);
  const [respuesta, setRespuesta] = useState(null);
  const [ronda, setRonda] = useState(0);
  const [fase, setFase] = useState('precio'); // 'precio' (con el club) | 'contrato' (con el jugador)
  const [montoAcordado, setMontoAcordado] = useState(null);
  // Add-ons: pagos extra endulzantes ofrecidos junto al precio base, atados
  // a partidos jugados con el club comprador — se deciden acá (fase precio)
  // pero recién se persisten cuando se crea el pase de verdad (enviarContrato).
  const [addons, setAddons] = useState([]);
  const [addonPartidos, setAddonPartidos] = useState('');
  const [addonMonto, setAddonMonto] = useState('');

  useEffect(() => {
    if (!jugador) return;
    setOfertaMonto(String(jugador.valor_mercado));
    setSalarioOfrecido(String(Math.round((jugador.salario || 1000) * 1.1)));
    setRespuesta(null);
    setAnios(3); setClausula(''); setHistorial([]);
    setRonda(0);
    setFase('precio');
    setMontoAcordado(null);
    setAddons([]);
    setAddonPartidos('');
    setAddonMonto('');
  }, [jugador]);

  useEffect(() => {
    if (!open || !jugador?.id_jugador || !idEquipoUsuario) return;
    const controller = new AbortController();
    fetch(`${API_URL}/fichajes/historial/${jugador.id_jugador}?id_equipo=${idEquipoUsuario}`, { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error('No se pudo cargar el historial'); return r.json(); })
      .then(setHistorial).catch((e) => { if (e.name !== 'AbortError') console.error(e); });
    return () => controller.abort();
  }, [open, jugador?.id_jugador, idEquipoUsuario, API_URL]);

  const agregarAddon = () => {
    const partidos = Number(addonPartidos);
    const monto = Number(addonMonto);
    if (!partidos || partidos <= 0 || !monto || monto <= 0) return;
    setAddons((prev) => [...prev, { partidos, monto }]);
    setAddonPartidos('');
    setAddonMonto('');
  };

  const quitarAddon = (i) => setAddons((prev) => prev.filter((_, idx) => idx !== i));

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
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisá las condiciones de la oferta.');
      setHistorial((prev) => [...prev, { fase, monto: Number(montoOverride ?? ofertaMonto), estado: data.estado, mensaje: data.mensaje || 'El club acepta el precio.' }]);
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
      setRespuesta({ estado: 'ERROR', mensaje: error.message || 'No se pudo conectar con el servidor.' });
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
          id_jugador: jugador.id_jugador, id_equipo_comprador: idEquipoUsuario, anios: Number(anios), clausula_rescision: clausula ? Number(clausula) : null,
          monto_oferta: montoAcordado, salario_ofrecido: salario, ronda, addons,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Revisá las condiciones del contrato.');
      setHistorial((prev) => [...prev, { fase: 'contrato', monto: salario, estado: data.estado, mensaje: data.mensaje || 'Respuesta del representante' }]);
      setRespuesta(data);
      setSalarioOfrecido(String(salario));
      if (data.estado === 'ACEPTADA') { if (onResuelto) onResuelto(); } else { setRonda((r) => r + 1); }
    } catch (error) {
      console.error('Error negociando el contrato:', error);
      setRespuesta({ estado: 'ERROR', mensaje: error.message || 'No se pudo conectar con el servidor.' });
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
      <div className="fm-negotiation">
        <header className="flex items-center gap-5"><PlayerFace player={jugador} API_URL={API_URL} className="editor-face" /><div><h2 className="text-2xl font-bold">Negociación de fichaje</h2><p className="text-slate-400">{jugador.nombre} · {fase === 'precio' ? 'Acuerdo con el club' : 'Contrato del jugador'}</p></div></header>
        <aside className="fm-negotiation-log"><h4>Historial de la negociación</h4>
          {!historial.length && <p className="text-slate-400">Todavía no enviaste una oferta.</p>}
          <ol>{historial.map((h, i) => <li key={i}><p className="font-bold">{h.fase === 'precio' ? 'Precio del pase' : 'Salario semanal'} · ${h.monto.toLocaleString('es-AR')}</p><p className="text-slate-300 mt-2">{h.mensaje}</p><small>{h.estado}</small></li>)}</ol>
        </aside>
        <div>
          <h3 id="negociacion-modal-title" className="text-2xl font-bold text-white">
            {fase === 'precio' ? `Acordar precio por ${jugador.nombre}` : `Contrato con ${jugador.nombre}`}
          </h3>
          <p className="text-sm text-slate-400 mt-1">
            {fase === 'precio' ? `${jugador.club} (club vendedor)` : `Precio ya acordado: $${montoAcordado?.toLocaleString('es-AR')}`}
            {' · '}Ronda {Math.min(ronda + 1, RONDAS_MAX)} de {RONDAS_MAX}
          </p>
          {fase === 'contrato' && (
            <>
              <p className="text-xs text-amber-400 mt-2">
                El club ya aceptó el precio — ahora falta que el jugador acepte su nuevo contrato.
              </p>
              {addons.length > 0 && (
                <p className="text-[11px] text-slate-400 mt-1">
                  + {addons.map((a) => `$${a.monto.toLocaleString('es-AR')} a los ${a.partidos} partidos`).join(', ')}
                </p>
              )}
            </>
          )}
        </div>

        {!respuesta ? (
          fase === 'precio' ? (
            <div className="space-y-4 text-sm">
              <p className="text-slate-300">Valor estimado: ${jugador.valor_mercado.toLocaleString('es-AR')}</p>
              {jugador.clausula_rescision != null && (
                <div className="bg-rose-950/40 border border-rose-500/40 rounded-xl p-3 flex items-center justify-between gap-3">
                  <p className="text-xs text-rose-300">
                    Tiene cláusula de rescisión: <span className="font-bold">${jugador.clausula_rescision.toLocaleString('es-AR')}</span>. El club no puede negarse a esa cifra.
                  </p>
                  <button
                    onClick={() => enviarOferta(jugador.clausula_rescision)}
                    disabled={procesando}
                    className="shrink-0 bg-rose-500 hover:bg-rose-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs"
                  >
                    Pagar cláusula
                  </button>
                </div>
              )}
              <MoneyInput value={ofertaMonto} onChange={setOfertaMonto} className="w-full bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white" />

              <div className="border-t border-slate-800 pt-4 space-y-2">
                <p className="text-xs text-slate-400">Add-ons (opcional): pagos extra si suma partidos con vos, para poder ofrecer un precio base más bajo.</p>
                {addons.map((a, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 bg-[#0b1326] border border-slate-800 rounded-lg px-3 py-2 text-xs">
                    <span className="text-slate-300">${a.monto.toLocaleString('es-AR')} a los {a.partidos} partidos</span>
                    <button onClick={() => quitarAddon(i)} className="text-rose-400 hover:text-rose-300 font-bold shrink-0">Quitar</button>
                  </div>
                ))}
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <label htmlFor="addon-partidos" className="text-[10px] text-slate-400 block mb-1">Partidos</label>
                    <input
                      id="addon-partidos" type="number" min="1" value={addonPartidos}
                      onChange={(e) => setAddonPartidos(e.target.value)}
                      className="w-full bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                    />
                  </div>
                  <div className="flex-1">
                    <label htmlFor="addon-monto" className="text-[10px] text-slate-400 block mb-1">Monto</label>
                    <MoneyInput id="addon-monto" value={addonMonto} onChange={setAddonMonto} className="w-full bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs" />
                  </div>
                  <button onClick={agregarAddon} className="shrink-0 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-2 rounded-lg text-xs font-bold">
                    + Agregar
                  </button>
                </div>
              </div>

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
              <div className="grid grid-cols-2 gap-4">
                <label>Duración (años)<select aria-label="Duración del contrato" value={anios} onChange={(e) => setAnios(e.target.value)} className="block w-full bg-slate-800 p-3 mt-2">{[1,2,3,4,5].map((n) => <option key={n}>{n}</option>)}</select></label>
                <label>Cláusula de rescisión (opcional)<MoneyInput value={clausula} onChange={setClausula} className="block w-full bg-slate-800 p-3 mt-2" /></label>
              </div>
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
