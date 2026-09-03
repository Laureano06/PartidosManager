import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import FixtureDetailModal from '../components/FixtureDetailModal';

const DIAS_SEMANA = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB'];
const NOMBRES_MES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
];

function codigoClub(nombreCompleto) {
  return (nombreCompleto || '?').split(' - ')[0];
}

// Grilla de 6 semanas (42 celdas) arrancando en domingo, incluyendo días del
// mes anterior/siguiente para completar filas — igual al calendario de FIFA.
function generarCeldas(anio, mes) {
  const primerDia = new Date(anio, mes, 1);
  const inicioGrilla = new Date(anio, mes, 1 - primerDia.getDay());
  return Array.from({ length: 42 }, (_, i) => {
    const fecha = new Date(inicioGrilla);
    fecha.setDate(inicioGrilla.getDate() + i);
    return fecha;
  });
}

function aISO(fecha) {
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}-${String(fecha.getDate()).padStart(2, '0')}`;
}

export default function CalendarioPage({ API_URL, idEquipoUsuario, fechaActual }) {
  const [partidos, setPartidos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [fixtureSeleccionado, setFixtureSeleccionado] = useState(null);
  const [mesVisible, setMesVisible] = useState(null); // {anio, mes} 0-indexado

  useEffect(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    fetch(`${API_URL}/calendario/equipo/${idEquipoUsuario}`)
      .then((r) => r.json())
      .then((data) => setPartidos(data.partidos))
      .catch((error) => console.error('Error cargando calendario:', error))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  // Arranca mostrando el mes de la fecha actual del juego (no la fecha real).
  useEffect(() => {
    if (mesVisible || !fechaActual) return;
    const [anio, mes] = fechaActual.split('-').map(Number);
    setMesVisible({ anio, mes: mes - 1 });
  }, [fechaActual, mesVisible]);

  const proximoPartido = partidos.find((p) => !p.jugado);

  const partidosPorFecha = useMemo(() => {
    const mapa = {};
    for (const p of partidos) mapa[p.fecha] = p;
    return mapa;
  }, [partidos]);

  if (cargando || !mesVisible) {
    return <p className="text-xs text-slate-400">Cargando calendario...</p>;
  }

  const celdas = generarCeldas(mesVisible.anio, mesVisible.mes);
  const cambiarMes = (delta) => {
    setMesVisible(({ anio, mes }) => {
      const total = anio * 12 + mes + delta;
      return { anio: Math.floor(total / 12), mes: ((total % 12) + 12) % 12 };
    });
  };

  return (
    <div className="h-full min-h-0 flex flex-col lg:flex-row gap-6">
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="shrink-0 flex items-center justify-between mb-4">
          <div>
            <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
            <h1 className="text-2xl font-black text-white mt-1 tracking-wide">CALENDARIO</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => cambiarMes(-1)} aria-label="Mes anterior" className="w-8 h-8 rounded-lg bg-[#121e36] border border-slate-800 text-slate-300 hover:border-sky-500/50">‹</button>
            <button onClick={() => cambiarMes(1)} aria-label="Mes siguiente" className="w-8 h-8 rounded-lg bg-[#121e36] border border-slate-800 text-slate-300 hover:border-sky-500/50">›</button>
          </div>
        </div>

        <div className="grid grid-cols-7 shrink-0 border-b border-slate-800 pb-2 mb-1">
          {DIAS_SEMANA.map((d) => (
            <p key={d} className="text-[10px] font-bold text-slate-400 text-center tracking-widest">{d}</p>
          ))}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto scroll-slide grid grid-cols-7 auto-rows-[minmax(84px,1fr)] gap-1">
          {celdas.map((fecha) => {
            const iso = aISO(fecha);
            const partido = partidosPorFecha[iso];
            const esDelMesVisible = fecha.getMonth() === mesVisible.mes;
            const esHoy = iso === fechaActual;
            const esLocal = partido && partido.id_local === idEquipoUsuario;
            const rival = partido ? codigoClub(esLocal ? partido.nombre_visitante : partido.nombre_local) : null;

            return (
              <button
                key={iso}
                disabled={!partido}
                onClick={() => partido && setFixtureSeleccionado(partido)}
                className={`text-left rounded-lg border p-1.5 flex flex-col transition ${
                  esHoy ? 'border-sky-500 ring-1 ring-sky-500/60' : 'border-slate-800/60'
                } ${
                  !esDelMesVisible ? 'bg-[#0b1326]/40 opacity-40' : partido ? 'bg-[#121e36] hover:border-sky-500/50 cursor-pointer' : 'bg-[#121e36]/60'
                }`}
              >
                <span className={`text-[11px] font-bold ${esDelMesVisible ? 'text-slate-300' : 'text-slate-600'}`}>{fecha.getDate()}</span>
                {partido && (
                  <div className={`mt-1 rounded-md px-1.5 py-1 text-[10px] leading-tight ${
                    partido.tipo === 'COPA' ? 'bg-amber-950/70 border border-amber-500/40 text-amber-300' : 'bg-sky-950/70 border border-sky-500/40 text-sky-300'
                  }`}>
                    <p className="font-bold uppercase tracking-wide truncate">{partido.tipo === 'COPA' ? (partido.nombre_competencia || 'Copa') : 'Liga'}</p>
                    <p className="truncate text-slate-200">{esLocal ? 'vs' : '@'} {rival}</p>
                    {partido.jugado && (
                      <p className="font-black text-white">{partido.goles_local} - {partido.goles_visitante}</p>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      <div className="w-full lg:w-64 shrink-0 space-y-4">
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5">
          <p className="text-3xl font-black text-white">{mesVisible.anio}</p>
          <p className="text-sm font-bold text-sky-400 uppercase tracking-widest">{NOMBRES_MES[mesVisible.mes]}</p>
        </div>

        {proximoPartido && (
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 space-y-1.5">
            <p className="text-[10px] font-bold text-amber-400 uppercase tracking-widest">Próximo partido</p>
            <p className={`text-[10px] font-bold uppercase ${proximoPartido.tipo === 'COPA' ? 'text-amber-400' : 'text-sky-400'}`}>
              {proximoPartido.tipo === 'COPA' ? (proximoPartido.nombre_competencia || 'Copa Internacional') : 'Liga'}
            </p>
            <p className="text-sm font-bold text-white truncate">
              <Link to={`/club/${proximoPartido.id_local}`} className="hover:text-sky-400 hover:underline">{proximoPartido.nombre_local}</Link>
              {' vs '}
              <Link to={`/club/${proximoPartido.id_visitante}`} className="hover:text-sky-400 hover:underline">{proximoPartido.nombre_visitante}</Link>
            </p>
            <p className="text-xs text-slate-400">{proximoPartido.fecha}</p>
          </div>
        )}
      </div>

      <FixtureDetailModal
        fixture={fixtureSeleccionado}
        open={!!fixtureSeleccionado}
        onClose={() => setFixtureSeleccionado(null)}
        esProximo={!!proximoPartido && fixtureSeleccionado?.id_fixture === proximoPartido.id_fixture}
      />
    </div>
  );
}
