import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import PlayerDetailModal from '../components/PlayerDetailModal';
import CeldaAccionFichaje from '../components/CeldaAccionFichaje';
import ContractModal from '../components/ContractModal';
import NegociacionFichajeModal from '../components/NegociacionFichajeModal';
import ConfirmarReclutamientoModal from '../components/ConfirmarReclutamientoModal';
import DialogoJugadorModal from '../components/DialogoJugadorModal';
import { formatearDuracion } from '../utils/formato';
import { formatOverall, formatPotencial } from '../utils/scouting';
import { CATEGORIAS_ACADEMIA, CATEGORIA_LABEL } from '../utils/academia';

// Igual que engine/data_gen.py: posición específica dentro de cada categoría
// amplia, para poder filtrar el mercado con la misma granularidad que
// muestran los resultados.
const POSICIONES_ESPECIFICAS = {
  POR: ['POR'],
  DEF: ['DFC', 'DFI', 'DFD'],
  MED: ['MCD', 'MC', 'MCO', 'MI', 'MD'],
  DEL: ['EI', 'ED', 'DC', 'MP'],
};

// Igual que en Plantel: clickear un header ordena asc, clickearlo de nuevo
// invierte a desc.
function ordenarLista(lista, sortKey, sortDir) {
  if (!sortKey) return lista;
  const copia = [...lista];
  copia.sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    // Los que no tienen contrato (agentes libres) van siempre al final,
    // ordenando asc o desc, en vez de mezclarse por un null/undefined.
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const cmp = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
    return sortDir === 'asc' ? cmp : -cmp;
  });
  return copia;
}

function useOrdenTabla(lista) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const clickHeader = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
  };
  const ordenada = useMemo(() => ordenarLista(lista, sortKey, sortDir), [lista, sortKey, sortDir]);
  return { ordenada, sortKey, sortDir, clickHeader };
}

function ThOrdenable({ label, colKey, sortKey, sortDir, onClick, className = '' }) {
  return (
    <th onClick={() => onClick(colKey)} className={`p-3 cursor-pointer select-none hover:text-sky-400 transition whitespace-nowrap ${className}`}>
      {label}
      {sortKey === colKey && <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>}
    </th>
  );
}

