import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { setRolJugador } from '../utils/roles';
import { FORMACIONES_SLOTS, calcularAlineacionSimple } from '../utils/formaciones';
import LoadingOverlay from '../components/LoadingOverlay';
import Cancha3D from '../components/Cancha3D';

const DURACION_TIEMPO_MS = 15000;
const POSICION_ORDEN = { POR: 0, DEF: 1, MED: 2, DEL: 3 };
const MAX_CAMBIOS = 5;

const ETIQUETA_EVENTO = {
  GOL: { texto: 'GOL', clase: 'bg-emerald-500 text-slate-950' },
  TARJETA_AMARILLA: { texto: 'TA', clase: 'bg-amber-400 text-slate-950' },
  TARJETA_ROJA: { texto: 'TR', clase: 'bg-rose-500 text-white' },
  LESION: { texto: 'LES', clase: 'bg-rose-900 text-rose-200' },
  CAMBIO_TACTICO: { texto: 'TAC', clase: 'bg-sky-500 text-slate-950' },
};

function BadgeEvento({ tipo }) {
  const ev = ETIQUETA_EVENTO[tipo];
  if (!ev) return <span className="shrink-0 text-slate-600">•</span>;
  return <span className={`shrink-0 text-[9px] font-black px-1.5 py-0.5 rounded ${ev.clase}`}>{ev.texto}</span>;
}

function SelectorMentalidad({ actual, onElegir }) {
  return (
    <div>
      <p className="text-xs text-slate-400 mb-2">Mentalidad {actual ? <span className="text-sky-400 font-bold">— actual: {actual}</span> : ''}</p>
      <div className="flex gap-2 flex-wrap">
        {['DEFENSIVA', 'BALANCEADA', 'OFENSIVA'].map((m) => (
          <button
            key={m}
            onClick={() => onElegir(m)}
            className={`px-3 py-2 rounded-lg text-xs font-bold ${
              actual === m ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 hover:bg-sky-500 hover:text-slate-950 text-slate-300'
            }`}
          >
            {m === 'DEFENSIVA' ? 'Defensiva' : m === 'OFENSIVA' ? 'Ofensiva' : 'Balanceada'}
          </button>
        ))}
      </div>
    </div>
  );
}

