import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

export default function PanelPage({ API_URL, idEquipoUsuario, idPartida, fechaActual }) {
  const [mails, setMails] = useState([]);
  const [tabla, setTabla] = useState([]);
  const [partidos, setPartidos] = useState([]);
  const [cargando, setCargando] = useState(true);

  const cargarTodo = useCallback(() => {
    if (!idEquipoUsuario) return;
    setCargando(true);
    Promise.all([
      fetch(`${API_URL}/inbox?id_equipo=${idEquipoUsuario}`).then((r) => r.json()),
      fetch(`${API_URL}/tabla?id_partida=${idPartida}`).then((r) => r.json()),
      fetch(`${API_URL}/calendario/equipo/${idEquipoUsuario}`).then((r) => r.json()),
    ])
      .then(([inboxData, tablaData, calendarioData]) => {
        setMails(inboxData.emails);
        setTabla(tablaData.tabla);
        setPartidos(calendarioData.partidos);
      })
      .catch((error) => console.error('Error cargando el panel:', error))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario, idPartida]);

  useEffect(() => { cargarTodo(); }, [cargarTodo]);

  const proximoPartido = partidos.find((p) => !p.jugado);
  const esDiaDePartido = !!proximoPartido && proximoPartido.fecha === fechaActual;
  const noLeidos = mails.filter((m) => !m.leido).length;
  const posicionUsuario = tabla.findIndex((r) => r.es_usuario) + 1;
  const miEquipo = tabla.find((r) => r.es_usuario);

  return (
    <div className="h-full min-h-0 flex flex-col gap-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 flex flex-col sm:flex-row justify-between items-center gap-4 shrink-0">
        <div>
          <span className="text-xs font-bold text-amber-400 uppercase">
            {proximoPartido?.tipo === 'COPA' ? 'Próximo Partido de Copa' : 'Próximo Partido Programado'}
          </span>
          <h4 className="text-xl font-black text-white mt-1">
            {cargando ? 'Cargando...' : proximoPartido ? `${proximoPartido.nombre_local} vs. ${proximoPartido.nombre_visitante}` : 'Temporada completa'}
          </h4>
          {proximoPartido && (
            <p className="text-xs text-sky-400 font-bold mt-1">Fecha del Encuentro: {proximoPartido.fecha}</p>
          )}
        </div>

        {esDiaDePartido ? (
          <Link
            to="/partido"
            className="px-5 py-3 rounded-xl text-xs font-bold transition shadow-lg shrink-0 bg-sky-500 hover:bg-sky-400 text-slate-950 shadow-sky-950/50 cursor-pointer animate-pulse inline-block"
          >
            ¡Ir al Partido!
          </Link>
        ) : (
          <button
            disabled
            className="px-5 py-3 rounded-xl text-xs font-bold shrink-0 bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed"
          >
            Esperando Fecha del Partido
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 flex-1 min-h-0">
        <Link
          to="/buzon"
          className="bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-5 flex flex-col min-h-0 transition"
        >
          <div className="flex items-center justify-between shrink-0">
            <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Buzón de Mensajes</h2>
            <span className="text-[10px] text-slate-500">Ver todo →</span>
          </div>
          {cargando ? (
            <p className="text-xs text-slate-400 mt-3">Cargando...</p>
          ) : (
            <>
              <p className="text-3xl font-black text-white mt-3">{noLeidos}</p>
              <p className="text-[11px] text-slate-500 mb-3">mensajes sin leer</p>
              <div className="space-y-1.5 overflow-hidden">
                {mails.slice(0, 3).map((m) => (
                  <div key={m.id} className={`text-xs px-2.5 py-1.5 rounded-lg truncate ${m.leido ? 'text-slate-500' : 'text-slate-200 font-bold'}`}>
                    {m.remitente}: {m.asunto}
                  </div>
                ))}
                {mails.length === 0 && <p className="text-xs text-slate-600">No hay mensajes.</p>}
              </div>
            </>
          )}
        </Link>

        <Link
          to="/calendario"
          className="bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-5 flex flex-col min-h-0 transition"
        >
          <div className="flex items-center justify-between shrink-0">
            <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Calendario</h2>
            <span className="text-[10px] text-slate-500">Ver todo →</span>
          </div>
          {cargando ? (
            <p className="text-xs text-slate-400 mt-3">Cargando...</p>
          ) : (
            <div className="space-y-1.5 mt-3">
              {partidos.filter((p) => !p.jugado).slice(0, 4).map((p) => (
                <div key={p.id_fixture} className="text-xs bg-[#0b1326] border border-slate-800 rounded-lg px-2.5 py-1.5">
                  <p className="text-slate-500">J{p.num_jornada} · {p.fecha}</p>
                  <p className="text-slate-200 truncate">{p.nombre_local} vs {p.nombre_visitante}</p>
                </div>
              ))}
              {partidos.every((p) => p.jugado) && <p className="text-xs text-slate-600">Temporada completa.</p>}
            </div>
          )}
        </Link>

        <Link
          to="/tabla"
          className="bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-5 flex flex-col min-h-0 transition"
        >
          <div className="flex items-center justify-between shrink-0">
            <h2 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Tabla de Posiciones</h2>
            <span className="text-[10px] text-slate-500">Ver todo →</span>
          </div>
          {cargando ? (
            <p className="text-xs text-slate-400 mt-3">Cargando...</p>
          ) : (
            <>
              <p className="text-3xl font-black text-white mt-3">{posicionUsuario || '—'}º</p>
              <p className="text-[11px] text-slate-500 mb-3">{miEquipo ? `${miEquipo.puntos} pts en ${miEquipo.jugados} PJ` : 'sin datos'}</p>
              <div className="space-y-1">
                {tabla.slice(0, 3).map((row, i) => (
                  <div key={row.id_equipo} className={`text-xs flex justify-between px-2.5 py-1 rounded-lg ${row.es_usuario ? 'text-sky-300 font-bold' : 'text-slate-400'}`}>
                    <span className="truncate">{i + 1}. {row.nombre}</span>
                    <span className="shrink-0">{row.puntos} pts</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Link>
      </div>
    </div>
  );
}
