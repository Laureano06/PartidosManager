import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import PlayerDetailModal from '../components/PlayerDetailModal';
import MoneyInput from '../components/MoneyInput';
import Bandera from '../components/Bandera';
import { formatOverall } from '../utils/scouting';

const NOMBRE_TIPO = { PROPIETARIO: 'Propietario', SATELITE: 'Club Satélite', MINORITARIO: 'Inversión Minoritaria' };

const FFP_TEXTO_CLASE = { verde: 'text-emerald-300', amarillo: 'text-amber-300', rojo: 'text-rose-300' };

const COLUMNAS = [
  { key: 'rol', label: 'Rol' },
  { key: 'nombre', label: 'Nombre' },
  { key: 'posicion', label: 'Pos' },
  { key: 'nacionalidad', label: 'Nac' },
  { key: 'edad', label: 'Edad' },
  { key: 'overall', label: 'Ovr' },
  { key: 'valor_mercado', label: 'Valor' },
  { key: 'salario', label: 'Salario/sem' },
];

const ROL_LABEL = { TITULAR: 'Titular', SUPLENTE: 'Suplente', RESERVA: 'Reserva' };
const ROL_CLASS = {
  TITULAR: 'bg-emerald-950 text-emerald-400 border border-emerald-500/40',
  SUPLENTE: 'bg-amber-950 text-amber-400 border border-amber-500/40',
  RESERVA: 'bg-slate-800 text-slate-400 border border-slate-700',
};