// El panel de "hacer cambios" es el mismo en el entretiempo y en una pausa
// durante el partido — solo cambia el texto que explica cuándo rige el
// cambio (ver `mensajeContexto`).
function PanelCambios({
  mensajeContexto, tacticaEquipo, onElegirMentalidad, slots, alineacion,
  titularSeleccionado, onSeleccionarTitular, cambiosAgotados, cambiosRealizados,
  banca, onHacerCambio,
}) {
  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
      <h2 className="text-sm font-bold text-white">Hacer cambios</h2>
      {mensajeContexto && <p className="text-[11px] text-slate-500">{mensajeContexto}</p>}

      <SelectorMentalidad actual={tacticaEquipo.mentalidad} onElegir={onElegirMentalidad} />

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">
          Tocá un titular en la cancha y después un suplente para reemplazarlo.
        </p>
        <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full border shrink-0 ml-2 ${
          cambiosAgotados ? 'bg-rose-950 text-rose-300 border-rose-500/40' : 'bg-slate-800 text-slate-300 border-slate-700'
        }`}>
          Cambios: {cambiosRealizados}/{MAX_CAMBIOS}
        </span>
      </div>

      <CanchaCambios
        slots={slots}
        alineacion={alineacion}
        titularSeleccionado={titularSeleccionado}
        onSeleccionarTitular={onSeleccionarTitular}
        sinCambiosDisponibles={cambiosAgotados}
      />

      <div>
        <p className="text-xs text-slate-400 mb-2">
          {titularSeleccionado ? `Elegí quién entra por ${titularSeleccionado.nombre}` : 'Suplentes disponibles'}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {banca.map((j) => (
            <button
              key={j.id_jugador}
              onClick={() => onHacerCambio(j)}
              disabled={j.lesionado || !titularSeleccionado || cambiosAgotados}
              className="text-left flex justify-between items-center gap-2 bg-[#0b1326] border border-slate-800 hover:border-sky-500/50 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl p-2.5 text-xs"
            >
              <span className="font-bold text-slate-200 truncate">
                {j.nombre} {j.lesionado && <span className="text-rose-400">(lesionado)</span>}
              </span>
              <span className="text-sky-400 font-bold shrink-0">{j.posicion_especifica || j.posicion} · {j.overall}</span>
            </button>
          ))}
          {banca.length === 0 && <p className="text-xs text-slate-600">No hay suplentes disponibles.</p>}
        </div>
      </div>
    </div>
  );
}

function ListaEventos({ eventos }) {
  if (eventos.length === 0) {
    return <p className="text-xs text-slate-500 text-center py-6">Sin novedades todavía...</p>;
  }
  return (
    <div className="space-y-1.5">
      {[...eventos].reverse().map((e, i) => (
        <div key={i} className="flex items-start gap-3 text-xs bg-[#0b1326] border border-slate-800/70 rounded-lg px-3 py-2">
          <span className="text-slate-500 font-bold w-8 shrink-0">{e.minuto}'</span>
          <BadgeEvento tipo={e.tipo} />
          <span className="text-slate-300">{e.texto || e.tipo}</span>
        </div>
      ))}
    </div>
  );
}

// Cancha en miniatura para hacer cambios en el entretiempo: se toca un
// titular (se resalta) y después un suplente de la lista para hacer el
// cambio, igual de visual que la pantalla de Tácticas pero simplificado
// (sin drag & drop, ya que acá solo hace falta reemplazar, no reordenar).
function CanchaCambios({ slots, alineacion, titularSeleccionado, onSeleccionarTitular, sinCambiosDisponibles }) {
  const iniciales = (nombre) => nombre.split(' ').pop();
  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-4 relative overflow-hidden min-h-[340px]">
      <div className="absolute inset-3 border-2 border-emerald-800/40 rounded-lg" />
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-1/3 aspect-square rounded-full border-2 border-emerald-800/40" />
      {slots.map((slot, i) => {
        const j = alineacion[i];
        if (!j) {
          return (
            <div key={i} style={{ left: `${slot.x}%`, top: `${slot.y}%` }} className="absolute -translate-x-1/2 -translate-y-1/2">
              <div className="w-9 h-9 rounded-full border-2 border-dashed border-slate-700 text-slate-600 flex items-center justify-center text-[9px] font-bold">
                {slot.posEspecifica || slot.pos}
              </div>
            </div>
          );
        }
        const seleccionado = titularSeleccionado?.id_jugador === j.id_jugador;
        const yaSalio = j.lesionado;
        return (
          <button
            key={i}
            type="button"
            disabled={sinCambiosDisponibles && !seleccionado}
            onClick={() => onSeleccionarTitular(j)}
            style={{ left: `${slot.x}%`, top: `${slot.y}%` }}
            className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-0.5 transition disabled:opacity-40 disabled:cursor-not-allowed ${
              seleccionado ? 'scale-110' : ''
            }`}
            title={yaSalio ? `${j.nombre} está lesionado — hay que cambiarlo` : j.nombre}
          >
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-black shadow-lg border bg-[#121e36] text-white whitespace-nowrap ${
              seleccionado ? 'border-amber-400 ring-2 ring-amber-400' : yaSalio ? 'border-rose-500' : 'border-sky-400'
            }`}>
              {iniciales(j.nombre)}
            </span>
            <span className="text-[9px] text-sky-300 font-bold bg-[#121e36]/80 px-1 rounded">{j.overall}</span>
            <span className={`text-[8px] font-black px-1.5 py-px rounded-full ${yaSalio ? 'bg-rose-500 text-white' : 'bg-slate-800 text-slate-400'}`}>
              {yaSalio ? 'Lesionado' : (slot.posEspecifica || slot.pos)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default function MatchDayPage({ API_URL, idPartida, idEquipoUsuario, fechaActual, plantilla, setPlantilla, onPartidoJugado }) {
  const navigate = useNavigate();
  const [proximoPartido, setProximoPartido] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [procesando, setProcesando] = useState(false);
  const [mensajeProcesando, setMensajeProcesando] = useState('Procesando...');

  // previo | animando1 | entretiempo | animando2 | resultado_rapido | final
  const [fase, setFase] = useState('previo');
  const [pausado, setPausado] = useState(false);

  const [eventosPrimerTiempo, setEventosPrimerTiempo] = useState([]);
  const [eventosSegundoTiempo, setEventosSegundoTiempo] = useState([]);
  const [golesMedioLocal, setGolesMedioLocal] = useState(0);
  const [golesMedioVisit, setGolesMedioVisit] = useState(0);
  const [golesFinalLocal, setGolesFinalLocal] = useState(0);
  const [golesFinalVisit, setGolesFinalVisit] = useState(0);
  const [mercadoIa, setMercadoIa] = useState([]);
  const [nuevaTemporada, setNuevaTemporada] = useState(false);
  const [charlaDada, setCharlaDada] = useState(false);
  const [resultadoCharla, setResultadoCharla] = useState(null);
  const [dandoCharla, setDandoCharla] = useState(false);

  const [tiempoTranscurrido, setTiempoTranscurrido] = useState(0);
  const [eventosRevelados, setEventosRevelados] = useState([]);

  // Táctica real del equipo (se pisa solo el campo que se cambia, nunca se
  // resetea la formación/presión a un valor fijo al cambiar mentalidad).
  const [tacticaEquipo, setTacticaEquipo] = useState({ formacion: '4-4-2', mentalidad: 'BALANCEADA', presion: 'MEDIA', estilo_pase: 'MIXTO' });
  // Formación real del rival (para dibujar la cancha 3D con ambos planteles,
  // no solo el propio).
  const [tacticaRival, setTacticaRival] = useState(null);
  const [plantillaRival, setPlantillaRival] = useState([]);
  const [coloresEquipos, setColoresEquipos] = useState({});
  const [vista3d, setVista3d] = useState(true);
  const [eventoGol3d, setEventoGol3d] = useState(null);
  const golesDisparados3d = useRef(new Set());
  const [eventoReaccion3d, setEventoReaccion3d] = useState(null);
  const reaccionesDisparadas3d = useRef(new Set());

  // Cambios de jugadores: máximo 5 por partido, se resetean solo al empezar
  // un partido nuevo (no en cada tiempo).
  const [cambiosRealizados, setCambiosRealizados] = useState(0);
  const [titularSeleccionado, setTitularSeleccionado] = useState(null);

  // Marcaje individual: instrucción efímera para el próximo partido, no se
  // persiste en ningún lado — solo vive acá mientras dura esta pantalla.
  const [jugadorMarcado, setJugadorMarcado] = useState('');

  useEffect(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/calendario/equipo/${idEquipoUsuario}`)
      .then((r) => r.json())
      .then((data) => setProximoPartido(data.partidos.find((p) => !p.jugado) || null))
      .catch((e) => console.error('Error cargando el próximo partido:', e))
      .finally(() => setCargando(false));
  }, [API_URL, idEquipoUsuario]);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/tacticas/${idEquipoUsuario}`)
      .then((r) => r.json())
      .then((d) => { if (d && d.formacion) setTacticaEquipo(d); })
      .catch((e) => console.error('Error cargando la táctica:', e));
  }, [API_URL, idEquipoUsuario]);

  // Formación y plantel real del rival, para que la cancha 3D muestre ambos
  // equipos tal cual están armados, no un rival inventado.
  useEffect(() => {
    if (!proximoPartido || !idEquipoUsuario) return;
    const idRival = proximoPartido.id_local === idEquipoUsuario ? proximoPartido.id_visitante : proximoPartido.id_local;
    fetch(`${API_URL}/tacticas/${idRival}`)
      .then((r) => r.json())
      .then((d) => { if (d && d.formacion) setTacticaRival(d); })
      .catch((e) => console.error('Error cargando la táctica del rival:', e));
    fetch(`${API_URL}/equipos/${idRival}/jugadores`)
      .then((r) => r.json())
      .then(setPlantillaRival)
      .catch((e) => console.error('Error cargando el plantel del rival:', e));
  }, [API_URL, proximoPartido, idEquipoUsuario]);

  // Colores reales de camiseta de ambos clubes, para pintar la cancha 3D.
  useEffect(() => {
    if (!idPartida) return;
    fetch(`${API_URL}/equipos?id_partida=${idPartida}`)
      .then((r) => r.json())
      .then((equipos) => {
        const mapa = {};
        equipos.forEach((e) => { mapa[e.id_equipo] = e.color; });
        setColoresEquipos(mapa);
      })
      .catch((e) => console.error('Error cargando los colores de los equipos:', e));
  }, [API_URL, idPartida]);

  const eventosDelTiempo = fase === 'animando2' ? eventosSegundoTiempo : eventosPrimerTiempo;
  const minutoInicio = fase === 'animando2' ? 46 : 1;
  const minutoFin = fase === 'animando2' ? 90 : 45;

  // El reloj y la revelación de eventos van en efectos separados a
  // propósito: mezclar ambas cosas dentro del updater de setState (como
  // estaba antes) podía disparar el efecto de revelación con el estado
  // "viejo" y hacer que el marcador del entretiempo se viera reseteado.
  useEffect(() => {
    if ((fase !== 'animando1' && fase !== 'animando2') || pausado) return;
    const id = setInterval(() => {
      setTiempoTranscurrido((prev) => Math.min(DURACION_TIEMPO_MS, prev + 100));
    }, 100);
    return () => clearInterval(id);
  }, [fase, pausado]);

  useEffect(() => {
    if (fase !== 'animando1' && fase !== 'animando2') return;
    const rango = minutoFin - minutoInicio;
    const minutoActual = minutoInicio + (tiempoTranscurrido / DURACION_TIEMPO_MS) * rango;
    setEventosRevelados(eventosDelTiempo.filter((e) => e.minuto <= minutoActual));
    if (tiempoTranscurrido >= DURACION_TIEMPO_MS) {
      setFase((f) => (f === 'animando1' ? 'entretiempo' : 'final'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tiempoTranscurrido, fase]);

  // Cada gol recién revelado dispara la animación de la pelota en la cancha
  // 3D — se marca con una clave por evento para no repetirla en cada tick.
  useEffect(() => {
    eventosRevelados.forEach((e) => {
      if (e.tipo !== 'GOL') return;
      const clave = `${fase}-${e.minuto}-${e.equipo}-${e.jugador}`;
      if (golesDisparados3d.current.has(clave)) return;
      golesDisparados3d.current.add(clave);
      setEventoGol3d({ equipo: e.equipo, jugador: e.jugador, key: `${clave}-${golesDisparados3d.current.size}` });
    });
  }, [eventosRevelados, fase]);

  // Tarjetas y lesiones también reaccionan en la cancha 3D (un jugador del
  // equipo afectado se frena un instante), igual criterio anti-repetición
  // que los goles.
  useEffect(() => {
    eventosRevelados.forEach((e) => {
      if (!['TARJETA_AMARILLA', 'TARJETA_ROJA', 'LESION'].includes(e.tipo)) return;
      const clave = `${fase}-${e.minuto}-${e.equipo}-${e.tipo}-${e.jugador}`;
      if (reaccionesDisparadas3d.current.has(clave)) return;
      reaccionesDisparadas3d.current.add(clave);
      setEventoReaccion3d({ equipo: e.equipo, tipo: e.tipo, jugador: e.jugador, key: `${clave}-${reaccionesDisparadas3d.current.size}` });
    });
  }, [eventosRevelados, fase]);

  // Al llegar al entretiempo, refrescamos la plantilla: el desgaste y las
  // lesiones del primer tiempo ya se aplicaron en el backend.
  useEffect(() => {
    if (fase !== 'entretiempo' || !idEquipoUsuario) return;
    setTitularSeleccionado(null);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/jugadores`)
      .then((r) => r.json())
      .then(setPlantilla)
      .catch((e) => console.error('Error refrescando la plantilla:', e));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fase, idEquipoUsuario]);

  if (cargando) return <p className="text-xs text-slate-400">Cargando partido...</p>;
  if (!proximoPartido) {
    return (
      <div className="space-y-4">
        <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
        <p className="text-sm text-slate-400">No hay ningún partido pendiente para hoy.</p>
      </div>
    );
  }
  if (fase === 'previo' && fechaActual && proximoPartido.fecha > fechaActual) {
    return (
      <div className="space-y-4">
        <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
        <p className="text-sm text-slate-400">
          Todavía no es el día de tu partido contra {proximoPartido.id_local === idEquipoUsuario ? proximoPartido.nombre_visitante : proximoPartido.nombre_local}.
          Avanzá los días desde el botón "Continuar" hasta el {proximoPartido.fecha}.
        </p>
      </div>
    );
  }

  const esLocalUsuario = proximoPartido.id_local === idEquipoUsuario;
  const nombreRival = esLocalUsuario ? proximoPartido.nombre_visitante : proximoPartido.nombre_local;
  const titulares = [...plantilla]
    .filter((j) => j.rol === 'TITULAR')
    .sort((a, b) => (POSICION_ORDEN[a.posicion] ?? 9) - (POSICION_ORDEN[b.posicion] ?? 9));
  // La reserva nunca viaja con el plantel del partido — solo suplentes
  // pueden entrar a jugar, ni siquiera como último recurso si están todos
  // lesionados (mismo criterio que `_once_titular` en el backend). Un
  // suplente lesionado tampoco puede entrar, así que directamente no se
  // lista (antes aparecía deshabilitado, pero seguía mostrándose).
  const banca = plantilla
    .filter((j) => j.rol === 'SUPLENTE' && !j.lesionado)
    .sort((a, b) => b.overall - a.overall);
  const slots = FORMACIONES_SLOTS[tacticaEquipo.formacion] || FORMACIONES_SLOTS['4-4-2'];
  const alineacion = calcularAlineacionSimple(titulares, slots);
  const cambiosAgotados = cambiosRealizados >= MAX_CAMBIOS;
  const formacionRival = tacticaRival?.formacion || '4-4-2';
  const formacionCanchaLocal = esLocalUsuario ? tacticaEquipo.formacion : formacionRival;
  const formacionCanchaVisita = esLocalUsuario ? formacionRival : tacticaEquipo.formacion;

  const idRival = proximoPartido.id_local === idEquipoUsuario ? proximoPartido.id_visitante : proximoPartido.id_local;
  const titularesRival = [...plantillaRival]
    .filter((j) => j.rol === 'TITULAR')
    .sort((a, b) => (POSICION_ORDEN[a.posicion] ?? 9) - (POSICION_ORDEN[b.posicion] ?? 9));
  const slotsRival = FORMACIONES_SLOTS[formacionRival] || FORMACIONES_SLOTS['4-4-2'];
  const alineacionRival = calcularAlineacionSimple(titularesRival, slotsRival);
  const nombresPropios = alineacion.map((j) => j?.nombre || '');
  const nombresRivales = alineacionRival.map((j) => j?.nombre || '');
  const nombresCanchaLocal = esLocalUsuario ? nombresPropios : nombresRivales;
  const nombresCanchaVisita = esLocalUsuario ? nombresRivales : nombresPropios;
  const colorPropio = coloresEquipos[idEquipoUsuario];
  const colorRival = coloresEquipos[idRival];
  const colorCanchaLocal = esLocalUsuario ? colorPropio : colorRival;
  const colorCanchaVisita = esLocalUsuario ? colorRival : colorPropio;
  const codigoLocal = proximoPartido.nombre_local.split(' - ')[0];
  const codigoVisita = proximoPartido.nombre_visitante.split(' - ')[0];

  const iniciarSimulacionRapida = async () => {
    setProcesando(true);
    setMensajeProcesando('Simulando el partido...');
    try {
      const res = await fetch(`${API_URL}/partidos/simular`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_local: proximoPartido.id_local, id_visitante: proximoPartido.id_visitante,
          id_jugador_marcado: jugadorMarcado ? Number(jugadorMarcado) : null,
        }),
      });
      const data = await res.json();
      setGolesFinalLocal(data.goles_local);
      setGolesFinalVisit(data.goles_visitante);
      setEventosSegundoTiempo(data.eventos || []);
      setEventosPrimerTiempo([]);
      setMercadoIa(data.mercado_ia || []);
      setNuevaTemporada(!!data.nueva_temporada);
      setCharlaDada(false);
      setResultadoCharla(null);
      setFase('resultado_rapido');
      if (onPartidoJugado) onPartidoJugado();
    } catch (error) {
      console.error('Error simulando el partido:', error);
    } finally {
      setProcesando(false);
    }
  };

  const iniciarPartidoEnVivo = async () => {
    setProcesando(true);
    setMensajeProcesando('Saliendo a la cancha...');
    try {
      const res = await fetch(`${API_URL}/partidos/simular-primer-tiempo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_local: proximoPartido.id_local, id_visitante: proximoPartido.id_visitante,
          id_jugador_marcado: jugadorMarcado ? Number(jugadorMarcado) : null,
        }),
      });
      const data = await res.json();
      setEventosPrimerTiempo(data.eventos || []);
      setGolesMedioLocal(data.goles_local);
      setGolesMedioVisit(data.goles_visitante);
      setTiempoTranscurrido(0);
      setEventosRevelados([]);
      setPausado(false);
      setCambiosRealizados(0);
      setCharlaDada(false);
      setResultadoCharla(null);
      golesDisparados3d.current = new Set();
      setEventoGol3d(null);
      reaccionesDisparadas3d.current = new Set();
      setEventoReaccion3d(null);
      setFase('animando1');
    } catch (error) {
      console.error('Error jugando el primer tiempo:', error);
    } finally {
      setProcesando(false);
    }
  };

  const continuarSegundoTiempo = async () => {
    setProcesando(true);
    setMensajeProcesando('Saliendo a la cancha para el segundo tiempo...');
    try {
      const res = await fetch(`${API_URL}/partidos/simular-segundo-tiempo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_local: proximoPartido.id_local, id_visitante: proximoPartido.id_visitante,
          goles_local: golesMedioLocal, goles_visitante: golesMedioVisit,
          id_jugador_marcado: jugadorMarcado ? Number(jugadorMarcado) : null,
        }),
      });
      const data = await res.json();
      setEventosSegundoTiempo(data.eventos || []);
      setGolesFinalLocal(data.goles_local);
      setGolesFinalVisit(data.goles_visitante);
      setMercadoIa(data.mercado_ia || []);
      setNuevaTemporada(!!data.nueva_temporada);
      setTiempoTranscurrido(0);
      setEventosRevelados([]);
      setPausado(false);
      setFase('animando2');
      if (onPartidoJugado) onPartidoJugado();
    } catch (error) {
      console.error('Error jugando el segundo tiempo:', error);
    } finally {
      setProcesando(false);
    }
  };

  const darCharla = async (tono) => {
    setDandoCharla(true);
    try {
      const res = await fetch(`${API_URL}/partidos/charla`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_fixture: proximoPartido.id_fixture, id_equipo: idEquipoUsuario, tono }),
      });
      const data = await res.json();
      if (res.ok) {
        setResultadoCharla(data);
        setCharlaDada(true);
      }
    } catch (error) {
      console.error('Error dando la charla post-partido:', error);
    } finally {
      setDandoCharla(false);
    }
  };

  // En el entretiempo el marcador es el resultado YA CONFIRMADO del primer
  // tiempo (viene del backend) — no se re-cuenta a partir de los eventos
  // revelados, así nunca puede "resetearse" visualmente.
  let golesVivoLocal;
  let golesVivoVisit;
  if (fase === 'entretiempo') {
    golesVivoLocal = golesMedioLocal;
    golesVivoVisit = golesMedioVisit;
  } else {
    const baseLocal = fase === 'animando2' ? golesMedioLocal : 0;
    const baseVisit = fase === 'animando2' ? golesMedioVisit : 0;
    golesVivoLocal = baseLocal + eventosRevelados.filter((e) => e.tipo === 'GOL' && e.equipo === 'local').length;
    golesVivoVisit = baseVisit + eventosRevelados.filter((e) => e.tipo === 'GOL' && e.equipo === 'visitante').length;
  }
  const minutoVivo = Math.min(minutoFin, Math.round(minutoInicio + (tiempoTranscurrido / DURACION_TIEMPO_MS) * (minutoFin - minutoInicio)));
  // El equipo que va perdiendo "presiona" en la cancha 3D — el juego
  // ambiental (posesión/intercepciones) refleja el marcador real, no un
  // azar simétrico.
  const equipoPresiona = golesVivoLocal < golesVivoVisit ? 'local' : golesVivoLocal > golesVivoVisit ? 'visitante' : null;

  const cambiarMentalidad = async (mentalidad) => {
    const nuevaTactica = { ...tacticaEquipo, mentalidad };
    setTacticaEquipo(nuevaTactica);
    await fetch(`${API_URL}/tacticas/configurar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_equipo: idEquipoUsuario, ...nuevaTactica }),
    }).catch((e) => console.error('Error cambiando mentalidad:', e));
  };

  const seleccionarTitular = (jugador) => {
    setTitularSeleccionado((prev) => (prev?.id_jugador === jugador.id_jugador ? null : jugador));
  };

  const hacerCambio = async (entrante) => {
    if (!titularSeleccionado || cambiosAgotados) return;
    const saliente = titularSeleccionado;
    setPlantilla((prev) => prev.map((j) => {
      if (j.id_jugador === saliente.id_jugador) return { ...j, rol: 'SUPLENTE' };
      if (j.id_jugador === entrante.id_jugador) return { ...j, rol: 'TITULAR' };
      return j;
    }));
    setCambiosRealizados((c) => c + 1);
    setTitularSeleccionado(null);
    try {
      await setRolJugador(API_URL, saliente.id_jugador, 'SUPLENTE');
      await setRolJugador(API_URL, entrante.id_jugador, 'TITULAR');
    } catch (error) {
      console.error('Error haciendo el cambio:', error);
    }
  };

  return (
    <div className="h-full min-h-0 overflow-y-auto scroll-slide space-y-6 pr-1">
      <LoadingOverlay show={procesando} mensaje={mensajeProcesando} />
      <div className="flex items-center justify-between">
        <Link to="/panel" className="text-xs text-sky-400 hover:underline">← Volver al panel</Link>
        {(fase === 'resultado_rapido' || fase === 'final') && (
          <button onClick={() => navigate('/panel')} className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs">
            Volver al panel
          </button>
        )}
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 text-center">
        <p className="text-xs text-amber-400 font-bold uppercase">Día de Partido</p>
        <h1 className="text-2xl font-black text-white mt-1">
          {proximoPartido.nombre_local} <span className="text-slate-500">vs</span> {proximoPartido.nombre_visitante}
        </h1>
        {(fase === 'previo') && <p className="text-xs text-slate-400 mt-1">{proximoPartido.fecha}</p>}
        {(fase === 'animando1' || fase === 'animando2' || fase === 'entretiempo') && (
          <p className="text-5xl font-black text-white mt-3">{golesVivoLocal} - {golesVivoVisit}</p>
        )}
        {(fase === 'animando1' || fase === 'animando2') && (
          <p className="text-xs text-sky-400 font-bold mt-2">Minuto {minutoVivo}'</p>
        )}
        {fase === 'entretiempo' && <p className="text-xs text-amber-400 font-bold mt-2">ENTRETIEMPO</p>}
        {(fase === 'resultado_rapido' || fase === 'final') && (
          <>
            <p className="text-5xl font-black text-white mt-3">{golesFinalLocal} - {golesFinalVisit}</p>
            <p className="text-xs text-slate-500 font-bold mt-2 uppercase">Final del partido</p>
          </>
        )}
      </div>

      {fase === 'previo' && (
        <>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white">Alineación titular vs {nombreRival}</h2>
              <Link to="/tacticas" className="text-xs text-sky-400 hover:underline">Editar en Tácticas →</Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {titulares.map((j) => (
                <div key={j.id_jugador} className="bg-[#0b1326] border border-slate-800 rounded-xl p-2.5 text-xs flex justify-between items-center">
                  <span className="font-bold text-slate-200 truncate">{j.nombre}</span>
                  <span className="text-sky-400 font-bold shrink-0 ml-2">{j.posicion_especifica || j.posicion}</span>
                </div>
              ))}
              {titulares.length === 0 && <p className="text-xs text-slate-500 col-span-full">No se pudo armar la alineación.</p>}
            </div>
          </div>

          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
            <h2 className="text-sm font-bold text-white">Marcaje individual</h2>
            <p className="text-[11px] text-slate-400">
              Elegí un rival para marcar de cerca en este partido: baja su aporte ofensivo, pero tu defensa cede un poco de solidez por reacomodarse para seguirlo.
            </p>
            <select
              value={jugadorMarcado}
              onChange={(e) => setJugadorMarcado(e.target.value)}
              aria-label="Jugador rival a marcar de cerca"
              className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-lg text-white text-xs"
            >
              <option value="">Sin marcaje especial</option>
              {titularesRival
                .filter((j) => j.posicion === 'DEL' || j.posicion === 'MED')
                .map((j) => (
                  <option key={j.id_jugador} value={j.id_jugador}>{j.nombre} ({j.posicion_especifica || j.posicion})</option>
                ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={iniciarSimulacionRapida}
              disabled={procesando}
              className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 text-slate-200 font-bold px-6 py-5 rounded-2xl text-sm"
            >
              Simulación rápida
              <p className="text-[11px] font-normal text-slate-500 mt-1">Resultado instantáneo, sin poder intervenir.</p>
            </button>
            <button
              onClick={iniciarPartidoEnVivo}
              disabled={procesando}
              className="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-6 py-5 rounded-2xl text-sm"
            >
              Jugar el partido
              <p className="text-[11px] font-normal text-slate-800 mt-1">15 segundos por tiempo, con pausa y cambios en el entretiempo.</p>
            </button>
          </div>
        </>
      )}

      {(fase === 'animando1' || fase === 'animando2') && (
        <>
          {vista3d ? (
            <div className="relative bg-black rounded-2xl overflow-hidden border border-slate-800">
              <div className="h-[460px]">
                <Cancha3D
                  formacionLocal={formacionCanchaLocal}
                  formacionVisita={formacionCanchaVisita}
                  eventoGol={eventoGol3d}
                  eventoReaccion={eventoReaccion3d}
                  colorLocal={colorCanchaLocal}
                  colorVisita={colorCanchaVisita}
                  nombresLocal={nombresCanchaLocal}
                  nombresVisita={nombresCanchaVisita}
                  equipoPresiona={equipoPresiona}
                />
              </div>

              {/* Marcador estilo transmisión, superpuesto a la cancha */}
              <div className="absolute top-3 left-3 bg-black/75 backdrop-blur-sm rounded-lg px-3 py-2 flex items-center gap-2.5 shadow-lg">
                <span className="text-xs font-bold text-slate-300">{codigoLocal}</span>
                <span className="text-lg font-black text-white tabular-nums">{golesVivoLocal} - {golesVivoVisit}</span>
                <span className="text-xs font-bold text-slate-300">{codigoVisita}</span>
                <span className="text-xs font-bold text-amber-400 ml-1 border-l border-slate-600 pl-2.5">{minutoVivo}'</span>
              </div>

              {/* Controles superpuestos, en vez de un panel aparte debajo */}
              <div className="absolute top-3 right-3 flex gap-2">
                <button
                  onClick={() => setPausado((p) => !p)}
                  className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs shadow-lg"
                >
                  {pausado ? 'Reanudar' : 'Pausar'}
                </button>
                <button
                  onClick={() => setVista3d(false)}
                  className="bg-black/60 hover:bg-black/80 text-slate-200 font-bold px-3 py-1.5 rounded-lg text-xs shadow-lg"
                >
                  Ver texto
                </button>
              </div>

              <div className="absolute bottom-0 left-0 right-0 h-1.5 bg-black/50">
                <div className="bg-sky-400 h-full transition-all" style={{ width: `${(tiempoTranscurrido / DURACION_TIEMPO_MS) * 100}%` }} />
              </div>
            </div>
          ) : (
            <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5">
              <div className="w-full bg-[#0b1326] h-2 rounded-full overflow-hidden border border-slate-800 mb-4">
                <div className="bg-sky-400 h-full transition-all" style={{ width: `${(tiempoTranscurrido / DURACION_TIEMPO_MS) * 100}%` }} />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPausado((p) => !p)}
                  className="flex-1 bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
                >
                  {pausado ? 'Reanudar' : 'Pausar'}
                </button>
                <button
                  onClick={() => setVista3d(true)}
                  className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold px-4 py-3 rounded-xl text-xs shrink-0"
                >
                  Ver cancha 3D
                </button>
              </div>
            </div>
          )}

          {pausado && (
            <PanelCambios
              mensajeContexto={
                fase === 'animando1'
                  ? 'Partido en pausa: este tiempo ya está resuelto, así que la táctica y los cambios que hagas acá van a regir a partir del segundo tiempo. Tocá "Reanudar" cuando quieras seguir.'
                  : 'Partido en pausa: este tiempo ya está resuelto, así que la táctica y los cambios que hagas acá van a regir desde tu próximo partido. Tocá "Reanudar" cuando quieras seguir.'
              }
              tacticaEquipo={tacticaEquipo}
              onElegirMentalidad={cambiarMentalidad}
              slots={slots}
              alineacion={alineacion}
              titularSeleccionado={titularSeleccionado}
              onSeleccionarTitular={seleccionarTitular}
              cambiosAgotados={cambiosAgotados}
              cambiosRealizados={cambiosRealizados}
              banca={banca}
              onHacerCambio={hacerCambio}
            />
          )}

          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
            <h2 className="text-sm font-bold text-white mb-3">Minuto a minuto</h2>
            <ListaEventos eventos={eventosRevelados} />
          </div>
        </>
      )}

      {fase === 'entretiempo' && (
        <>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
            <h2 className="text-sm font-bold text-white mb-1">Resumen del primer tiempo</h2>
            <ListaEventos eventos={eventosPrimerTiempo} />
          </div>

          <PanelCambios
            tacticaEquipo={tacticaEquipo}
            onElegirMentalidad={cambiarMentalidad}
            slots={slots}
            alineacion={alineacion}
            titularSeleccionado={titularSeleccionado}
            onSeleccionarTitular={seleccionarTitular}
            cambiosAgotados={cambiosAgotados}
            cambiosRealizados={cambiosRealizados}
            banca={banca}
            onHacerCambio={hacerCambio}
          />

          <button
            onClick={continuarSegundoTiempo}
            disabled={procesando}
            className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-4 rounded-2xl text-sm"
          >
            Continuar al segundo tiempo
          </button>
        </>
      )}

      {(fase === 'resultado_rapido' || fase === 'final') && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-3">
            {fase === 'final' ? 'Resumen completo del partido' : 'Resumen del partido'}
          </h2>
          <ListaEventos eventos={fase === 'final' ? [...eventosPrimerTiempo, ...eventosSegundoTiempo] : eventosSegundoTiempo} />
          {mercadoIa.length > 0 && (
            <div className="border-t border-slate-800 pt-4 mt-4 space-y-1.5">
              <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider">Movimientos del mercado</h4>
              {mercadoIa.map((linea, i) => <p key={i} className="text-xs text-slate-400">{linea}</p>)}
            </div>
          )}
          {nuevaTemporada && (
            <div className="border-t border-slate-800 pt-4 mt-4">
              <p className="text-xs text-sky-300 font-bold">Terminó la temporada — se armó el fixture nuevo. Revisá tu plantel en el Centro de Desarrollo.</p>
            </div>
          )}
          <div className="border-t border-slate-800 pt-4 mt-4">
            <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-2">Charla post-partido</h4>
            {charlaDada ? (
              <p className="text-xs text-slate-300">
                {resultadoCharla && (resultadoCharla.delta >= 0
                  ? `Le diste al plantel el mensaje justo — moral ${resultadoCharla.delta >= 0 ? '+' : ''}${resultadoCharla.delta}.`
                  : `El mensaje no encajó con el resultado — moral ${resultadoCharla.delta}.`)}
              </p>
            ) : (
              <div className="flex gap-2 flex-wrap">
                {[
                  { tono: 'EFUSIVA', label: 'Efusiva' },
                  { tono: 'CALMA', label: 'Calma' },
                  { tono: 'EXIGENTE', label: 'Exigente' },
                ].map(({ tono, label }) => (
                  <button
                    key={tono}
                    onClick={() => darCharla(tono)}
                    disabled={dandoCharla}
                    className="bg-slate-800 hover:bg-sky-500 hover:text-slate-950 disabled:opacity-50 text-slate-300 font-bold px-3 py-2 rounded-lg text-xs"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
