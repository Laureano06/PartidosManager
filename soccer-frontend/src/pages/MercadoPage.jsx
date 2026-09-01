import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ContractModal from '../components/ContractModal';
import NegociacionFichajeModal from '../components/NegociacionFichajeModal';
import PlayerDetailModal from '../components/PlayerDetailModal';
import OfrecerJugadorModal from '../components/OfrecerJugadorModal';
import CederPrestamoModal from '../components/CederPrestamoModal';
import DialogoJugadorModal from '../components/DialogoJugadorModal';
import { formatOverall, formatPotencial } from '../utils/scouting';

function BadgePrioridad({ prioridad }) {
  const color = prioridad >= 8 ? 'bg-emerald-500 text-slate-950' : prioridad >= 5 ? 'bg-sky-500 text-slate-950' : 'bg-slate-700 text-slate-200';
  return <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full font-black text-xs ${color}`}>{prioridad}</span>;
}

export default function MercadoPage({ API_URL, idEquipoUsuario, idPartida, plantilla, setPlantilla, onPresupuestoCambiado, onPlantillaCambiada }) {
  const navigate = useNavigate();
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [tab, setTab] = useState('entrada'); // 'entrada' | 'salida'

  const [jugadorContrato, setJugadorContrato] = useState(null);
  const [modoContrato, setModoContrato] = useState('precontrato');
  const [jugadorNegociacion, setJugadorNegociacion] = useState(null);
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [jugadorAOfrecer, setJugadorAOfrecer] = useState(null);
  const [jugadorACeder, setJugadorACeder] = useState(null);
  const [jugadorADialogar, setJugadorADialogar] = useState(null);
  const [negociaciones, setNegociaciones] = useState({ comprando: [] });
  const idsComprando = useMemo(() => new Map(negociaciones.comprando.map((o) => [o.id_jugador, o])), [negociaciones.comprando]);

  const cargarNegociaciones = useCallback(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/fichajes/en-negociacion?id_equipo=${idEquipoUsuario}`)
      .then((r) => r.json())
      .then(setNegociaciones)
      .catch((e) => console.error('Error cargando negociaciones:', e));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargarNegociaciones(); }, [cargarNegociaciones]);

  const verEnPanel = (jugadorSalida) => {
    // Los datos de "salida" son un resumen; para el panel completo usamos
    // el jugador real de la plantilla (mismos datos que ve Plantel/Táctica).
    const completo = plantilla.find((j) => j.id_jugador === jugadorSalida.id_jugador);
    setJugadorDetalle(completo || jugadorSalida);
  };

  const toggleTransferible = async (jugador) => {
    const nuevoValor = !jugador.en_transferible;
    setPlantilla((prev) => prev.map((j) => (j.id_jugador === jugador.id_jugador ? { ...j, en_transferible: nuevoValor } : j)));
    setJugadorDetalle((prev) => (prev && prev.id_jugador === jugador.id_jugador ? { ...prev, en_transferible: nuevoValor } : prev));
    try {
      await fetch(`${API_URL}/jugadores/${jugador.id_jugador}/transferible`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ en_transferible: nuevoValor }),
      });
    } catch (error) {
      console.error('Error actualizando lista de transferibles:', error);
    }
  };

  const cargarRecomendaciones = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/fichajes/recomendaciones?id_equipo=${idEquipoUsuario}`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando recomendaciones:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargarRecomendaciones(); }, [cargarRecomendaciones]);

  const irAFichar = (jugador) => {
    if (jugador.es_libre) {
      setModoContrato('libre');
      setJugadorContrato(jugador);
    } else if (jugador.elegible_precontrato) {
      setModoContrato('precontrato');
      setJugadorContrato(jugador);
    } else {
      setJugadorNegociacion(jugador);
    }
  };

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando sala de fichajes...</p>;
  }

  const esPropio = jugadorDetalle ? plantilla.some((p) => p.id_jugador === jugadorDetalle.id_jugador) : false;

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs text-slate-400">POSICIÓN MÁS PRIORITARIA</p>
            <p className="text-lg font-black text-white">{datos.posicion_prioritaria || '—'}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setTab('entrada')}
              className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'entrada' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
            >
              Oportunidades de entrada ({datos.recomendaciones.length})
            </button>
            <button
              onClick={() => setTab('salida')}
              className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'salida' ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
            >
              Oportunidades de salida ({datos.oportunidades_salida.length})
            </button>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {Object.entries(datos.promedios_por_posicion).map(([pos, valor]) => (
            <div key={pos} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-500">{pos}</p>
              <p className="text-sm font-bold text-white">{valor || '—'}</p>
            </div>
          ))}
        </div>
      </div>

      {tab === 'entrada' && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Recomendaciones de futbolista</h2>
          <p className="text-[11px] text-slate-500 mb-4">Jugadores del mercado que mejoran tus posiciones más flojas, ordenados por prioridad.</p>
          {datos.recomendaciones.length === 0 ? (
            <p className="text-xs text-slate-500">No encontramos jugadores que mejoren tu plantel en este momento.</p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="p-2">Prior.</th>
                  <th className="p-2">Jugador</th>
                  <th className="p-2">Club</th>
                  <th className="p-2">Pos</th>
                  <th className="p-2">Edad</th>
                  <th className="p-2">Ovr</th>
                  <th className="p-2">Pot</th>
                  <th className="p-2">Valor</th>
                  <th className="p-2">Acción</th>
                </tr>
              </thead>
              <tbody>
                {datos.recomendaciones.map((j) => (
                  <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                    <td className="p-2"><BadgePrioridad prioridad={j.prioridad} /></td>
                    <td className="p-2 font-bold text-slate-200 cursor-pointer" onClick={() => setJugadorDetalle(j)}>{j.nombre}</td>
                    <td className="p-2 text-slate-400">{j.club}</td>
                    <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                    <td className="p-2 text-slate-300">{j.edad}</td>
                    <td className="p-2 font-bold text-white">{formatOverall(j)}</td>
                    <td className="p-2 font-bold text-amber-300">{formatPotencial(j)}</td>
                    <td className="p-2 font-bold text-sky-400">${j.valor_mercado.toLocaleString('es-AR')}</td>
                    <td className="p-2">
                      {idsComprando.has(j.id_jugador) ? (
                        <span className="text-[10px] font-bold text-emerald-400">Se unirá a tu club {idsComprando.get(j.id_jugador).texto_incorporacion}</span>
                      ) : j.id_equipo_precontrato === idEquipoUsuario ? (
                        <span className="text-[10px] font-bold text-emerald-400">
                          Se unirá a tu club libre el {j.fecha_fin_contrato ? new Date(`${j.fecha_fin_contrato}T00:00:00`).toLocaleDateString('es-AR') : '?'}
                        </span>
                      ) : j.id_equipo_precontrato ? (
                        <span className="text-[10px] text-slate-500">Ya firmó precontrato con otro club</span>
                      ) : j.asequible ? (
                        <button onClick={() => irAFichar(j)} className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-1 rounded text-xs">
                          Ir a fichar
                        </button>
                      ) : (
                        <span className="text-[10px] text-rose-400 font-bold">Sin presupuesto</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === 'salida' && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Jugadores con salida recomendada</h2>
          <p className="text-[11px] text-slate-500 mb-4">Jugadores propios que rinden por debajo del promedio del equipo o que suman poco rodaje.</p>
          {datos.oportunidades_salida.length === 0 ? (
            <p className="text-xs text-slate-500">No hay jugadores que convenga liberar por ahora.</p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="p-2">Jugador</th>
                  <th className="p-2">Pos</th>
                  <th className="p-2">Edad</th>
                  <th className="p-2">Ovr</th>
                  <th className="p-2">Rol</th>
                  <th className="p-2">Valor</th>
                  <th className="p-2">Acción</th>
                </tr>
              </thead>
              <tbody>
                {datos.oportunidades_salida.map((j) => (
                  <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                    <td className="p-2 font-bold text-slate-200 cursor-pointer" onClick={() => verEnPanel(j)}>{j.nombre}</td>
                    <td className="p-2 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                    <td className="p-2 text-slate-300">{j.edad}</td>
                    <td className="p-2 font-bold text-white">{j.overall}</td>
                    <td className="p-2 text-slate-400">{j.rol}</td>
                    <td className="p-2 font-bold text-sky-400">${j.valor_mercado.toLocaleString('es-AR')}</td>
                    <td className="p-2">
                      <button onClick={() => verEnPanel(j)} className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-3 py-1 rounded text-xs">
                        Ver ficha
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <ContractModal
        open={!!jugadorContrato}
        onClose={() => setJugadorContrato(null)}
        jugador={jugadorContrato}
        modo={modoContrato}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onResuelto={() => { cargarRecomendaciones(); cargarNegociaciones(); onPresupuestoCambiado?.(); onPlantillaCambiada?.(); }}
      />

      <NegociacionFichajeModal
        jugador={jugadorNegociacion}
        open={!!jugadorNegociacion}
        onClose={() => setJugadorNegociacion(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onResuelto={() => { cargarRecomendaciones(); cargarNegociaciones(); onPresupuestoCambiado?.(); onPlantillaCambiada?.(); }}
      />

      <PlayerDetailModal
        jugador={jugadorDetalle}
        open={!!jugadorDetalle}
        onClose={() => setJugadorDetalle(null)}
        API_URL={API_URL}
        // Las recomendaciones son jugadores de OTROS clubes: ahí no tiene
        // sentido ofrecer a mercado, poner en transferibles ni ceder (eso es
        // solo para el propio plantel, en la pestaña "salida") — en cambio
        // corresponde la acción de fichaje.
        onToggleTransferible={esPropio ? () => toggleTransferible(jugadorDetalle) : undefined}
        onOfrecer={esPropio ? () => { setJugadorAOfrecer(jugadorDetalle); setJugadorDetalle(null); } : undefined}
        onCeder={esPropio ? () => { setJugadorACeder(jugadorDetalle); setJugadorDetalle(null); } : undefined}
        onNegociar={!esPropio && jugadorDetalle && !jugadorDetalle.es_libre && !jugadorDetalle.elegible_precontrato ? () => { setJugadorDetalle(null); irAFichar(jugadorDetalle); } : undefined}
        onPrecontrato={!esPropio && jugadorDetalle && !jugadorDetalle.es_libre && jugadorDetalle.elegible_precontrato && !jugadorDetalle.id_equipo_precontrato ? () => { setJugadorDetalle(null); irAFichar(jugadorDetalle); } : undefined}
        onFicharLibre={!esPropio && jugadorDetalle && jugadorDetalle.es_libre ? () => { setJugadorDetalle(null); irAFichar(jugadorDetalle); } : undefined}
        onEnviarOjeador={!esPropio && jugadorDetalle ? () => navigate(`/cuerpo-tecnico?asignar=${jugadorDetalle.id_jugador}`) : undefined}
        onHablar={jugadorDetalle ? () => { setJugadorADialogar(jugadorDetalle); setJugadorDetalle(null); } : undefined}
      />
      <DialogoJugadorModal
        jugador={jugadorADialogar}
        open={!!jugadorADialogar}
        onClose={() => setJugadorADialogar(null)}
        API_URL={API_URL}
        idEquipoInteresado={idEquipoUsuario}
      />
      <OfrecerJugadorModal
        jugador={jugadorAOfrecer}
        open={!!jugadorAOfrecer}
        onClose={() => setJugadorAOfrecer(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        idPartida={idPartida}
      />
      <CederPrestamoModal
        jugador={jugadorACeder}
        open={!!jugadorACeder}
        onClose={() => setJugadorACeder(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        idPartida={idPartida}
        onResuelto={() => { if (jugadorACeder) setPlantilla((prev) => prev.filter((j) => j.id_jugador !== jugadorACeder.id_jugador)); cargarRecomendaciones(); }}
      />
    </div>
  );
}
