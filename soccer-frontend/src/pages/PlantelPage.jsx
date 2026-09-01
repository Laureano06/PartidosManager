import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import PlayerDetailModal from '../components/PlayerDetailModal';
import ContractModal from '../components/ContractModal';
import OfrecerJugadorModal from '../components/OfrecerJugadorModal';
import CederPrestamoModal from '../components/CederPrestamoModal';
import DialogoJugadorModal from '../components/DialogoJugadorModal';
import Bandera from '../components/Bandera';
import { formatearDuracion } from '../utils/formato';
import { useDragScroll } from '../utils/useDragScroll';
import { CATEGORIAS_ACADEMIA, CATEGORIA_LABEL, puedeMoverACategoria } from '../utils/academia';

const ROL_LABEL = { TITULAR: 'Titular', SUPLENTE: 'Suplente', RESERVA: 'Reserva' };
const ROL_CLASS = {
  TITULAR: 'bg-emerald-950 text-emerald-400 border border-emerald-500/40',
  SUPLENTE: 'bg-amber-950 text-amber-400 border border-amber-500/40',
  RESERVA: 'bg-slate-800 text-slate-400 border border-slate-700',
};

const ROL_ORDEN = { TITULAR: 0, SUPLENTE: 1, RESERVA: 2 };
const POSICION_ORDEN = { POR: 0, DEF: 1, MED: 2, DEL: 3 };

const PLANTILLAS = ['PRIMERA', ...CATEGORIAS_ACADEMIA];

const COLUMNAS_PRIMERA = [
  { key: 'rol', label: 'Rol' },
  { key: 'nombre', label: 'Nombre' },
  { key: 'posicion', label: 'Pos' },
  { key: 'nacionalidad', label: 'Nac' },
  { key: 'edad', label: 'Edad' },
  { key: 'ataque', label: 'Atq' },
  { key: 'defensa', label: 'Def' },
  { key: 'fisico', label: 'Fís' },
  { key: 'overall', label: 'Ovr' },
  { key: 'valor_mercado', label: 'Valor' },
  { key: 'salario', label: 'Salario/sem' },
  { key: 'dias_restantes_contrato', label: 'Contrato' },
];

const COLUMNAS_ACADEMIA = [
  { key: 'nombre', label: 'Nombre' },
  { key: 'posicion', label: 'Pos' },
  { key: 'nacionalidad', label: 'Nac' },
  { key: 'edad', label: 'Edad' },
  { key: 'ataque', label: 'Atq' },
  { key: 'defensa', label: 'Def' },
  { key: 'fisico', label: 'Fís' },
  { key: 'overall', label: 'Ovr' },
  { key: 'potencial', label: 'Pot' },
  { key: null, label: '' },
];

function valorOrdenable(j, key) {
  if (key === 'rol') return ROL_ORDEN[j.rol] ?? 9;
  if (key === 'posicion') return POSICION_ORDEN[j.posicion] ?? 9;
  return j[key];
}

