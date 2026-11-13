import React, { useEffect, useMemo, useState } from 'react';

function fechaCorta(valor) {
  return new Intl.DateTimeFormat('es-AR', { day: 'numeric', month: 'short' }).format(new Date(`${valor}T12:00:00`));
}

function estadoVentana(ventana, fechaActual) {
  if (!fechaActual) return 'PRÓXIMA';
  if (fechaActual < ventana.inicio) return 'PRÓXIMA';
  if (fechaActual > ventana.fin) return 'FINALIZADA';
  return 'EN CURSO';
}

export default function SeleccionesPage({ API_URL, idPartida, fechaActual }) {
  const [selecciones, setSelecciones] = useState([]);
  const [activa, setActiva] = useState(null);
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState(null);
  const [busqueda, setBusqueda] = useState('');
  const [ventanas, setVentanas] = useState([]);
  const [partidos, setPartidos] = useState([]);
  const [torneos, setTorneos] = useState([]);

  useEffect(() => {
    if (!idPartida) return;
    setDetalle(null); setActiva(null);
    fetch(`${API_URL}/partidas/${idPartida}/selecciones`)
      .then(async (r) => { const d = await r.json(); if (!r.ok) throw new Error(d.detail || 'No se pudieron cargar las selecciones.'); return d; })
      .then(setSelecciones).catch((e) => setError(e.message));
    fetch(`${API_URL}/partidas/${idPartida}/ventanas-internacionales`)
      .then((r) => r.ok ? r.json() : []).then(setVentanas).catch(() => setVentanas([]));
    fetch(`${API_URL}/partidas/${idPartida}/partidos-selecciones`)
      .then((r) => r.ok ? r.json() : []).then(setPartidos).catch(() => setPartidos([]));
    fetch(`${API_URL}/partidas/${idPartida}/torneos-selecciones`)
      .then((r) => r.ok ? r.json() : []).then(setTorneos).catch(() => setTorneos([]));
  }, [API_URL, idPartida]);

  useEffect(() => {
    if (!activa) return;
    fetch(`${API_URL}/selecciones/${activa}`)
      .then((r) => r.json()).then(setDetalle).catch(() => setDetalle(null));
  }, [API_URL, activa]);

  const resumen = useMemo(() => {
    const pendientes = partidos.filter((p) => !p.jugado);
    const enCurso = ventanas.find((v) => estadoVentana(v, fechaActual) === 'EN CURSO');
    const proxima = ventanas.find((v) => estadoVentana(v, fechaActual) === 'PRÓXIMA');
    return { pendientes, enCurso, proxima };
  }, [ventanas, partidos, fechaActual]);

  return <div className="p-5 lg:p-7 space-y-5 max-w-[1600px] mx-auto">
    <div className="fm-page-heading">
      <p className="fm-eyebrow">FÚTBOL INTERNACIONAL</p>
      <h1>Selecciones</h1>
      <p>Planteles y elegibilidad importados desde el Data Pack de esta carrera.</p>
    </div>
    {error && <p className="text-sm text-red-300">{error}</p>}
    {ventanas.length > 0 && <section className="fm-panel p-4 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="fm-eyebrow">CALENDARIO INTERNACIONAL</p><h2 className="text-base font-black text-white">Ventanas y disponibilidad</h2></div><div className="flex gap-2 text-xs"><span className="rounded bg-slate-900 px-2 py-1 text-slate-300">{resumen.pendientes.length} partidos pendientes</span>{resumen.enCurso && <span className="rounded bg-amber-500/20 px-2 py-1 font-bold text-amber-300">Ventana en curso</span>}</div></div>
      <div className="grid gap-3 md:grid-cols-3">{ventanas.map((v) => { const estado = estadoVentana(v, fechaActual); const partidosVentana = partidos.filter((p) => p.fecha >= v.inicio && p.fecha <= v.fin); return <div key={v.id_ventana} className={`rounded-xl border p-3 ${estado === 'EN CURSO' ? 'border-amber-400/50 bg-amber-950/20' : estado === 'PRÓXIMA' ? 'border-sky-500/30 bg-sky-950/15' : 'border-slate-800 bg-slate-950/40'}`}><div className="flex items-start justify-between gap-2"><p className="text-xs font-bold text-white">{v.nombre}</p><span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-black ${estado === 'EN CURSO' ? 'bg-amber-400 text-slate-950' : estado === 'PRÓXIMA' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-400'}`}>{estado}</span></div><p className="mt-2 text-sm text-slate-300">{fechaCorta(v.inicio)} — {fechaCorta(v.fin)}</p><p className="mt-1 text-[11px] text-slate-500">{partidosVentana.length} partido{partidosVentana.length === 1 ? '' : 's'} programado{partidosVentana.length === 1 ? '' : 's'}</p></div>; })}</div>
      {resumen.proxima && <p className="text-xs text-slate-400">Próxima convocatoria: <strong className="text-slate-200">{resumen.proxima.nombre}</strong>. Los jugadores convocados no estarán disponibles para su club durante esa ventana.</p>}
    </section>}
    {torneos.length > 0 && <section className="fm-panel p-4 space-y-4"><div><p className="fm-eyebrow">COMPETICIONES OFICIALES DEL PACK</p><h2 className="text-base font-black text-white">Torneos y clasificación</h2></div>{torneos.map((torneo) => <div key={torneo.id_torneo} className="border border-slate-800 rounded-xl p-3"><h3 className="font-bold text-sky-300">{torneo.nombre} <span className="text-[10px] text-slate-500">{torneo.tipo}</span></h3><div className="mt-3 grid lg:grid-cols-2 gap-3">{torneo.grupos.map((grupo) => <TablaGrupo key={grupo.nombre} grupo={grupo} />)}</div></div>)}</section>}
    {partidos.length > 0 && <div className="fm-panel px-4 py-3 text-xs"><strong className="text-sky-300">Partidos internacionales:</strong><div className="mt-2 grid md:grid-cols-2 xl:grid-cols-3 gap-2">{partidos.map((p) => <div key={p.id_partido} className={`border rounded px-2 py-1.5 text-slate-300 ${p.oficial ? 'bg-sky-950/30 border-sky-700/40' : 'bg-slate-950/60 border-slate-800'}`}><span className="text-slate-500">{p.fecha}</span>{p.competencia && <span className="text-sky-300"> · {p.competencia}</span>} · {p.local} {p.jugado ? <strong className="text-white">{p.goles_local}–{p.goles_visitante}</strong> : 'vs'} {p.visitante}</div>)}</div></div>}
    {!error && selecciones.length === 0 && <div className="fm-panel p-5 text-sm text-slate-400">Esta carrera no se creó con selecciones en su pack. Importá o creá una carrera nueva con un `.pmpack` que incluya <code>database/selecciones.json</code>.</div>}
    {selecciones.length > 0 && <div className="grid lg:grid-cols-[330px_1fr] gap-5">
      <section className="fm-panel p-3 space-y-1 h-fit">
        <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar selección" className="w-full mb-2 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white" />
        <div className="max-h-[68vh] overflow-y-auto scroll-slide space-y-1">
        {selecciones.filter((s) => `${s.nombre} ${s.pais} ${s.categoria}`.toLowerCase().includes(busqueda.toLowerCase())).map((s) => <button key={s.id_seleccion} onClick={() => setActiva(s.id_seleccion)} className={`w-full text-left px-3 py-3 rounded-lg transition ${activa === s.id_seleccion ? 'bg-sky-500 text-slate-950' : 'hover:bg-slate-800 text-slate-200'}`}>
          <div className="font-bold text-sm">{s.nombre} <span className="text-[10px] opacity-70">{s.categoria}</span></div>
          <div className="text-xs opacity-75 mt-0.5">{s.confederacion || s.pais}{s.ranking ? ` · Ranking ${s.ranking}` : ''}</div>
        </button>)}</div>
      </section>
      <section className="fm-panel p-5 min-h-72">
        {!detalle && <p className="text-sm text-slate-400">Elegí una selección para ver su plantel.</p>}
        {detalle && <>
          <div className="border-b border-slate-700 pb-4 mb-4"><h2 className="text-xl font-black">{detalle.nombre}</h2><p className="text-sm text-slate-400">{detalle.seleccionador || 'Sin seleccionador cargado'} · {detalle.confederacion}</p></div>
          <Tabla titulo={`${detalle.convocados.some((j) => j.estado_convocatoria === 'PRESELECCION') ? 'Preselección de juego' : 'Convocados'} (${detalle.convocados.length})`} jugadores={detalle.convocados} />
          <Tabla titulo={`Elegibilidad registrada en el PMPack (${detalle.elegibles.length})`} jugadores={detalle.elegibles} />
        </>}
      </section>
    </div>}
  </div>;
}

function Tabla({ titulo, jugadores }) {
  return <div className="mb-5"><h3 className="text-xs font-black tracking-wide text-sky-300 uppercase mb-2">{titulo}</h3>
    {jugadores.length === 0 ? <p className="text-xs text-slate-500">Sin jugadores cargados.</p> : <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-2">{jugadores.map((j) => <div key={j.id_jugador} className="bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2"><p className="font-bold text-sm">{j.nombre}</p><p className="text-xs text-slate-400">{j.posicion_especifica || j.posicion} · {j.edad} años · OVR {j.overall}</p></div>)}</div>}
  </div>;
}

function TablaGrupo({ grupo }) {
  return <div className="overflow-hidden rounded-lg border border-slate-800"><p className="bg-slate-900 px-3 py-2 text-xs font-bold text-white">{grupo.nombre}</p><div className="text-[11px]">{grupo.tabla.map((fila, indice) => <div key={fila.codigo} className="grid grid-cols-[24px_1fr_28px_28px_28px] gap-1 px-3 py-1.5 border-t border-slate-800 text-slate-300"><span className="text-slate-500">{indice + 1}</span><span>{fila.nombre}</span><span>{fila.pj}</span><span>{fila.gf - fila.gc >= 0 ? '+' : ''}{fila.gf - fila.gc}</span><strong className="text-sky-300 text-right">{fila.pts}</strong></div>)}</div></div>;
}
