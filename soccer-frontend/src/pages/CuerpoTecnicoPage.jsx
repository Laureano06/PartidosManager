import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

function BarraProgreso({ progreso }) {
  return (
    <div className="w-full bg-[#0b1326] h-2 rounded-full overflow-hidden border border-slate-800">
      <div className="bg-sky-400 h-full" style={{ width: `${progreso}%` }} />
    </div>
  );
}

function RangoOverall({ objetivo }) {
  if (objetivo.overall != null) return <span className="font-bold text-white">{objetivo.overall}</span>;
  return <span className="font-bold text-slate-400">{objetivo.overall_rango[0]}-{objetivo.overall_rango[1]}</span>;
}

const FOCO_LABEL = { EQUILIBRADO: 'Equilibrado', OFENSIVO: 'Ofensivo', DEFENSIVO: 'Defensivo', FISICO: 'Físico', DESCANSO: 'Descanso' };
const INTENSIDAD_LABEL = { BAJA: 'Baja', MEDIA: 'Media', ALTA: 'Alta' };

export default function CuerpoTecnicoPage({ API_URL, idEquipoUsuario }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [ojeadorAsignando, setOjeadorAsignando] = useState(null);
  const [nombreBusqueda, setNombreBusqueda] = useState('');
  const [resultados, setResultados] = useState([]);
  const [foco, setFoco] = useState('EQUILIBRADO');
  const [intensidad, setIntensidad] = useState('MEDIA');
  const [guardandoEntrenamiento, setGuardandoEntrenamiento] = useState(false);

  const idJugadorPreseleccionado = searchParams.get('asignar');

  const cargar = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/cuerpo-tecnico`)
      .then((r) => r.json())
      .then((data) => {
        setDatos(data);
        setFoco(data.entrenamiento.foco);
        setIntensidad(data.entrenamiento.intensidad);
      })
      .catch((e) => console.error('Error cargando cuerpo técnico:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => { cargar(); }, [cargar]);

  const guardarEntrenamiento = async () => {
    setGuardandoEntrenamiento(true);
    try {
      await fetch(`${API_URL}/entrenamiento/configurar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_equipo: idEquipoUsuario, foco, intensidad }),
      });
      cargar();
    } catch (e) {
      console.error('Error configurando entrenamiento:', e);
    } finally {
      setGuardandoEntrenamiento(false);
    }
  };

  // Si venimos de "Enviar ojeador" en otra pantalla con un jugador ya
  // elegido, se asigna directo al primer ojeador libre en vez de pedirle
  // al usuario que vuelva a elegir el objetivo.
  useEffect(() => {
    if (!idJugadorPreseleccionado || !datos) return;
    const libre = datos.ojeadores.find((o) => !o.asignado);
    if (libre) {
      asignar(libre.id_ojeador, Number(idJugadorPreseleccionado));
    }
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idJugadorPreseleccionado, datos]);

  const asignar = async (idOjeador, idJugador) => {
    try {
      await fetch(`${API_URL}/scouting/asignar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_ojeador: idOjeador, id_jugador: idJugador }),
      });
      setOjeadorAsignando(null);
      setNombreBusqueda('');
      setResultados([]);
      cargar();
    } catch (e) {
      console.error('Error asignando ojeador:', e);
    }
  };

  const quitar = async (idOjeador) => {
    try {
      await fetch(`${API_URL}/scouting/quitar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_ojeador: idOjeador }),
      });
      cargar();
    } catch (e) {
      console.error('Error quitando asignación:', e);
    }
  };

  const buscar = (texto) => {
    setNombreBusqueda(texto);
    if (!texto.trim()) { setResultados([]); return; }
    const params = new URLSearchParams({ id_equipo: String(idEquipoUsuario), nombre: texto, orden: 'valor' });
    fetch(`${API_URL}/mercado/jugadores?${params.toString()}`)
      .then((r) => r.json())
      .then((data) => setResultados(data.jugadores.slice(0, 8)))
      .catch((e) => console.error('Error buscando jugador para scoutear:', e));
  };

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando cuerpo técnico...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Asistente Táctico</h2>
          <p className="text-lg font-black text-white">{datos.asistente.nombre}</p>
          <p className="text-sm text-slate-300 leading-relaxed">"{datos.asistente.opinion}"</p>
        </div>

        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
          <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Asistente de Entrenamiento</h2>
          <p className="text-sm text-slate-300 leading-relaxed">"{datos.entrenamiento.consejo}"</p>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs text-slate-400 block mb-1">Foco</label>
              <select
                value={foco}
                onChange={(e) => setFoco(e.target.value)}
                className="w-full bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              >
                {Object.entries(FOCO_LABEL).map(([valor, label]) => (
                  <option key={valor} value={valor}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="text-xs text-slate-400 block mb-1">Intensidad</label>
              <select
                value={intensidad}
                onChange={(e) => setIntensidad(e.target.value)}
                className="w-full bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              >
                {Object.entries(INTENSIDAD_LABEL).map(([valor, label]) => (
                  <option key={valor} value={valor}>{label}</option>
                ))}
              </select>
            </div>
          </div>
          <button
            onClick={guardarEntrenamiento}
            disabled={guardandoEntrenamiento}
            className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2 rounded-lg text-xs"
          >
            {guardandoEntrenamiento ? 'Aplicando...' : 'Aplicar plan de entrenamiento'}
          </button>
        </div>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
        <h2 className="text-sm font-bold text-white mb-1">Ojeadores</h2>
        <p className="text-[11px] text-slate-500 mb-4">Cada ojeador scoutea a un jugador a la vez — cuanto mejor su calidad, más rápido cierra el rango de overall/potencial hasta revelar el número exacto.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {datos.ojeadores.map((o) => (
            <div key={o.id_ojeador} className="bg-[#0b1326] border border-slate-800 rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-bold text-slate-200 text-sm">{o.nombre}</p>
                <span className="text-[10px] text-slate-500">Calidad {o.calidad}</span>
              </div>
              {o.asignado ? (
                <>
                  <p className="text-xs text-slate-400">
                    Scouteando a <span className="text-slate-200 font-bold">{o.asignado.nombre}</span> ({o.asignado.posicion_especifica || o.asignado.posicion})
                  </p>
                  <BarraProgreso progreso={o.asignado.progreso} />
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500">{o.asignado.progreso}% investigado</span>
                    <span>Ovr <RangoOverall objetivo={o.asignado} /></span>
                  </div>
                  <button
                    onClick={() => quitar(o.id_ojeador)}
                    className="w-full mt-1 text-[11px] text-slate-500 hover:text-slate-300"
                  >
                    Quitar del objetivo
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setOjeadorAsignando(o.id_ojeador)}
                  className="w-full bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-2 rounded-lg text-xs"
                >
                  Asignar objetivo
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {ojeadorAsignando != null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setOjeadorAsignando(null)}>
          <div className="bg-[#121e36] border border-slate-700 rounded-2xl p-6 w-full max-w-md space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-white">¿A quién scoutea?</h3>
            <input
              autoFocus
              type="text"
              value={nombreBusqueda}
              onChange={(e) => buscar(e.target.value)}
              placeholder="Buscar jugador por nombre..."
              className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-lg text-white text-sm"
            />
            <div className="space-y-1.5 max-h-72 overflow-y-auto scroll-slide">
              {resultados.map((j) => (
                <button
                  key={j.id_jugador}
                  onClick={() => asignar(ojeadorAsignando, j.id_jugador)}
                  className="w-full text-left flex items-center justify-between bg-[#0b1326] border border-slate-800 hover:border-sky-500/50 rounded-lg px-3 py-2 text-xs transition"
                >
                  <span className="text-slate-200">{j.nombre} <span className="text-slate-500">({j.posicion_especifica || j.posicion})</span></span>
                  <span className="text-slate-500">{j.club}</span>
                </button>
              ))}
              {nombreBusqueda && resultados.length === 0 && (
                <p className="text-xs text-slate-500">Sin resultados.</p>
              )}
            </div>
            <button onClick={() => setOjeadorAsignando(null)} className="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg text-xs">
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