function BadgeContrato({ j }) {
  if (j.es_libre) {
    return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-500/40">LIBRE</span>;
  }
  if (j.dias_restantes_contrato == null) return null;
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
      j.elegible_precontrato ? 'bg-amber-950 text-amber-300 border-amber-500/40' : 'bg-slate-800 text-slate-400 border-slate-700'
    }`}>
      {j.elegible_precontrato ? `Libre en ${formatearDuracion(j.dias_restantes_contrato)}` : formatearDuracion(j.dias_restantes_contrato)}
    </span>
  );
}

export default function TransferenciasPage({ API_URL, idEquipoUsuario, idPartida, onPresupuestoCambiado, onPlantillaCambiada }) {
  const navigate = useNavigate();
  const [ligas, setLigas] = useState([]);
  const [idLiga, setIdLiga] = useState('');

  const [tab, setTab] = useState('resumen'); // 'resumen' | 'clubes' | 'buscar' | 'preseleccion' | 'negociacion'

  // --- dashboard de resumen: recomendaciones + datos del mercado ---
  const [recomendaciones, setRecomendaciones] = useState(null);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/fichajes/recomendaciones?id_equipo=${idEquipoUsuario}`)
      .then((r) => r.json())
      .then(setRecomendaciones)
      .catch((e) => console.error('Error cargando recomendaciones:', e));
  }, [API_URL, idEquipoUsuario]);

  // --- preseleccionados (shortlist), persistido por equipo en localStorage ---
  const [preseleccionados, setPreseleccionados] = useState([]);
  const [filtroPreselPos, setFiltroPreselPos] = useState('');
  const [filtroPreselPosEspecifica, setFiltroPreselPosEspecifica] = useState('');
  const preseleccionadosFiltrados = preseleccionados.filter((j) => {
    if (filtroPreselPos && j.posicion !== filtroPreselPos) return false;
    if (filtroPreselPosEspecifica && j.posicion_especifica !== filtroPreselPosEspecifica) return false;
    return true;
  });
  const ordenPresel = useOrdenTabla(preseleccionadosFiltrados);

  useEffect(() => {
    if (!idEquipoUsuario) return;
    try {
      const guardado = localStorage.getItem(`preseleccion_${idEquipoUsuario}`);
      setPreseleccionados(guardado ? JSON.parse(guardado) : []);
    } catch {
      setPreseleccionados([]);
    }
  }, [idEquipoUsuario]);

  const guardarPreseleccion = (lista) => {
    setPreseleccionados(lista);
    if (idEquipoUsuario) {
      try { localStorage.setItem(`preseleccion_${idEquipoUsuario}`, JSON.stringify(lista)); } catch { /* noop */ }
    }
  };

  const estaPreseleccionado = (idJugador) => preseleccionados.some((j) => j.id_jugador === idJugador);

  const toggleShortlist = (jugador) => {
    if (estaPreseleccionado(jugador.id_jugador)) {
      guardarPreseleccion(preseleccionados.filter((j) => j.id_jugador !== jugador.id_jugador));
    } else {
      guardarPreseleccion([...preseleccionados, jugador]);
    }
  };

  // --- negociaciones en curso (compras/ventas acordadas + ofertas recibidas) ---
  const [negociaciones, setNegociaciones] = useState({ comprando: [], vendiendo: [], recibidas: [], precontratos_entrantes: [], precontratos_salientes: [] });
  const idsComprando = useMemo(() => new Map(negociaciones.comprando.map((o) => [o.id_jugador, o])), [negociaciones.comprando]);
  const [cargandoNegociaciones, setCargandoNegociaciones] = useState(false);
  const [filtroNegPos, setFiltroNegPos] = useState('');
  const [filtroNegPosEspecifica, setFiltroNegPosEspecifica] = useState('');
  const filtrarPorPosicion = (lista) => lista.filter((o) => {
    if (filtroNegPos && o.posicion !== filtroNegPos) return false;
    if (filtroNegPosEspecifica && o.posicion_especifica !== filtroNegPosEspecifica) return false;
    return true;
  });

  const cargarNegociaciones = () => {
    if (!idEquipoUsuario) return;
    setCargandoNegociaciones(true);
    fetch(`${API_URL}/fichajes/en-negociacion?id_equipo=${idEquipoUsuario}`)
      .then((r) => r.json())
      .then(setNegociaciones)
      .catch((e) => console.error('Error cargando negociaciones:', e))
      .finally(() => setCargandoNegociaciones(false));
  };

  useEffect(() => {
    cargarNegociaciones();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idEquipoUsuario]);

  // Vender un jugador es una decisión de alto impacto (lo saca de tu plantel
  // de forma efectivamente irreversible) — a diferencia de "Rechazar", que
  // no tiene costo, "Aceptar" pasa por una confirmación explícita en vez de
  // ejecutarse directo al click.
  const [ofertaAConfirmar, setOfertaAConfirmar] = useState(null);
  const [confirmandoOferta, setConfirmandoOferta] = useState(false);
  // % de reventa que pedís al vender — si el club comprador revende a este
  // jugador más adelante, cobrás este % de esa venta (una sola vez).
  const [porcentajeReventa, setPorcentajeReventa] = useState('');

  const responderOfertaRecibida = async (idOferta, aceptar, porcentajeReventaSolicitado) => {
    try {
      await fetch(`${API_URL}/fichajes/responder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_oferta: idOferta, aceptar, porcentaje_reventa_solicitado: porcentajeReventaSolicitado || null }),
      });
      cargarNegociaciones();
      if (aceptar) { onPresupuestoCambiado?.(); onPlantillaCambiada?.(); }
    } catch (error) {
      console.error('Error respondiendo la oferta:', error);
    }
  };

  const confirmarVenta = async () => {
    if (!ofertaAConfirmar) return;
    setConfirmandoOferta(true);
    await responderOfertaRecibida(ofertaAConfirmar.id_oferta, true, Number(porcentajeReventa) || null);
    setConfirmandoOferta(false);
    setOfertaAConfirmar(null);
    setPorcentajeReventa('');
  };

  // --- método 1: club -> jugador ---
  const [clubes, setClubes] = useState([]);
  const [cargandoClubes, setCargandoClubes] = useState(false);
  const [clubSeleccionado, setClubSeleccionado] = useState(null);
  const [jugadoresClub, setJugadoresClub] = useState([]);
  const [cargandoPlantel, setCargandoPlantel] = useState(false);
  const [filtroClubPos, setFiltroClubPos] = useState('');
  const [filtroClubPosEspecifica, setFiltroClubPosEspecifica] = useState('');
  const jugadoresClubFiltrados = jugadoresClub.filter((j) => {
    if (filtroClubPos && j.posicion !== filtroClubPos) return false;
    if (filtroClubPosEspecifica && j.posicion_especifica !== filtroClubPosEspecifica) return false;
    return true;
  });
  const ordenClub = useOrdenTabla(jugadoresClubFiltrados);

  // --- método 2: buscador (nombre y/o métricas) en toda la liga/mercado ---
  const [filtros, setFiltros] = useState({ nombre: '', club: '', categoria: '', posicion: '', posicionEspecifica: '', edadMin: '', edadMax: '', overallMin: '', orden: 'valor', soloLibres: false });
  const [jugadorAReclutar, setJugadorAReclutar] = useState(null);
  const [resultadosBusqueda, setResultadosBusqueda] = useState([]);
  const [totalBusqueda, setTotalBusqueda] = useState(0);
  const [cargandoBusqueda, setCargandoBusqueda] = useState(false);
  const ordenBusqueda = useOrdenTabla(resultadosBusqueda);

  // --- ficha / negociación ---
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [jugadorADialogar, setJugadorADialogar] = useState(null);
  const [jugadorNegociacion, setJugadorNegociacion] = useState(null);

  useEffect(() => {
    if (!idPartida) return;
    fetch(`${API_URL}/ligas?id_partida=${idPartida}`).then((r) => r.json()).then(setLigas).catch((e) => console.error('Error cargando ligas:', e));
  }, [API_URL, idPartida]);

  useEffect(() => {
    if (!idPartida) return;
    setCargandoClubes(true);
    const qs = idLiga ? `&id_liga=${idLiga}` : '';
    fetch(`${API_URL}/equipos?id_partida=${idPartida}${qs}`)
      .then((r) => r.json())
      .then((data) => setClubes(data.filter((c) => c.id_equipo !== idEquipoUsuario)))
      .catch((e) => console.error('Error cargando clubes:', e))
      .finally(() => setCargandoClubes(false));
  }, [API_URL, idLiga, idEquipoUsuario, idPartida]);

  const abrirClub = (club) => {
    setClubSeleccionado(club);
    setCargandoPlantel(true);
    setFiltroClubPos('');
    setFiltroClubPosEspecifica('');
    fetch(`${API_URL}/equipos/${club.id_equipo}/jugadores`)
      .then((r) => r.json())
      .then(setJugadoresClub)
      .catch((e) => console.error('Error cargando plantel del club:', e))
      .finally(() => setCargandoPlantel(false));
  };

  // Una categoría juvenil (Sub-13/15/18/21) solo tiene sentido buscarla club
  // por club — la Academia de cada club se genera perezosamente, así que
  // "todas las Sub-18 de la liga" sin filtrar por club devolvería nada más
  // que los pocos clubes que alguien ya miró antes, no la liga entera.
  const categoriaEsJuvenil = CATEGORIAS_ACADEMIA.includes(filtros.categoria);

  const buscarJugadores = () => {
    if (categoriaEsJuvenil && !filtros.club.trim()) return;
    setCargandoBusqueda(true);
    const params = new URLSearchParams();
    if (idLiga) params.set('id_liga', idLiga);
    if (filtros.nombre) params.set('nombre', filtros.nombre);
    if (filtros.club) params.set('club', filtros.club);
    if (filtros.categoria) params.set('categoria', filtros.categoria);
    if (filtros.posicion) params.set('posicion', filtros.posicion);
    if (filtros.posicionEspecifica) params.set('posicion_especifica', filtros.posicionEspecifica);
    if (filtros.edadMin) params.set('edad_min', filtros.edadMin);
    if (filtros.edadMax) params.set('edad_max', filtros.edadMax);
    if (filtros.overallMin) params.set('overall_min', filtros.overallMin);
    if (filtros.soloLibres) params.set('solo_libres', 'true');
    params.set('orden', filtros.orden);
    if (idPartida) params.set('id_partida', idPartida);
    fetch(`${API_URL}/mercado/jugadores?${params.toString()}`)
      .then((r) => r.json())
      .then((data) => { setResultadosBusqueda(data.jugadores); setTotalBusqueda(data.total ?? data.jugadores.length); })
      .catch((e) => console.error('Error buscando en el mercado:', e))
      .finally(() => setCargandoBusqueda(false));
  };

  useEffect(() => {
    if (tab === 'buscar') buscarJugadores();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, idLiga]);

  const irABuscar = (posicion = '') => {
    setFiltros((f) => ({ ...f, posicion }));
    setTab('buscar');
  };

  // --- precontrato / fichaje libre (ContractModal) ---
  const [jugadorContrato, setJugadorContrato] = useState(null);
  const [modoContrato, setModoContrato] = useState('precontrato');

  const abrirAccion = (jugador) => {
    setJugadorDetalle(null);
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

  const labelAccion = (j) => (j.es_libre ? 'Fichar libre' : j.elegible_precontrato ? 'Precontrato' : 'Negociar');

  const posicionLabel = (j) => j.posicion_especifica || j.posicion;

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="filtro-liga" className="text-xs text-slate-400 block mb-1">Liga</label>
          <select
            id="filtro-liga"
            value={idLiga}
            onChange={(e) => { setIdLiga(e.target.value); setClubSeleccionado(null); setJugadoresClub([]); }}
            className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
          >
            <option value="">Todas las ligas</option>
            {ligas.map((l) => <option key={l.id_liga} value={l.id_liga}>{l.codigo} — {l.pais}</option>)}
          </select>
        </div>

        <div className="flex gap-2 ml-auto flex-wrap">
          <button
            onClick={() => setTab('resumen')}
            className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'resumen' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
          >
            Resumen
          </button>
          <button
            onClick={() => setTab('buscar')}
            className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'buscar' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
          >
            Buscador
          </button>
          <button
            onClick={() => setTab('clubes')}
            className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'clubes' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
          >
            Explorar por club
          </button>
          <button
            onClick={() => setTab('preseleccion')}
            className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'preseleccion' ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
          >
            ★ Preseleccionados ({preseleccionados.length})
          </button>
          <button
            onClick={() => setTab('negociacion')}
            className={`px-4 py-2 rounded-xl text-xs font-bold ${tab === 'negociacion' ? 'bg-sky-500 text-slate-950' : 'bg-slate-800 text-slate-300'}`}
          >
            En negociación ({negociaciones.recibidas.length})
          </button>
        </div>
      </div>

      {tab === 'resumen' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <button onClick={() => irABuscar(recomendaciones?.posicion_prioritaria)} className="text-left bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-4 transition">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Posición prioritaria</p>
              <p className="text-2xl font-black text-white mt-1">{recomendaciones?.posicion_prioritaria || '—'}</p>
              <p className="text-[11px] text-slate-400 mt-1">Tocá para buscar en el mercado</p>
            </button>
            <button onClick={() => setTab('negociacion')} className="text-left bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-4 transition">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Ofertas recibidas</p>
              <p className="text-2xl font-black text-white mt-1">{negociaciones.recibidas.length}</p>
              <p className="text-[11px] text-slate-400 mt-1">Esperando tu respuesta</p>
            </button>
            <button onClick={() => setTab('negociacion')} className="text-left bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-4 transition">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Compras / Ventas acordadas</p>
              <p className="text-2xl font-black text-white mt-1">
                {negociaciones.comprando.length + negociaciones.vendiendo.length + negociaciones.precontratos_entrantes.length + negociaciones.precontratos_salientes.length}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">Pendientes de la próxima ventana</p>
            </button>
            <button onClick={() => setTab('preseleccion')} className="text-left bg-[#121e36] border border-slate-800 hover:border-sky-500/50 rounded-2xl p-4 transition">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Preseleccionados</p>
              <p className="text-2xl font-black text-white mt-1">{preseleccionados.length}</p>
              <p className="text-[11px] text-slate-400 mt-1">Tu lista de seguimiento</p>
            </button>
          </div>

          {recomendaciones && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(recomendaciones.promedios_por_posicion).map(([pos, valor]) => (
                <div key={pos} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-center">
                  <p className="text-[10px] text-slate-400">Nivel promedio {pos}</p>
                  <p className="text-sm font-bold text-white">{valor || '—'}</p>
                </div>
              ))}
            </div>
          )}

          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-sm font-bold text-white">Recomendaciones para tu equipo</h2>
              <button onClick={() => irABuscar()} className="text-xs text-sky-400 hover:underline shrink-0">Ver todo en el buscador →</button>
            </div>
            <p className="text-[11px] text-slate-400 mb-4">Jugadores del mercado que mejoran tus posiciones más flojas. Tocá uno para buscarlo y negociar.</p>
            {!recomendaciones || recomendaciones.recomendaciones.length === 0 ? (
              <p className="text-xs text-slate-400">No hay recomendaciones disponibles por ahora.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {recomendaciones.recomendaciones.slice(0, 6).map((j) => (
                  <button
                    key={j.id_jugador}
                    onClick={() => irABuscar(j.posicion)}
                    className="text-left flex items-center justify-between gap-3 bg-[#0b1326] border border-slate-800 hover:border-sky-500/50 rounded-xl p-3 text-xs transition"
                  >
                    <div className="min-w-0">
                      <p className="font-bold text-slate-200 truncate">{j.nombre}</p>
                      <p className="text-slate-400 truncate">{j.club} · {j.posicion_especifica || j.posicion} · {j.edad} años</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-bold text-white">{formatOverall(j)} <span className="text-amber-300">/ {formatPotencial(j)}</span></p>
                      <p className="text-sky-400 font-bold">${j.valor_mercado.toLocaleString('es-AR')}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {recomendaciones && recomendaciones.oportunidades_salida.length > 0 && (
            <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
              <h2 className="text-sm font-bold text-white mb-1">Jugadores con salida recomendada</h2>
              <p className="text-[11px] text-slate-400 mb-4">Rinden por debajo del promedio del equipo o suman poco rodaje.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {recomendaciones.oportunidades_salida.slice(0, 4).map((j) => (
                  <div key={j.id_jugador} className="flex items-center justify-between gap-3 bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs">
                    <div className="min-w-0">
                      <p className="font-bold text-slate-200 truncate">{j.nombre}</p>
                      <p className="text-slate-400">{j.posicion_especifica || j.posicion} · {j.edad} años · {j.rol}</p>
                    </div>
                    <p className="font-bold text-sky-400 shrink-0">${j.valor_mercado.toLocaleString('es-AR')}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'clubes' && !clubSeleccionado && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-1">Explorar por club</h2>
          <p className="text-[11px] text-slate-400 mb-4">Elegí un club para ver su plantel completo.</p>
          {cargandoClubes ? (
            <p className="text-xs text-slate-400">Cargando clubes...</p>
          ) : (
            <select
              defaultValue=""
              onChange={(e) => {
                const club = clubes.find((c) => String(c.id_equipo) === e.target.value);
                if (club) abrirClub(club);
              }}
              className="w-full max-w-md bg-[#0b1326] border border-slate-700 p-3 rounded-xl text-white text-sm"
            >
              <option value="" disabled>Seleccioná un club...</option>
              {clubes.map((c) => (
                <option key={c.id_equipo} value={c.id_equipo}>{c.nombre}</option>
              ))}
            </select>
          )}
        </div>
      )}

      {tab === 'clubes' && clubSeleccionado && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-white">Plantel de {clubSeleccionado.nombre}</h2>
            <div className="flex items-center gap-3">
              <Link to={`/club/${clubSeleccionado.id_equipo}`} className="text-xs text-sky-400 hover:underline">Ver panel del club →</Link>
              <button onClick={() => setClubSeleccionado(null)} className="text-xs text-sky-400 hover:underline">← Volver a clubes</button>
            </div>
          </div>
          <div className="flex flex-wrap gap-4 items-end mb-4">
            <div>
              <label htmlFor="filtro-club-pos" className="text-xs text-slate-400 block mb-1">Posición</label>
              <select
                id="filtro-club-pos"
                value={filtroClubPos}
                onChange={(e) => { setFiltroClubPos(e.target.value); setFiltroClubPosEspecifica(''); }}
                className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              >
                <option value="">Todas</option>
                <option value="POR">POR</option>
                <option value="DEF">DEF</option>
                <option value="MED">MED</option>
                <option value="DEL">DEL</option>
              </select>
            </div>
            {filtroClubPos && (
              <div>
                <label htmlFor="filtro-club-pos-especifica" className="text-xs text-slate-400 block mb-1">Específica</label>
                <select
                  id="filtro-club-pos-especifica"
                  value={filtroClubPosEspecifica}
                  onChange={(e) => setFiltroClubPosEspecifica(e.target.value)}
                  className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                >
                  <option value="">Todas</option>
                  {POSICIONES_ESPECIFICAS[filtroClubPos].map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {cargandoPlantel ? (
            <p className="text-xs text-slate-400">Cargando plantel...</p>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="p-3"></th>
                  <ThOrdenable label="Jugador" colKey="nombre" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <ThOrdenable label="Pos" colKey="posicion" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <ThOrdenable label="Edad" colKey="edad" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <ThOrdenable label="Ovr" colKey="overall" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <ThOrdenable label="Valor" colKey="valor_mercado" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <ThOrdenable label="Contrato" colKey="dias_restantes_contrato" sortKey={ordenClub.sortKey} sortDir={ordenClub.sortDir} onClick={ordenClub.clickHeader} />
                  <th className="p-3">Acción</th>
                </tr>
              </thead>
              <tbody>
                {ordenClub.ordenada.map((j) => {
                  const jc = { ...j, club: clubSeleccionado.nombre };
                  return (
                    <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                      <td className="p-3">
                        <button onClick={() => toggleShortlist(jc)} aria-label={estaPreseleccionado(j.id_jugador) ? `Quitar a ${j.nombre} de preseleccionados` : `Agregar a ${j.nombre} a preseleccionados`} aria-pressed={estaPreseleccionado(j.id_jugador)} className={`text-base ${estaPreseleccionado(j.id_jugador) ? 'text-amber-400' : 'text-slate-500 hover:text-slate-300'}`}>★</button>
                      </td>
                      <td
                        className="p-3 font-bold text-slate-200 cursor-pointer focus-visible:outline focus-visible:outline-sky-500"
                        onClick={() => setJugadorDetalle(jc)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setJugadorDetalle(jc); } }}
                        role="button"
                        tabIndex={0}
                        aria-label={`Ver ficha de ${j.nombre}`}
                      >
                        {j.nombre}
                      </td>
                      <td className="p-3 text-sky-400">{posicionLabel(j)}</td>
                      <td className="p-3 text-slate-300">{j.edad}</td>
                      <td className="p-3 font-bold text-white">{formatOverall(j)}</td>
                      <td className="p-3 font-bold text-sky-400">${j.valor_mercado.toLocaleString('es-AR')}</td>
                      <td className="p-3"><BadgeContrato j={jc} /></td>
                      <td className="p-3">
                        <CeldaAccionFichaje j={jc} idsComprando={idsComprando} onAccion={abrirAccion} label={labelAccion(jc)} idEquipoUsuario={idEquipoUsuario} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}

      {tab === 'buscar' && (
        <>
          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 flex flex-wrap gap-3 items-end">
            <div>
              <label htmlFor="filtro-nombre" className="text-xs text-slate-400 block mb-1">Nombre</label>
              <input
                id="filtro-nombre"
                type="text"
                value={filtros.nombre}
                onChange={(e) => setFiltros((f) => ({ ...f, nombre: e.target.value }))}
                onKeyDown={(e) => { if (e.key === 'Enter') buscarJugadores(); }}
                placeholder="Buscar jugador..."
                className="w-40 bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              />
            </div>
            <div>
              <label htmlFor="filtro-club-nombre" className="text-xs text-slate-400 block mb-1">Club</label>
              <input
                id="filtro-club-nombre"
                type="text"
                value={filtros.club}
                onChange={(e) => setFiltros((f) => ({ ...f, club: e.target.value }))}
                onKeyDown={(e) => { if (e.key === 'Enter') buscarJugadores(); }}
                placeholder="Buscar club..."
                className="w-40 bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              />
            </div>
            <div>
              <label htmlFor="filtro-categoria" className="text-xs text-slate-400 block mb-1">Categoría</label>
              <select
                id="filtro-categoria"
                value={filtros.categoria}
                onChange={(e) => setFiltros((f) => ({ ...f, categoria: e.target.value }))}
                className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              >
                <option value="">Primera + Sub-21</option>
                <option value="PRIMERA">Solo Primera</option>
                {CATEGORIAS_ACADEMIA.map((c) => (
                  <option key={c} value={c}>{CATEGORIA_LABEL[c]}</option>
                ))}
              </select>
              {categoriaEsJuvenil && !filtros.club.trim() && (
                <p className="text-[10px] text-amber-400 mt-1 max-w-[160px]">Escribí un club — la Academia se busca club por club.</p>
              )}
            </div>
            <div>
              <label htmlFor="filtro-buscar-pos" className="text-xs text-slate-400 block mb-1">Posición</label>
              <select
                id="filtro-buscar-pos"
                value={filtros.posicion}
                onChange={(e) => setFiltros((f) => ({ ...f, posicion: e.target.value, posicionEspecifica: '' }))}
                className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
              >
                <option value="">Todas</option>
                <option value="POR">POR</option>
                <option value="DEF">DEF</option>
                <option value="MED">MED</option>
                <option value="DEL">DEL</option>
              </select>
            </div>
            {filtros.posicion && (
              <div>
                <label htmlFor="filtro-buscar-pos-especifica" className="text-xs text-slate-400 block mb-1">Específica</label>
                <select
                  id="filtro-buscar-pos-especifica"
                  value={filtros.posicionEspecifica}
                  onChange={(e) => setFiltros((f) => ({ ...f, posicionEspecifica: e.target.value }))}
                  className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                >
                  <option value="">Todas</option>
                  {POSICIONES_ESPECIFICAS[filtros.posicion].map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label htmlFor="filtro-edad-min" className="text-xs text-slate-400 block mb-1">Edad mín.</label>
              <input id="filtro-edad-min" type="number" min="0" max="99" value={filtros.edadMin} onChange={(e) => setFiltros((f) => ({ ...f, edadMin: e.target.value }))} className="w-20 bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs" />
            </div>
            <div>
              <label htmlFor="filtro-edad-max" className="text-xs text-slate-400 block mb-1">Edad máx.</label>
              <input id="filtro-edad-max" type="number" min="0" max="99" value={filtros.edadMax} onChange={(e) => setFiltros((f) => ({ ...f, edadMax: e.target.value }))} className="w-20 bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs" />
            </div>
            <div>
              <label htmlFor="filtro-overall-min" className="text-xs text-slate-400 block mb-1">Overall mín.</label>
              <input id="filtro-overall-min" type="number" min="0" max="99" value={filtros.overallMin} onChange={(e) => setFiltros((f) => ({ ...f, overallMin: e.target.value }))} className="w-20 bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs" />
            </div>
            <div>
              <label htmlFor="filtro-orden" className="text-xs text-slate-400 block mb-1">Ordenar por</label>
              <select id="filtro-orden" value={filtros.orden} onChange={(e) => setFiltros((f) => ({ ...f, orden: e.target.value }))} className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs">
                <option value="valor">Valor</option>
                <option value="overall">Overall</option>
                <option value="edad">Edad</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-300 pb-2">
              <input
                type="checkbox"
                checked={filtros.soloLibres}
                onChange={(e) => setFiltros((f) => ({ ...f, soloLibres: e.target.checked }))}
                className="accent-sky-500"
              />
              Solo agentes libres
            </label>
            <button onClick={buscarJugadores} className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs">
              Aplicar filtros
            </button>
          </div>

          <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
            <h2 className="text-sm font-bold text-white mb-4">
              Resultados ({resultadosBusqueda.length}{totalBusqueda > resultadosBusqueda.length ? ` de ${totalBusqueda}` : ''})
              {totalBusqueda > resultadosBusqueda.length && (
                <span className="text-[11px] font-normal text-slate-400 ml-2">Afiná los filtros para ver más específico</span>
              )}
            </h2>
            {cargandoBusqueda ? (
              <p className="text-xs text-slate-400">Buscando...</p>
            ) : (
              <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="p-3"></th>
                    <ThOrdenable label="Jugador" colKey="nombre" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Club" colKey="club" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Pos" colKey="posicion" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Edad" colKey="edad" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Ovr" colKey="overall" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Valor" colKey="valor_mercado" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <ThOrdenable label="Contrato" colKey="dias_restantes_contrato" sortKey={ordenBusqueda.sortKey} sortDir={ordenBusqueda.sortDir} onClick={ordenBusqueda.clickHeader} />
                    <th className="p-3">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {ordenBusqueda.ordenada.map((j) => {
                    const esJuvenil = j.categoria && j.categoria !== 'PRIMERA';
                    return (
                    <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                      <td className="p-3">
                        <button onClick={() => toggleShortlist(j)} aria-label={estaPreseleccionado(j.id_jugador) ? `Quitar a ${j.nombre} de preseleccionados` : `Agregar a ${j.nombre} a preseleccionados`} aria-pressed={estaPreseleccionado(j.id_jugador)} className={`text-base ${estaPreseleccionado(j.id_jugador) ? 'text-amber-400' : 'text-slate-500 hover:text-slate-300'}`}>★</button>
                      </td>
                      <td
                        className="p-3 font-bold text-slate-200 cursor-pointer focus-visible:outline focus-visible:outline-sky-500"
                        onClick={() => setJugadorDetalle(j)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setJugadorDetalle(j); } }}
                        role="button"
                        tabIndex={0}
                        aria-label={`Ver ficha de ${j.nombre}`}
                      >
                        {j.nombre}
                      </td>
                      <td className="p-3 text-slate-400">
                        {j.id_equipo ? <Link to={`/club/${j.id_equipo}`} className="hover:text-sky-400 hover:underline" onClick={(e) => e.stopPropagation()}>{j.club}</Link> : j.club}
                      </td>
                      <td className="p-3 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                      <td className="p-3 text-slate-300">{j.edad}</td>
                      <td className="p-3 font-bold text-white">{formatOverall(j)}</td>
                      <td className="p-3 font-bold text-sky-400">${j.valor_mercado.toLocaleString('es-AR')}</td>
                      <td className="p-3">
                        {esJuvenil ? (
                          j.fecha_fin_contrato ? (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-500/40">Con contrato</span>
                          ) : (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-500/40">Libre</span>
                          )
                        ) : (
                          <BadgeContrato j={j} />
                        )}
                      </td>
                      <td className="p-3">
                        {esJuvenil ? (
                          j.fecha_fin_contrato ? (
                            <button onClick={() => setJugadorNegociacion(j)} className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-1 rounded text-xs">
                              Negociar
                            </button>
                          ) : (
                            <button onClick={() => setJugadorAReclutar(j)} className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-3 py-1 rounded text-xs">
                              Reclutar
                            </button>
                          )
                        ) : (
                          <CeldaAccionFichaje j={j} idsComprando={idsComprando} onAccion={abrirAccion} label={labelAccion(j)} idEquipoUsuario={idEquipoUsuario} />
                        )}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            )}
          </div>
        </>
      )}

      {tab === 'preseleccion' && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-4">Jugadores Preseleccionados ({preseleccionados.length})</h2>
          {preseleccionados.length === 0 ? (
            <p className="text-xs text-slate-400">Todavía no marcaste ningún jugador. Tocá la ★ en las tablas de clubes o de búsqueda.</p>
          ) : (
            <>
            <div className="flex flex-wrap gap-4 items-end mb-4">
              <div>
                <label htmlFor="filtro-presel-pos" className="text-xs text-slate-400 block mb-1">Posición</label>
                <select
                  id="filtro-presel-pos"
                  value={filtroPreselPos}
                  onChange={(e) => { setFiltroPreselPos(e.target.value); setFiltroPreselPosEspecifica(''); }}
                  className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                >
                  <option value="">Todas</option>
                  <option value="POR">POR</option>
                  <option value="DEF">DEF</option>
                  <option value="MED">MED</option>
                  <option value="DEL">DEL</option>
                </select>
              </div>
              {filtroPreselPos && (
                <div>
                  <label htmlFor="filtro-presel-pos-especifica" className="text-xs text-slate-400 block mb-1">Específica</label>
                  <select
                    id="filtro-presel-pos-especifica"
                    value={filtroPreselPosEspecifica}
                    onChange={(e) => setFiltroPreselPosEspecifica(e.target.value)}
                    className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                  >
                    <option value="">Todas</option>
                    {POSICIONES_ESPECIFICAS[filtroPreselPos].map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="p-3"></th>
                  <ThOrdenable label="Jugador" colKey="nombre" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Club" colKey="club" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Pos" colKey="posicion" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Edad" colKey="edad" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Ovr" colKey="overall" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Valor" colKey="valor_mercado" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <ThOrdenable label="Contrato" colKey="dias_restantes_contrato" sortKey={ordenPresel.sortKey} sortDir={ordenPresel.sortDir} onClick={ordenPresel.clickHeader} />
                  <th className="p-3">Acción</th>
                </tr>
              </thead>
              <tbody>
                {ordenPresel.ordenada.map((j) => (
                  <tr key={j.id_jugador} className="border-b border-slate-800/40 hover:bg-[#0b1326]">
                    <td className="p-3">
                      <button onClick={() => toggleShortlist(j)} aria-label={`Quitar a ${j.nombre} de preseleccionados`} aria-pressed="true" className="text-base text-amber-400">★</button>
                    </td>
                    <td
                      className="p-3 font-bold text-slate-200 cursor-pointer focus-visible:outline focus-visible:outline-sky-500"
                      onClick={() => setJugadorDetalle(j)}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setJugadorDetalle(j); } }}
                      role="button"
                      tabIndex={0}
                      aria-label={`Ver ficha de ${j.nombre}`}
                    >
                      {j.nombre}
                    </td>
                    <td className="p-3 text-slate-400">{j.club}</td>
                    <td className="p-3 text-sky-400" title={j.posicion}>{j.posicion_especifica || j.posicion}</td>
                    <td className="p-3 text-slate-300">{j.edad}</td>
                    <td className="p-3 font-bold text-white">{formatOverall(j)}</td>
                    <td className="p-3 font-bold text-sky-400">${j.valor_mercado.toLocaleString('es-AR')}</td>
                    <td className="p-3"><BadgeContrato j={j} /></td>
                    <td className="p-3">
                      <CeldaAccionFichaje j={j} idsComprando={idsComprando} onAccion={abrirAccion} label={labelAccion(j)} idEquipoUsuario={idEquipoUsuario} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            </>
          )}
        </div>
      )}

      {tab === 'negociacion' && (
        <div className="space-y-6">
          {cargandoNegociaciones ? (
            <p className="text-xs text-slate-400">Cargando negociaciones...</p>
          ) : (
            <>
              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-5 flex flex-wrap gap-4 items-end">
                <div>
                  <label htmlFor="filtro-neg-pos" className="text-xs text-slate-400 block mb-1">Posición</label>
                  <select
                    id="filtro-neg-pos"
                    value={filtroNegPos}
                    onChange={(e) => { setFiltroNegPos(e.target.value); setFiltroNegPosEspecifica(''); }}
                    className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                  >
                    <option value="">Todas</option>
                    <option value="POR">POR</option>
                    <option value="DEF">DEF</option>
                    <option value="MED">MED</option>
                    <option value="DEL">DEL</option>
                  </select>
                </div>
                {filtroNegPos && (
                  <div>
                    <label htmlFor="filtro-neg-pos-especifica" className="text-xs text-slate-400 block mb-1">Específica</label>
                    <select
                      id="filtro-neg-pos-especifica"
                      value={filtroNegPosEspecifica}
                      onChange={(e) => setFiltroNegPosEspecifica(e.target.value)}
                      className="bg-[#0b1326] border border-slate-700 p-2 rounded-lg text-white text-xs"
                    >
                      <option value="">Todas</option>
                      {POSICIONES_ESPECIFICAS[filtroNegPos].map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-1">Ofertas recibidas por tus jugadores ({filtrarPorPosicion(negociaciones.recibidas).length})</h2>
                <p className="text-[11px] text-slate-400 mb-4">Esperando tu respuesta.</p>
                {filtrarPorPosicion(negociaciones.recibidas).length === 0 ? (
                  <p className="text-xs text-slate-400">No tenés ofertas pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {filtrarPorPosicion(negociaciones.recibidas).map((o) => (
                      <div key={o.id_oferta} className="bg-[#0b1326] border border-slate-800 rounded-xl p-3 text-xs space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-bold text-slate-200">{o.nombre_jugador} <span className="text-slate-400">({o.posicion_especifica || o.posicion} · Ovr {o.overall})</span></p>
                            <p className="text-slate-400 mt-0.5">
                              <Link to={`/club/${o.id_equipo_comprador}`} className="hover:text-sky-400 hover:underline">{o.nombre_comprador}</Link> ofrece ${o.monto_oferta.toLocaleString('es-AR')}
                            </p>
                          </div>
                          {ofertaAConfirmar?.id_oferta !== o.id_oferta && (
                            <div className="flex gap-2 shrink-0">
                              <button onClick={() => setOfertaAConfirmar(o)} className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-3 py-1.5 rounded-lg">Aceptar</button>
                              <button onClick={() => responderOfertaRecibida(o.id_oferta, false)} className="bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 px-3 py-1.5 rounded-lg">Rechazar</button>
                            </div>
                          )}
                        </div>
                        {ofertaAConfirmar?.id_oferta === o.id_oferta && (
                          <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-lg p-3 space-y-2">
                            <p className="text-emerald-300">
                              Confirmás la venta de <span className="font-bold">{o.nombre_jugador}</span> a {o.nombre_comprador} por ${o.monto_oferta.toLocaleString('es-AR')}. Sale de tu plantel.
                            </p>
                            <div className="flex items-center gap-2">
                              <label htmlFor={`reventa-${o.id_oferta}`} className="text-[11px] text-emerald-300/80 shrink-0">
                                % de reventa futura (opcional):
                              </label>
                              <input
                                id={`reventa-${o.id_oferta}`}
                                type="number" min="1" max="100" placeholder="0"
                                value={porcentajeReventa}
                                onChange={(e) => setPorcentajeReventa(e.target.value)}
                                className="w-16 bg-[#0b1326] border border-slate-700 p-1.5 rounded-lg text-white text-[11px]"
                              />
                              <span className="text-[11px] text-emerald-300/80">
                                — si {o.nombre_comprador} lo revende después, cobrás ese % de esa venta.
                              </span>
                            </div>
                            <div className="flex gap-2 shrink-0 pt-1">
                              <button
                                onClick={confirmarVenta}
                                disabled={confirmandoOferta}
                                className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1.5 rounded-lg"
                              >
                                {confirmandoOferta ? 'Vendiendo...' : 'Sí, vender'}
                              </button>
                              <button
                                onClick={() => { setOfertaAConfirmar(null); setPorcentajeReventa(''); }}
                                disabled={confirmandoOferta}
                                className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 px-3 py-1.5 rounded-lg"
                              >
                                Cancelar
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-1">Compras acordadas ({filtrarPorPosicion(negociaciones.comprando).length})</h2>
                <p className="text-[11px] text-slate-400 mb-4">Pendientes de que abra la próxima ventana de mercado.</p>
                {filtrarPorPosicion(negociaciones.comprando).length === 0 ? (
                  <p className="text-xs text-slate-400">No tenés compras pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {filtrarPorPosicion(negociaciones.comprando).map((o) => (
                      <div key={o.id_oferta} className="bg-[#0b1326] border border-emerald-500/30 rounded-xl p-3 text-xs">
                        <p className="font-bold text-slate-200">{o.nombre_jugador} <span className="text-slate-400">({o.posicion_especifica || o.posicion} · Ovr {formatOverall(o)})</span></p>
                        <p className="text-emerald-400 mt-0.5">
                          Le pagás a <Link to={`/club/${o.id_equipo_vendedor}`} className="hover:underline">{o.nombre_vendedor}</Link>: ${o.monto_oferta.toLocaleString('es-AR')}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-1">Ventas acordadas ({filtrarPorPosicion(negociaciones.vendiendo).length})</h2>
                <p className="text-[11px] text-slate-400 mb-4">Pendientes de que abra la próxima ventana de mercado.</p>
                {filtrarPorPosicion(negociaciones.vendiendo).length === 0 ? (
                  <p className="text-xs text-slate-400">No tenés ventas pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {filtrarPorPosicion(negociaciones.vendiendo).map((o) => (
                      <div key={o.id_oferta} className="bg-[#0b1326] border border-amber-500/30 rounded-xl p-3 text-xs">
                        <p className="font-bold text-slate-200">{o.nombre_jugador} <span className="text-slate-400">({o.posicion_especifica || o.posicion} · Ovr {o.overall})</span></p>
                        <p className="text-amber-400 mt-0.5">
                          Te paga <Link to={`/club/${o.id_equipo_comprador}`} className="hover:underline">{o.nombre_comprador}</Link>: ${o.monto_oferta.toLocaleString('es-AR')}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-1">Precontratos firmados — se suman a tu club ({filtrarPorPosicion(negociaciones.precontratos_entrantes).length})</h2>
                <p className="text-[11px] text-slate-400 mb-4">Se incorporan libres cuando termine su contrato actual.</p>
                {filtrarPorPosicion(negociaciones.precontratos_entrantes).length === 0 ? (
                  <p className="text-xs text-slate-400">No tenés precontratos entrantes pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {filtrarPorPosicion(negociaciones.precontratos_entrantes).map((j) => (
                      <div key={j.id_jugador} className="bg-[#0b1326] border border-emerald-500/30 rounded-xl p-3 text-xs">
                        <p className="font-bold text-slate-200">{j.nombre_jugador} <span className="text-slate-400">({j.posicion_especifica || j.posicion} · Ovr {formatOverall(j)})</span></p>
                        <p className="text-emerald-400 mt-0.5">
                          Hoy en {j.id_equipo_club ? <Link to={`/club/${j.id_equipo_club}`} className="hover:underline">{j.nombre_club}</Link> : j.nombre_club} · libre el {j.fecha_fin_contrato ? new Date(`${j.fecha_fin_contrato}T00:00:00`).toLocaleDateString('es-AR') : '?'} · ${j.salario_precontrato?.toLocaleString('es-AR')}/semana
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6">
                <h2 className="text-sm font-bold text-white mb-1">Precontratos firmados — se van de tu club ({filtrarPorPosicion(negociaciones.precontratos_salientes).length})</h2>
                <p className="text-[11px] text-slate-400 mb-4">Se van libres cuando termine su contrato actual con vos.</p>
                {filtrarPorPosicion(negociaciones.precontratos_salientes).length === 0 ? (
                  <p className="text-xs text-slate-400">No tenés precontratos salientes pendientes.</p>
                ) : (
                  <div className="space-y-2">
                    {filtrarPorPosicion(negociaciones.precontratos_salientes).map((j) => (
                      <div key={j.id_jugador} className="bg-[#0b1326] border border-amber-500/30 rounded-xl p-3 text-xs">
                        <p className="font-bold text-slate-200">{j.nombre_jugador} <span className="text-slate-400">({j.posicion_especifica || j.posicion} · Ovr {j.overall})</span></p>
                        <p className="text-amber-400 mt-0.5">
                          Se va a {j.id_equipo_club ? <Link to={`/club/${j.id_equipo_club}`} className="hover:underline">{j.nombre_club}</Link> : j.nombre_club} el {j.fecha_fin_contrato ? new Date(`${j.fecha_fin_contrato}T00:00:00`).toLocaleDateString('es-AR') : '?'} · ${j.salario_precontrato?.toLocaleString('es-AR')}/semana
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      <PlayerDetailModal
        jugador={jugadorDetalle}
        open={!!jugadorDetalle}
        onClose={() => setJugadorDetalle(null)}
        API_URL={API_URL}
        onNegociar={jugadorDetalle && !jugadorDetalle.es_libre && !jugadorDetalle.elegible_precontrato ? () => abrirAccion(jugadorDetalle) : undefined}
        onPrecontrato={jugadorDetalle && !jugadorDetalle.es_libre && jugadorDetalle.elegible_precontrato && !jugadorDetalle.id_equipo_precontrato ? () => abrirAccion(jugadorDetalle) : undefined}
        onFicharLibre={jugadorDetalle && jugadorDetalle.es_libre ? () => abrirAccion(jugadorDetalle) : undefined}
        onEnviarOjeador={jugadorDetalle ? () => navigate(`/cuerpo-tecnico?asignar=${jugadorDetalle.id_jugador}`) : undefined}
        onHablar={jugadorDetalle ? () => { setJugadorADialogar(jugadorDetalle); setJugadorDetalle(null); } : undefined}
      />
      <DialogoJugadorModal
        jugador={jugadorADialogar}
        open={!!jugadorADialogar}
        onClose={() => setJugadorADialogar(null)}
        API_URL={API_URL}
        idEquipoInteresado={idEquipoUsuario}
      />

      <ContractModal
        open={!!jugadorContrato}
        onClose={() => setJugadorContrato(null)}
        jugador={jugadorContrato}
        modo={modoContrato}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onResuelto={() => { if (tab === 'buscar') buscarJugadores(); cargarNegociaciones(); onPresupuestoCambiado?.(); onPlantillaCambiada?.(); }}
      />

      <NegociacionFichajeModal
        jugador={jugadorNegociacion}
        open={!!jugadorNegociacion}
        onClose={() => setJugadorNegociacion(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onResuelto={() => { if (tab === 'buscar') buscarJugadores(); cargarNegociaciones(); onPresupuestoCambiado?.(); onPlantillaCambiada?.(); }}
      />

      <ConfirmarReclutamientoModal
        jugador={jugadorAReclutar}
        open={!!jugadorAReclutar}
        onClose={() => setJugadorAReclutar(null)}
        API_URL={API_URL}
        idEquipoUsuario={idEquipoUsuario}
        onConfirmado={() => {
          setJugadorAReclutar(null);
          if (tab === 'buscar') buscarJugadores();
          onPresupuestoCambiado?.();
        }}
      />
    </div>
  );
}