function MoverJugadorModal({ jugador, destino, operacion, API_URL, onCerrar, onConfirmado }) {
  const [duracion, setDuracion] = useState(6);
  const [conOpcion, setConOpcion] = useState(false);
  const [opcionCompra, setOpcionCompra] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const precioFamiliaEstimado = Math.round((jugador.valor_mercado * 0.5) / 1000) * 1000;

  const confirmar = async () => {
    setEnviando(true);
    setError(null);
    try {
      const r = await fetch(`${API_URL}/multiclub/mover-jugador`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_jugador: jugador.id_jugador,
          id_equipo_destino: destino.id_equipo,
          operacion,
          duracion_meses: operacion === 'PRESTAMO' ? duracion : null,
          opcion_compra: operacion === 'PRESTAMO' && conOpcion && opcionCompra ? Number(opcionCompra) : null,
        }),
      });
      const data = await r.json();
      if (!r.ok) { setError(data.detail || 'No se pudo mover al jugador.'); return; }
      onConfirmado(data);
    } catch (e) {
      console.error('Error moviendo jugador por el pipeline multiclub:', e);
      setError('No se pudo conectar con el servidor.');
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onCerrar}>
      <div className="bg-[#121e36] border border-slate-700 rounded-2xl p-6 w-full max-w-sm space-y-4" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-bold text-white">
          {operacion === 'PRESTAMO' ? 'Préstamo facilitado' : 'Transferencia interna'}: {jugador.nombre} → {destino.nombre}
        </h3>
        <p className="text-xs text-slate-400">
          Movimiento directo por el pipeline de tu red multiclub — sin negociación ni tirada de interés.
        </p>

        {operacion === 'PRESTAMO' ? (
          <>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Duración</label>
              <div className="flex gap-3">
                <button onClick={() => setDuracion(6)} className={`flex-1 px-3 py-2 rounded-xl font-bold text-xs ${duracion === 6 ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}>6 meses</button>
                <button onClick={() => setDuracion(12)} className={`flex-1 px-3 py-2 rounded-xl font-bold text-xs ${duracion === 12 ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}>1 año</button>
              </div>
            </div>
            <div>
              <label className="flex items-center gap-2 text-xs text-slate-300 mb-2">
                <input type="checkbox" checked={conOpcion} onChange={(e) => setConOpcion(e.target.checked)} className="accent-sky-500" />
                Incluir opción de compra
              </label>
              {conOpcion && (
                <MoneyInput value={opcionCompra} onChange={setOpcionCompra} className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-lg text-white text-sm" />
              )}
            </div>
          </>
        ) : (
          <div className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs space-y-1">
            <p className="text-slate-400">Precio de familia (50% del valor de mercado): <span className="text-sky-400 font-bold">${precioFamiliaEstimado.toLocaleString('es-AR')}</span></p>
            <p className="text-slate-500">Se mueve directo entre presupuestos de fichajes, con contrato nuevo en {destino.nombre}.</p>
          </div>
        )}

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <div className="flex gap-2">
          <button
            onClick={confirmar}
            disabled={enviando}
            className="flex-1 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2.5 rounded-lg text-sm"
          >
            {enviando ? 'Aplicando...' : 'Confirmar'}
          </button>
          <button onClick={onCerrar} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2.5 rounded-lg text-sm">
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ClubPage({ API_URL, idEquipoUsuario, idPartida, clubActivo, setClubActivo }) {
  const { idEquipo: idEquipoParam } = useParams();
  const idEquipo = Number(idEquipoParam);
  const navigate = useNavigate();
  const esPropioClub = idEquipo === idEquipoUsuario;

  const [equipo, setEquipo] = useState(null);
  const [plantel, setPlantel] = useState(null);
  const [economia, setEconomia] = useState(null);
  const [tabla, setTabla] = useState(null);
  const [multiclub, setMulticlub] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [movimiento, setMovimiento] = useState(null); // { jugador, destino, operacion }
  const [mensajeMovimiento, setMensajeMovimiento] = useState(null);

  const cargar = useCallback(() => {
    if (!idEquipo || !idPartida) return;
    setCargando(true);
    Promise.all([
      fetch(`${API_URL}/equipos?id_partida=${idPartida}`).then((r) => r.json()),
      fetch(`${API_URL}/equipos/${idEquipo}/jugadores`).then((r) => (r.ok ? r.json() : [])),
      fetch(`${API_URL}/equipos/${idEquipo}/economia`).then((r) => r.json()),
      idEquipoUsuario ? fetch(`${API_URL}/equipos/${idEquipoUsuario}/multiclub`).then((r) => r.json()) : Promise.resolve(null),
    ])
      .then(([equipos, jugadores, econ, mc]) => {
        const este = equipos.find((e) => e.id_equipo === idEquipo);
        setEquipo(este || null);
        setPlantel(jugadores);
        setEconomia(econ);
        setMulticlub(mc);
        if (este) {
          fetch(`${API_URL}/tabla?id_liga=${este.id_liga}`).then((r) => r.json()).then((t) => setTabla(t.tabla)).catch(() => setTabla(null));
        }
      })
      .catch((e) => console.error('Error cargando el panel de equipo:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipo, idPartida, idEquipoUsuario]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { setMensajeMovimiento(null); }, [idEquipo]);

  const afiliadosPipeline = useMemo(() => {
    if (!multiclub) return [];
    const propios = multiclub.tus_participaciones.filter((a) => a.pipeline_habilitado).map((a) => ({ ...a, esInversor: true }));
    const ajenos = multiclub.participaciones_sobre_tu_club.filter((a) => a.pipeline_habilitado).map((a) => ({ ...a, esInversor: false }));
    return [...propios, ...ajenos];
  }, [multiclub]);

  const afiliacionConEsteClub = afiliadosPipeline.find((a) => a.id_equipo === idEquipo);

  const destinosPosibles = esPropioClub
    ? afiliadosPipeline
    : (afiliacionConEsteClub ? [{ id_equipo: idEquipoUsuario, nombre: 'tu club' }] : []);

  const togglearInfluencia = async (afiliacion, habilitada) => {
    try {
      await fetch(`${API_URL}/multiclub/influencia`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_afiliacion: afiliacion.id_afiliacion, habilitada }),
      });
      cargar();
    } catch (e) {
      console.error('Error togglando influencia:', e);
    }
  };

  if (cargando || !equipo) {
    return <p className="text-xs text-slate-400">Cargando panel de equipo...</p>;
  }

  const posicionTabla = tabla ? tabla.findIndex((t) => t.id_equipo === idEquipo) + 1 : null;

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          {equipo.escudo_url ? (
            <img src={equipo.escudo_url.startsWith('/static/') ? `${API_URL}${equipo.escudo_url}` : equipo.escudo_url} alt={equipo.nombre} className="w-12 h-12 rounded-lg object-contain bg-[#0b1326] border border-slate-800" />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-sky-950 border border-sky-500/40 text-sky-300 font-black flex items-center justify-center">
              {equipo.nombre.replace(/^.*-\s*/, '').trim().charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <h1 className="text-lg font-black text-white">{equipo.nombre}</h1>
            <p className="text-xs text-slate-400">
              Reputación {equipo.reputacion}{posicionTabla ? ` · ${posicionTabla}º en su liga` : ''} · {equipo.puntos} pts ({equipo.ganados}G {equipo.empatados}E {equipo.perdidos}P)
            </p>
          </div>
        </div>
        {!esPropioClub && clubActivo === idEquipo && (
          <span className="text-xs font-bold text-amber-300 bg-amber-950/60 border border-amber-500/40 px-3 py-1.5 rounded-lg">
            Gestionando este club
          </span>
        )}
      </div>

      {afiliacionConEsteClub && (
        <div className="bg-[#121e36] border border-sky-500/40 rounded-2xl p-6 space-y-3">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">
            Club afiliado — {NOMBRE_TIPO[afiliacionConEsteClub.tipo_relacion] || afiliacionConEsteClub.tipo_relacion} ({afiliacionConEsteClub.porcentaje}%)
          </h2>
          <p className="text-xs text-slate-400">
            Tenés pipeline de préstamos y transferencias facilitado con este club (sin negociación).
          </p>
          {afiliacionConEsteClub.esInversor && setClubActivo && (
            <div className="flex items-center gap-3 pt-2 border-t border-slate-800">
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={afiliacionConEsteClub.influencia_habilitada}
                  onChange={(e) => togglearInfluencia(afiliacionConEsteClub, e.target.checked)}
                  className="accent-sky-500"
                />
                Influir en su táctica, entrenamiento y fichajes
              </label>
              {afiliacionConEsteClub.influencia_habilitada && (
                <button
                  onClick={() => { setClubActivo(idEquipo); navigate('/tacticas'); }}
                  className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs"
                >
                  Gestionar este club ➔
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {mensajeMovimiento && (
        <div className="bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 rounded-xl p-3 text-xs">
          {mensajeMovimiento}
        </div>
      )}

      {economia && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-4">
            <p className="text-[11px] text-slate-400 uppercase">Presupuesto fichajes</p>
            <p className="text-lg font-black text-white">${economia.presupuesto_fichajes.toLocaleString('es-AR')}</p>
          </div>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-4">
            <p className="text-[11px] text-slate-400 uppercase">Masa salarial/sem</p>
            <p className="text-lg font-black text-white">${economia.masa_salarial_semanal.toLocaleString('es-AR')}</p>
          </div>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-4">
            <p className="text-[11px] text-slate-400 uppercase">Valor de plantilla</p>
            <p className="text-lg font-black text-white">${economia.valor_plantilla.toLocaleString('es-AR')}</p>
          </div>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-4">
            <p className="text-[11px] text-slate-400 uppercase">Estado FFP</p>
            <p className={`text-sm font-bold uppercase ${FFP_TEXTO_CLASE[economia.color_ffp] || 'text-white'}`}>{economia.estado_ffp}</p>
          </div>
        </div>
      )}

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-3">Plantel ({plantel?.length ?? 0} jugadores)</h2>
        {!plantel || plantel.length === 0 ? (
          <p className="text-xs text-slate-400">Sin datos de plantel disponibles.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  {COLUMNAS.map((c) => <th key={c.key} className="p-2">{c.label}</th>)}
                  {destinosPosibles.length > 0 && <th className="p-2"></th>}
                </tr>
              </thead>
              <tbody>
                {plantel.map((j) => (
                  <tr
                    key={j.id_jugador}
                    onClick={() => setJugadorDetalle(j)}
                    onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); setJugadorDetalle(j); } }}
                    role="button"
                    tabIndex={0}
                    aria-label={`Ver ficha de ${j.nombre}`}
                    className="border-b border-slate-800/40 hover:bg-[#0b1326]/60 focus-visible:bg-[#0b1326]/60 focus-visible:outline focus-visible:outline-sky-500 cursor-pointer"
                  >
                    <td className="p-2">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${ROL_CLASS[j.rol] || ROL_CLASS.RESERVA}`}>{ROL_LABEL[j.rol] || j.rol}</span>
                    </td>
                    <td className="p-2 font-bold text-slate-200 whitespace-nowrap">{j.nombre}</td>
                    <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                    <td className="p-2 whitespace-nowrap"><Bandera pais={j.nacionalidad} /></td>
                    <td className="p-2 text-slate-300">{j.edad}</td>
                    <td className="p-2 font-bold text-white">{formatOverall(j)}</td>
                    <td className="p-2 font-bold text-slate-300 whitespace-nowrap">${j.valor_mercado.toLocaleString('es-AR')}</td>
                    <td className="p-2 text-slate-400 whitespace-nowrap">${j.salario.toLocaleString('es-AR')}</td>
                    {destinosPosibles.length > 0 && (
                      <td className="p-2">
                        <select
                          value=""
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const [idDestino, operacion] = e.target.value.split(':');
                            const destino = destinosPosibles.find((d) => String(d.id_equipo) === idDestino);
                            if (destino) setMovimiento({ jugador: j, destino, operacion });
                            e.target.value = '';
                          }}
                          className="text-[10px] bg-slate-800 hover:bg-slate-700 text-sky-400 px-2 py-1 rounded font-bold border-none cursor-pointer"
                        >
                          <option value="" disabled>Mover ▾</option>
                          {destinosPosibles.map((d) => (
                            <React.Fragment key={d.id_equipo}>
                              <option value={`${d.id_equipo}:PRESTAMO`}>Préstamo a {d.nombre}</option>
                              <option value={`${d.id_equipo}:TRANSFERENCIA`}>Transferencia a {d.nombre}</option>
                            </React.Fragment>
                          ))}
                        </select>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <PlayerDetailModal jugador={jugadorDetalle} open={!!jugadorDetalle} onClose={() => setJugadorDetalle(null)} API_URL={API_URL} />

      {movimiento && (
        <MoverJugadorModal
          jugador={movimiento.jugador}
          destino={movimiento.destino}
          operacion={movimiento.operacion}
          API_URL={API_URL}
          onCerrar={() => setMovimiento(null)}
          onConfirmado={(data) => {
            setMovimiento(null);
            setMensajeMovimiento(data.mensaje);
            cargar();
          }}
        />
      )}
    </div>
  );
}