export default function PlantelPage({ plantilla, setPlantilla, API_URL, idEquipoUsuario, idPartida }) {
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [jugadorContrato, setJugadorContrato] = useState(null);
  const [jugadorAOfrecer, setJugadorAOfrecer] = useState(null);
  const [jugadorACeder, setJugadorACeder] = useState(null);
  const [jugadorADialogar, setJugadorADialogar] = useState(null);
  // Por defecto agrupado Titular → Suplente → Reserva, no en el orden en que
  // vino de la base.
  const [sortKey, setSortKey] = useState('rol');
  const [sortDir, setSortDir] = useState('asc');
  const { ref, dragHandlers } = useDragScroll();

  const [searchParams, setSearchParams] = useSearchParams();
  const categoriaParam = (searchParams.get('categoria') || 'PRIMERA').toUpperCase();
  const [categoriaActiva, setCategoriaActiva] = useState(PLANTILLAS.includes(categoriaParam) ? categoriaParam : 'PRIMERA');
  const [academia, setAcademia] = useState(null); // {sub13, sub15, sub18, sub21} — se pide una sola vez
  const [cargandoAcademia, setCargandoAcademia] = useState(false);

  useEffect(() => {
    if (categoriaActiva === 'PRIMERA' || academia || !idEquipoUsuario) return;
    setCargandoAcademia(true);
    fetch(`${API_URL}/equipos/${idEquipoUsuario}/academia`)
      .then((r) => r.json())
      .then(setAcademia)
      .catch((e) => console.error('Error cargando academia:', e))
      .finally(() => setCargandoAcademia(false));
  }, [categoriaActiva, academia, API_URL, idEquipoUsuario]);

  const elegirPlantilla = (categoria) => {
    setCategoriaActiva(categoria);
    setSearchParams(categoria === 'PRIMERA' ? {} : { categoria });
  };

  const listaActual = categoriaActiva === 'PRIMERA'
    ? plantilla
    : (academia?.[categoriaActiva.toLowerCase()] || []);

  const moverCategoria = async (jugador, categoriaDestino) => {
    try {
      const r = await fetch(`${API_URL}/jugadores/${jugador.id_jugador}/categoria`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ categoria: categoriaDestino }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(err.detail || 'No se pudo mover al jugador de categoría.');
        return;
      }
      // El jugador deja la categoría actual — se saca de la vista local sin
      // esperar un refetch completo, y se invalida el cache de academia para
      // que la próxima vez que se mire una categoría venga actualizada.
      setAcademia(null);
      if (categoriaActiva === 'PRIMERA') {
        setPlantilla((prev) => prev.filter((j) => j.id_jugador !== jugador.id_jugador));
      }
    } catch (error) {
      console.error('Error moviendo de categoría:', error);
    }
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

  const elegirAccion = (jugador, accion) => {
    if (accion === 'renovar') setJugadorContrato(jugador);
    else if (accion === 'transferible') toggleTransferible(jugador);
    else if (accion === 'ofrecer') setJugadorAOfrecer(jugador);
    else if (accion === 'ceder') setJugadorACeder(jugador);
    else if (accion.startsWith('mover:')) moverCategoria(jugador, accion.slice('mover:'.length));
  };

  // Al cederlo, el jugador deja de pertenecer a este plantel (pasa al
  // club prestamista) — lo sacamos de la lista local sin esperar a un
  // refetch completo.
  const quitarDePlantelPorCesion = (idJugador) => {
    setPlantilla((prev) => prev.filter((j) => j.id_jugador !== idJugador));
  };

  const clickHeader = (key) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const plantelOrdenado = useMemo(() => {
    if (!sortKey) return listaActual;
    const copia = [...listaActual];
    copia.sort((a, b) => {
      const va = valorOrdenable(a, sortKey);
      const vb = valorOrdenable(b, sortKey);
      const cmp = (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * (sortDir === 'asc' ? 1 : -1);
      if (cmp !== 0) return cmp;
      // Empate (p. ej. varios titulares): agrupar por posición en el orden
      // de la cancha (POR, DEF, MED, DEL), no como vinieron de la base.
      if (sortKey === 'rol') {
        const pa = POSICION_ORDEN[a.posicion] ?? 9;
        const pb = POSICION_ORDEN[b.posicion] ?? 9;
        if (pa !== pb) return pa - pb;
        return b.overall - a.overall;
      }
      return 0;
    });
    return copia;
  }, [listaActual, sortKey, sortDir]);

  const columnas = categoriaActiva === 'PRIMERA' ? COLUMNAS_PRIMERA : COLUMNAS_ACADEMIA;

  return (
    <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 flex flex-col h-full min-h-0 gap-4">
      <div className="flex items-center justify-between shrink-0 flex-wrap gap-3">
        <h2 className="text-base font-bold text-white">
          {CATEGORIA_LABEL[categoriaActiva]} ({listaActual.length} Jugadores)
        </h2>
        <div className="flex gap-1 bg-[#0b1326] p-1 rounded-xl border border-slate-800">
          {PLANTILLAS.map((cat) => (
            <button
              key={cat}
              onClick={() => elegirPlantilla(cat)}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition ${
                categoriaActiva === cat ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-white'
              }`}
            >
              {CATEGORIA_LABEL[cat]}
            </button>
          ))}
        </div>
      </div>
      {cargandoAcademia && categoriaActiva !== 'PRIMERA' && (
        <p className="text-xs text-slate-500 shrink-0">Cargando Academia...</p>
      )}
      <div ref={ref} {...dragHandlers} className="flex-1 min-h-0 overflow-auto scroll-slide cursor-grab">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="sticky top-0 bg-[#121e36] z-10">
            <tr className="border-b border-slate-800 text-slate-400">
              {columnas.map((col) => (
                <th
                  key={col.key || '_accion'}
                  onClick={col.key ? () => clickHeader(col.key) : undefined}
                  className={`p-3 select-none whitespace-nowrap ${col.key ? 'cursor-pointer hover:text-sky-400 transition' : ''}`}
                >
                  {col.label}
                  {sortKey === col.key && <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {plantelOrdenado.map((j) => (
              <tr
                key={j.id_jugador}
                onClick={() => setJugadorDetalle(j)}
                className="border-b border-slate-800/40 hover:bg-[#0b1326]/60 cursor-pointer"
              >
                {categoriaActiva === 'PRIMERA' && (
                  <td className="p-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${ROL_CLASS[j.rol] || ROL_CLASS.RESERVA}`}>
                      {ROL_LABEL[j.rol] || j.rol}
                    </span>
                  </td>
                )}
                <td className="p-3 font-bold text-slate-200 whitespace-nowrap">
                  {j.nombre}
                  {j.en_transferible && (
                    <span title="En lista de transferibles" className="ml-1.5 text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-400 text-slate-950 align-middle">
                      LISTA
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <span className="bg-[#0b1326] text-sky-400 px-2 py-0.5 rounded font-bold" title={j.posicion}>
                    {j.posicion_especifica || j.posicion}
                  </span>
                </td>
                <td className="p-3 whitespace-nowrap"><Bandera pais={j.nacionalidad} /></td>
                <td className="p-3 text-slate-300">{j.edad}</td>
                <td className="p-3 font-bold text-sky-300">{j.ataque}</td>
                <td className="p-3 font-bold text-blue-300">{j.defensa}</td>
                <td className="p-3 text-emerald-400">{j.fisico}</td>
                <td className="p-3 font-bold text-white">{j.overall}</td>
                {categoriaActiva === 'PRIMERA' ? (
                  <>
                    <td className="p-3 font-bold text-slate-300 whitespace-nowrap">${j.valor_mercado.toLocaleString('es-AR')}</td>
                    <td className="p-3 text-slate-400 whitespace-nowrap">${j.salario.toLocaleString('es-AR')}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-24 shrink-0 text-right whitespace-nowrap ${j.dias_restantes_contrato != null && j.dias_restantes_contrato <= 180 ? 'text-amber-400 font-bold' : 'text-slate-400'}`}>
                          {formatearDuracion(j.dias_restantes_contrato)}
                        </span>
                        <select
                          value=""
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => { elegirAccion(j, e.target.value); e.target.value = ''; }}
                          className="w-32 shrink-0 text-[10px] bg-slate-800 hover:bg-slate-700 text-sky-400 px-2 py-1 rounded font-bold border-none cursor-pointer"
                        >
                          <option value="" disabled>Acciones ▾</option>
                          <option value="renovar">Renovar contrato</option>
                          <option value="transferible">{j.en_transferible ? 'Sacar de transferibles' : 'Poner en transferibles'}</option>
                          <option value="ofrecer">Ofrecer a equipos</option>
                          <option value="ceder">Ceder a préstamo</option>
                          {PLANTILLAS.filter((c) => c !== 'PRIMERA' && puedeMoverACategoria(j.edad, c)).map((c) => (
                            <option key={c} value={`mover:${c}`}>Mover a {CATEGORIA_LABEL[c]}</option>
                          ))}
                        </select>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="p-3 font-bold text-amber-300">{j.potencial}</td>
                    <td className="p-3">
                      <select
                        value=""
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => { elegirAccion(j, e.target.value); e.target.value = ''; }}
                        className="w-36 shrink-0 text-[10px] bg-slate-800 hover:bg-slate-700 text-sky-400 px-2 py-1 rounded font-bold border-none cursor-pointer"
                      >
                        <option value="" disabled>Mover a ▾</option>
                        {PLANTILLAS.filter((c) => c !== categoriaActiva && puedeMoverACategoria(j.edad, c)).map((c) => (
                          <option key={c} value={`mover:${c}`}>{CATEGORIA_LABEL[c]}</option>
                        ))}
                      </select>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PlayerDetailModal
        jugador={jugadorDetalle}
        open={!!jugadorDetalle}
        onClose={() => setJugadorDetalle(null)}
        API_URL={API_URL}
        onRenovar={jugadorDetalle ? () => { setJugadorContrato(jugadorDetalle); setJugadorDetalle(null); } : undefined}
        onToggleTransferible={jugadorDetalle ? () => toggleTransferible(jugadorDetalle) : undefined}
        onOfrecer={jugadorDetalle ? () => { setJugadorAOfrecer(jugadorDetalle); setJugadorDetalle(null); } : undefined}
        onCeder={jugadorDetalle ? () => { setJugadorACeder(jugadorDetalle); setJugadorDetalle(null); } : undefined}
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
        modo="renovar"
        API_URL={API_URL}
        onResuelto={() => {
          fetch(`${API_URL}/equipos/${idEquipoUsuario}/jugadores`).then((r) => r.json()).then(setPlantilla).catch(() => {});
        }}
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
        onResuelto={() => jugadorACeder && quitarDePlantelPorCesion(jugadorACeder.id_jugador)}
      />
    </div>
  );
}
