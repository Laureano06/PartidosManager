import PlayerFace from '../components/PlayerFace';
import React, { useEffect, useMemo, useState } from 'react';
import Modal from '../components/Modal';
import PlayerDetailModal from '../components/PlayerDetailModal';
import { setRolJugador, setDutyJugador } from '../utils/roles';
import { FORMACIONES_SLOTS, FORMACIONES_LABEL } from '../utils/formaciones';

const ROL_ORDEN = { TITULAR: 0, SUPLENTE: 1, RESERVA: 2 };
const BANCO_SIZE = 9;

// La alineación se deriva de plantilla+formación, salvo los slots con una
// asignación manual (jugador puesto fuera de su posición natural), que se
// respetan mientras el jugador siga siendo titular. Solo se usan jugadores
// con rol TITULAR — si no hay ninguno para una posición, el lugar queda
// vacío en vez de disimularlo con un suplente o una reserva.
function calcularAlineacion(plantilla, slots, asignacionManual) {
  const disponibles = { POR: [], DEF: [], MED: [], DEL: [] };
  plantilla.forEach((j) => { if (j.rol === 'TITULAR' && disponibles[j.posicion]) disponibles[j.posicion].push(j); });
  Object.keys(disponibles).forEach((pos) => {
    disponibles[pos].sort((a, b) => b.overall - a.overall);
  });

  const usados = new Set();
  const resultado = slots.map((slot, i) => {
    const idManual = asignacionManual[i];
    if (idManual != null) {
      const jugadorManual = plantilla.find((j) => j.id_jugador === idManual && j.rol === 'TITULAR');
      if (jugadorManual) {
        usados.add(jugadorManual.id_jugador);
        return jugadorManual;
      }
    }
    return null;
  });

  resultado.forEach((val, i) => {
    if (val) return;
    const slot = slots[i];
    const candidato = disponibles[slot.pos]?.find((j) => !usados.has(j.id_jugador));
    if (candidato) {
      usados.add(candidato.id_jugador);
      resultado[i] = candidato;
    }
  });

  // Una ubicación manual fuera de su posición natural puede dejar a otro
  // titular sin categoría disponible (por ejemplo, un MED en el lugar de un
  // DEL). Completar los huecos con los titulares aún no usados garantiza
  // siempre once jugadores en la cancha y los marca como fuera de posición.
  const restantes = plantilla
    .filter((j) => j.rol === 'TITULAR' && !usados.has(j.id_jugador))
    .sort((a, b) => b.overall - a.overall);
  let siguiente = 0;
  resultado.forEach((val, i) => {
    if (val || siguiente >= restantes.length) return;
    resultado[i] = restantes[siguiente];
    usados.add(restantes[siguiente].id_jugador);
    siguiente += 1;
  });

  return resultado;
}

function PanelBanca({ titulo, jugadores, rolDestino, vacio, panelSobrevolado, onDragOverPanel, onDragLeavePanel, onDropPanel, onVerFicha, horizontal, downward, bare, jugadorSeleccionado, onToggleSeleccion, onColocarAqui }) {
  const modoColocar = jugadorSeleccionado != null;
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); onDragOverPanel(rolDestino); }}
      onDragLeave={() => onDragLeavePanel(rolDestino)}
      onDrop={(e) => onDropPanel(e, rolDestino)}
      onClick={() => onColocarAqui(rolDestino)}
      onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onColocarAqui(rolDestino); } }}
      role={modoColocar ? 'button' : undefined}
      tabIndex={modoColocar ? 0 : undefined}
      aria-label={modoColocar ? `Enviar a ${titulo}` : undefined}
      className={`transition ${
        bare
          ? 'shrink-0'
          : `bg-[#121e36] border rounded-2xl p-4 ${horizontal ? '' : 'space-y-2 h-full flex flex-col min-h-0'} ${
              panelSobrevolado === rolDestino || modoColocar ? 'border-sky-500' : 'border-slate-800'
            }`
      }`}
    >
      <h4 className="text-xs font-bold text-slate-300 uppercase shrink-0 mb-2">{titulo} ({jugadores.length})</h4>
      <div className={horizontal ? 'flex flex-row gap-2 overflow-x-auto scroll-slide pb-1' : downward ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2' : 'space-y-2 overflow-y-auto scroll-slide min-h-0 flex-1 pr-1 max-h-56'}>
        {jugadores.map((j) => {
          const seleccionado = jugadorSeleccionado === j.id_jugador;
          return (
          <div
            key={j.id_jugador}
            draggable
            onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(j.id_jugador)); }}
            onClick={(e) => { e.stopPropagation(); if (modoColocar) onColocarAqui(rolDestino); else onToggleSeleccion(j.id_jugador); }}
            className={`p-2 rounded-xl border bg-[#0b1326] hover:border-sky-500/50 cursor-grab active:cursor-grabbing text-xs flex justify-between items-center transition gap-2 ${
              seleccionado ? 'border-sky-400 ring-1 ring-sky-400' : 'border-slate-800'
            } ${horizontal ? 'shrink-0 w-40' : ''}`}
          >
            <PlayerFace player={j} className="fm-list-face" /><div className="flex-1 min-w-0">
              <p className="font-bold text-slate-200 truncate">{j.nombre}</p>
              <p className="text-[10px] text-slate-400">Ovr {j.overall}</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); onToggleSeleccion(j.id_jugador); }}
              aria-label={seleccionado ? `Cancelar mover a ${j.nombre}` : `Mover a ${j.nombre}`}
              aria-pressed={seleccionado}
              title="Mover con teclado/click (alternativa a arrastrar)"
              className={`text-[10px] w-5 h-5 rounded flex items-center justify-center shrink-0 ${
                seleccionado ? 'bg-sky-400 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              ⇄
            </button>
            <span className="text-[10px] bg-slate-800 text-sky-400 px-1.5 py-0.5 rounded font-bold shrink-0" title={j.posicion}>{j.posicion_especifica || j.posicion}</span>
          </div>
          );
        })}
        {jugadores.length === 0 && <p className="text-[11px] text-slate-400 shrink-0">{vacio}</p>}
      </div>
    </div>
  );
}

// El banco de suplentes tiene siempre 9 lugares fijos: si sobran jugadores
// no entran (hay que bajar a alguien primero) y si faltan, el lugar queda
// vacío en vez de que el banco achique o agrande su tamaño.
function BancoSuplentes({ slots, slotSobrevolado, onDragOverSlot, onDragLeaveSlot, onDropSlot, onVerFicha, vertical, bare, jugadorSeleccionado, onToggleSeleccion, onColocarEn }) {
  const ocupados = slots.filter(Boolean).length;
  const modoColocar = jugadorSeleccionado != null;
  return (
    <div className={bare ? 'shrink-0' : `bg-[#121e36] border border-slate-800 rounded-2xl p-4 ${vertical ? 'h-full flex flex-col min-h-0' : ''}`}>
      <h4 className="text-xs font-bold text-slate-300 uppercase mb-2 shrink-0">Banco de Suplentes ({ocupados}/{BANCO_SIZE})</h4>
      <div className={vertical ? 'flex flex-col gap-1 overflow-y-auto scroll-slide min-h-0' : 'grid grid-cols-3 sm:grid-cols-9 gap-2'}>
        {slots.map((j, i) => {
          const seleccionado = !!j && jugadorSeleccionado === j.id_jugador;
          return (
          <div
            key={i}
            draggable={!!j}
            onDragStart={j ? (e) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(j.id_jugador)); } : undefined}
            onDragOver={(e) => { e.preventDefault(); onDragOverSlot(i); }}
            onDragLeave={() => onDragLeaveSlot(i)}
            onDrop={(e) => onDropSlot(e, i)}
            onClick={() => { if (modoColocar) onColocarEn(i); else if (j) onToggleSeleccion(j.id_jugador); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (modoColocar) onColocarEn(i); else if (j) onToggleSeleccion(j.id_jugador); } }}
            role="button"
            tabIndex={0}
            aria-label={j ? `${j.nombre}, ${j.posicion_especifica || j.posicion}, overall ${j.overall}${modoColocar ? ' — click para ubicar acá' : ' — click para seleccionar y mover'}` : `Lugar ${i + 1} del banco, vacío${modoColocar ? ' — click para ubicar acá' : ''}`}
            className={`h-16 rounded-xl border p-1.5 flex items-center justify-center text-center transition focus-visible:outline focus-visible:outline-sky-500 ${
              j ? 'bg-[#0b1326] cursor-grab active:cursor-grabbing' : 'border-dashed cursor-pointer'
            } ${seleccionado ? 'ring-1 ring-sky-400' : ''} ${slotSobrevolado === i || (modoColocar && !seleccionado) ? 'border-sky-400 scale-105' : 'border-slate-800'}`}
          >
            {j ? (
              <div className="min-w-0 flex items-center gap-2"><PlayerFace player={j} className="fm-list-face" />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-200 truncate">{j.nombre}</p>
                  <p className="text-[10px] text-slate-400">{j.posicion_especifica || j.posicion} · Ovr {j.overall}</p>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleSeleccion(j.id_jugador); }}
                  aria-label={seleccionado ? `Cancelar mover a ${j.nombre}` : `Mover a ${j.nombre}`}
                  aria-pressed={seleccionado}
                  title="Mover con teclado/click (alternativa a arrastrar)"
                  className={`text-[9px] w-4 h-4 rounded flex items-center justify-center shrink-0 ${
                    seleccionado ? 'bg-sky-400 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  ⇄
                </button>
              </div>
            ) : (
              <span className="text-[10px] text-slate-400">Vacío</span>
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

export default function TacticasPage({ plantilla, setPlantilla, API_URL, idEquipoUsuario }) {
  const [formacion, setFormacion] = useState('4-4-2');
  const [mentalidad, setMentalidad] = useState('BALANCEADA');
  const [presion, setPresion] = useState('MEDIA');
  const [cargandoTactica, setCargandoTactica] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [mensajeGuardado, setMensajeGuardado] = useState(null);
  const [jugadorDetalle, setJugadorDetalle] = useState(null);
  const [jugadorTactica, setJugadorTactica] = useState(null);
  const [slotSobrevolado, setSlotSobrevolado] = useState(null);
  const [panelSobrevolado, setPanelSobrevolado] = useState(null); // 'suplentes' | 'reserva' | null
  const [asignacionManual, setAsignacionManual] = useState({});
  const [ordenBanco, setOrdenBanco] = useState([]); // ids de jugador, en el orden de sus 9 lugares fijos
  const [slotBancoSobrevolado, setSlotBancoSobrevolado] = useState(null);
  // Alternativa a arrastrar con el mouse: "levantar" un jugador con un click
  // o el teclado y después click/Enter en el destino — mismo patrón que ya
  // usa PanelCambios en MatchDayPage para las sustituciones, acá aplicado a
  // los 3 tipos de destino (cancha, banco, panel de reserva). Sin esto la
  // interacción central de la página era 100% drag-and-drop nativo, sin
  // ningún camino para teclado ni táctil confiable.
  const [jugadorSeleccionado, setJugadorSeleccionado] = useState(null);

  useEffect(() => {
    if (jugadorSeleccionado == null) return;
    const onKey = (e) => { if (e.key === 'Escape') setJugadorSeleccionado(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [jugadorSeleccionado]);

  // Trae la táctica ya guardada del equipo, para que al volver a esta
  // página (o recargar) se mantenga la formación/mentalidad/presión
  // elegidas en vez de arrancar siempre de los valores por defecto.
  useEffect(() => {
    if (!idEquipoUsuario) return;
    fetch(`${API_URL}/tacticas/${idEquipoUsuario}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        if (data.formacion) setFormacion(data.formacion);
        if (data.mentalidad) setMentalidad(data.mentalidad);
        if (data.presion) setPresion(data.presion);
      })
      .catch((error) => console.error('Error cargando la táctica guardada:', error))
      .finally(() => setCargandoTactica(false));
  }, [API_URL, idEquipoUsuario]);

  const slots = FORMACIONES_SLOTS[formacion];

  // Al cambiar de formación los índices de slot ya no significan lo mismo.
  useEffect(() => { setAsignacionManual({}); }, [formacion]);

  const alineacion = useMemo(() => calcularAlineacion(plantilla, slots, asignacionManual), [plantilla, slots, asignacionManual]);

  const idsEnCancha = useMemo(
    () => new Set(alineacion.filter(Boolean).map((j) => j.id_jugador)),
    [alineacion]
  );
  const fueraDeCancha = useMemo(
    () => plantilla
      .filter((j) => !idsEnCancha.has(j.id_jugador))
      .sort((a, b) => (ROL_ORDEN[a.rol] - ROL_ORDEN[b.rol]) || b.overall - a.overall),
    [plantilla, idsEnCancha]
  );
  const suplentes = useMemo(() => fueraDeCancha.filter((j) => j.rol !== 'RESERVA'), [fueraDeCancha]);
  const reserva = useMemo(() => fueraDeCancha.filter((j) => j.rol === 'RESERVA'), [fueraDeCancha]);

  // Mantiene ordenBanco sincronizado con quiénes son SUPLENTE ahora mismo:
  // saca a los que ya no lo son (los subieron a titular o los bajaron a
  // reserva) y ubica a los nuevos en el primer lugar libre — nunca más de
  // BANCO_SIZE, así el banco no puede agrandarse por arriba de 9.
  useEffect(() => {
    setOrdenBanco((prev) => {
      const idsSuplentes = new Set(suplentes.map((j) => j.id_jugador));
      const next = prev.filter((id) => id != null && idsSuplentes.has(id));
      suplentes.forEach((j) => {
        if (!next.includes(j.id_jugador) && next.length < BANCO_SIZE) next.push(j.id_jugador);
      });
      const sinCambios = next.length === prev.length && next.every((id, i) => id === prev[i]);
      return sinCambios ? prev : next;
    });
  }, [suplentes]);

  const bancoSlots = useMemo(
    () => Array.from({ length: BANCO_SIZE }, (_, i) => {
      const id = ordenBanco[i];
      return id != null ? plantilla.find((j) => j.id_jugador === id) ?? null : null;
    }),
    [ordenBanco, plantilla]
  );

  const cambiarRolLocal = (jugador, nuevoRol) => {
    setPlantilla((prev) => prev.map((j) => (j.id_jugador === jugador.id_jugador ? { ...j, rol: nuevoRol } : j)));
    setRolJugador(API_URL, jugador.id_jugador, nuevoRol).catch((error) => console.error('Error cambiando rol:', error));
  };

  const cambiarDuty = (jugador, duty) => {
    setPlantilla((prev) => prev.map((j) => (j.id_jugador === jugador.id_jugador ? { ...j, duty } : j)));
    setDutyJugador(API_URL, jugador.id_jugador, duty).catch((error) => console.error('Error cambiando duty:', error));
  };

  const limpiarAsignacionDe = (idJugador) => {
    setAsignacionManual((prev) => {
      const next = { ...prev };
      Object.keys(next).forEach((k) => { if (next[k] === idJugador) delete next[k]; });
      return next;
    });
  };

  const mandarAPanel = (jugador, rolDestino) => {
    limpiarAsignacionDe(jugador.id_jugador);
    cambiarRolLocal(jugador, rolDestino);
  };

  // Al soltar sobre un slot de la cancha, según de dónde venga el jugador:
  // - Si ya era titular en OTRO lugar de la cancha, es una reubicación entre
  //   dos titulares: cada uno pasa al lugar del otro, ninguno sale al banco.
  // - Si venía de un lugar puntual del banco, el titular saliente ocupa
  //   exactamente ese mismo lugar (cambio real, no uno cualquiera).
  // - Si venía de reserva o de otro lado, el titular saliente pasa a
  //   suplente (o a reserva si el banco ya está lleno).
  // Si el jugador no coincide con la posición del slot, queda marcado como
  // fuera de posición (se resalta en amarillo al renderizar).
  const moverASlot = (jugadorId, slotIndex) => {
    const jugador = plantilla.find((j) => j.id_jugador === jugadorId);
    if (!jugador) return;
    const ocupanteActual = alineacion[slotIndex];
    if (ocupanteActual?.id_jugador === jugador.id_jugador) return;

    const idxCanchaOrigen = alineacion.findIndex((j) => j?.id_jugador === jugadorId);

    setAsignacionManual((prev) => {
      const next = { ...prev };
      // Se limpia cualquier asignación manual previa de ambos jugadores
      // involucrados, para reconstruirla de cero según corresponda.
      Object.keys(next).forEach((k) => {
        if (next[k] === jugadorId || (ocupanteActual && next[k] === ocupanteActual.id_jugador)) delete next[k];
      });
      // Se fija el slot elegido siempre, coincida o no con la posición
      // natural: el relleno automático ubica a cada titular en el primer
      // lugar libre de su posición en orden fijo, así que sin esta marca
      // mover a alguien a OTRO lugar vacío de su misma posición no tendría
      // ningún efecto (el algoritmo lo volvería a poner donde estaba).
      next[slotIndex] = jugadorId;
      if (idxCanchaOrigen !== -1 && ocupanteActual) next[idxCanchaOrigen] = ocupanteActual.id_jugador;
      return next;
    });

    if (idxCanchaOrigen !== -1) return; // reubicación entre titulares: nadie cambia de rol

    if (ocupanteActual) {
      const idxBancoOrigen = ordenBanco.indexOf(jugadorId);
      if (idxBancoOrigen !== -1) {
        // Cambio real: el titular saliente va exactamente al lugar del
        // banco que dejó libre el que entra, no a cualquier otro.
        const next = [...ordenBanco];
        next[idxBancoOrigen] = ocupanteActual.id_jugador;
        setOrdenBanco(next);
        cambiarRolLocal(ocupanteActual, 'SUPLENTE');
      } else {
        // Venía de reserva (o de otro lado sin lugar puntual): si el banco
        // ya está lleno, no hay dónde meterlo, pasa directo a reserva.
        cambiarRolLocal(ocupanteActual, suplentes.length >= BANCO_SIZE ? 'RESERVA' : 'SUPLENTE');
      }
    }
    if (jugador.rol !== 'TITULAR') cambiarRolLocal(jugador, 'TITULAR');
  };

  const soltarEnSlot = (e, slotIndex) => {
    e.preventDefault();
    setSlotSobrevolado(null);
    moverASlot(Number(e.dataTransfer.getData('text/plain')), slotIndex);
  };

  // Suelta sobre un lugar puntual del banco de suplentes: si viene de otro
  // lugar del banco, reordena (swap); si viene de la cancha o de reserva,
  // ocupa ese lugar y, si ya había alguien ahí, lo manda a reserva.
  const moverABanco = (jugadorId, slotIndex) => {
    const jugador = plantilla.find((j) => j.id_jugador === jugadorId);
    if (!jugador) return;

    // "Ya está en el banco" se define por ocupar uno de los 9 lugares, no
    // por el campo rol: un titular que no entra en la cancha por formación
    // también se muestra en el banco, y hay que poder reordenarlo igual.
    const idxOrigen = ordenBanco.indexOf(jugadorId);
    const yaEnBanco = idxOrigen !== -1;
    if (yaEnBanco && idxOrigen === slotIndex) return;

    // Se arma "next" con el ordenBanco actual (no con el updater de
    // setState) porque después necesitamos saber sincrónicamente a quién
    // desplazamos, para bajarlo a reserva.
    const next = [...ordenBanco];
    while (next.length < BANCO_SIZE) next.push(null);
    const ocupanteId = next[slotIndex];

    if (yaEnBanco) {
      next[idxOrigen] = ocupanteId ?? null;
    }
    next[slotIndex] = jugadorId;
    setOrdenBanco(next);

    if (!yaEnBanco && ocupanteId != null) {
      const ocupante = plantilla.find((j) => j.id_jugador === ocupanteId);
      if (ocupante) cambiarRolLocal(ocupante, 'RESERVA');
    }
    if (jugador.rol !== 'SUPLENTE') {
      limpiarAsignacionDe(jugador.id_jugador);
      cambiarRolLocal(jugador, 'SUPLENTE');
    }
  };

  const soltarEnBanco = (e, slotIndex) => {
    e.preventDefault();
    setSlotBancoSobrevolado(null);
    moverABanco(Number(e.dataTransfer.getData('text/plain')), slotIndex);
  };

  // Acepta tanto bajar a alguien de la cancha (era TITULAR) como mover un
  // jugador al panel de Reserva (era TITULAR/SUPLENTE).
  const moverAPanel = (jugadorId, rolDestino) => {
    const jugador = plantilla.find((j) => j.id_jugador === jugadorId);
    if (!jugador || jugador.rol === rolDestino) return;
    mandarAPanel(jugador, rolDestino);
  };

  const soltarEnPanel = (e, rolDestino) => {
    e.preventDefault();
    setPanelSobrevolado(null);
    moverAPanel(Number(e.dataTransfer.getData('text/plain')), rolDestino);
  };

  // Único punto de entrada del modo teclado/click: "coloca" al jugador
  // levantado (jugadorSeleccionado) en el destino elegido, sea cual sea su
  // tipo, y cierra la selección. No hace nada si no hay nadie levantado —
  // así los mismos manejadores de destino sirven aunque todavía no se
  // seleccionó a nadie.
  const colocarSeleccionadoEn = (tipo, arg) => {
    if (jugadorSeleccionado == null) return;
    if (tipo === 'slot') moverASlot(jugadorSeleccionado, arg);
    else if (tipo === 'banco') moverABanco(jugadorSeleccionado, arg);
    else if (tipo === 'panel') moverAPanel(jugadorSeleccionado, arg);
    setJugadorSeleccionado(null);
  };

  const toggleSeleccion = (idJugador) => {
    setJugadorSeleccionado((prev) => (prev === idJugador ? null : idJugador));
  };

  const guardarTactica = async () => {
    if (!idEquipoUsuario) return;
    setGuardando(true);
    try {
      const res = await fetch(`${API_URL}/tacticas/configurar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_equipo: idEquipoUsuario, formacion, mentalidad, presion, estilo_pase: 'MIXTO' }),
      });
      const data = await res.json();
      setMensajeGuardado(data.mensaje || 'Táctica guardada.');
    } catch (error) {
      console.error('Error guardando la táctica:', error);
      setMensajeGuardado('No se pudo conectar con el servidor.');
    } finally {
      setGuardando(false);
      setTimeout(() => setMensajeGuardado(null), 4000);
    }
  };

  const iniciales = (nombre) => nombre.split(' ').pop();

  if (cargandoTactica) {
    return <p className="text-xs text-slate-400">Cargando táctica...</p>;
  }

  return (
    <div className="fm-tactics">
      <div className="fm-tactics-controls space-y-4">
        <h2 className="text-lg font-bold text-white">Tácticas</h2>
        <div>
          <label htmlFor="tacticas-formacion" className="text-xs text-slate-400 block mb-1">Formación</label>
          <select id="tacticas-formacion" value={formacion} onChange={(e) => setFormacion(e.target.value)} className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-xs text-white">
            {Object.keys(FORMACIONES_SLOTS).map((f) => (
              <option key={f} value={f}>{FORMACIONES_LABEL[f]}</option>
            ))}
          </select>
          <p className="text-[10px] text-slate-400 mt-1">Cambiar la formación reinicia las ubicaciones manuales que hayas hecho en la cancha.</p>
        </div>
        <div>
          <label htmlFor="tacticas-mentalidad" className="text-xs text-slate-400 block mb-1">Mentalidad</label>
          <select id="tacticas-mentalidad" value={mentalidad} onChange={(e) => setMentalidad(e.target.value)} className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-xs text-white">
            <option value="ULTRA_DEFENSIVA">Ultra defensiva</option>
            <option value="DEFENSIVA">Defensiva</option>
            <option value="BALANCEADA">Balanceada</option>
            <option value="OFENSIVA">Ofensiva</option>
            <option value="PRESION_ALTA">Presión alta (todo al ataque)</option>
          </select>
        </div>
        <div>
          <label htmlFor="tacticas-presion" className="text-xs text-slate-400 block mb-1">Presión</label>
          <select id="tacticas-presion" value={presion} onChange={(e) => setPresion(e.target.value)} className="w-full bg-[#0b1326] border border-slate-700 p-2.5 rounded-xl text-xs text-white">
            <option value="BAJA">Baja</option>
            <option value="MEDIA">Media</option>
            <option value="ALTA">Alta</option>
          </select>
        </div>
        <button
          onClick={guardarTactica}
          disabled={guardando}
          className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs"
        >
          {guardando ? 'Guardando...' : 'Guardar Táctica'}
        </button>
        {mensajeGuardado && <p className="text-[11px] text-emerald-400">{mensajeGuardado}</p>}
        <p className="text-[11px] text-slate-400 pt-2 border-t border-slate-800">
          Arrastrá un jugador de los paneles a la cancha para hacerlo titular, o de la cancha a los paneles de suplentes o reserva para sacarlo. Vos elegís a quién reemplaza. Si lo ponés en una posición que no es la suya, la posición se marca en amarillo.
          <br /><br />
          Para cambiar jugadores: hacé click en un suplente o reserva para seleccionarlo y después click (o Enter) en su lugar de la cancha. Escape cancela.
          <br /><br />
          Hacé click en un titular de la cancha para ajustar su instrucción individual de ataque y defensa.
        </p>
      </div>

      <div className="fm-tactics-field">
        <div className="fm-pitch">
          <div className="absolute inset-3 border-2 border-emerald-800/40 rounded-lg" />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-1/3 aspect-square rounded-full border-2 border-emerald-800/40" />

          {slots.map((slot, i) => {
            const j = alineacion[i];
            const fueraDePosicion = !!j && j.posicion !== slot.pos;
            const seleccionado = !!j && jugadorSeleccionado === j.id_jugador;
            const modoColocar = jugadorSeleccionado != null;
            return (
              <div
                key={i}
                onDragOver={(e) => { e.preventDefault(); setSlotSobrevolado(i); }}
                onDragLeave={() => setSlotSobrevolado((s) => (s === i ? null : s))}
                onDrop={(e) => soltarEnSlot(e, i)}
                onClick={!j ? () => colocarSeleccionadoEn('slot', i) : undefined}
                onKeyDown={!j ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); colocarSeleccionadoEn('slot', i); } } : undefined}
                role={!j ? 'button' : undefined}
                tabIndex={!j ? 0 : undefined}
                aria-label={!j ? `Lugar vacío en cancha (${slot.posEspecifica || slot.pos})${modoColocar ? ' — click para ubicar acá' : ''}` : undefined}
                style={{ left: `${slot.x}%`, top: `${Math.min(88, Math.max(12, 100 - slot.y))}%` }}
                className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center transition focus-visible:outline focus-visible:outline-sky-500 ${
                  slotSobrevolado === i ? 'scale-110' : ''
                }`}
              >
                {j ? (
                  <>
                    <div
                      draggable
                      onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(j.id_jugador)); }}
                      onClick={() => { if (modoColocar) colocarSeleccionadoEn('slot', i); else setJugadorTactica(j); }}
                      className="cursor-grab active:cursor-grabbing flex flex-col items-center gap-0.5"
                      title={
                        fueraDePosicion
                          ? `${j.nombre} juega fuera de su posición natural (${j.posicion_especifica || j.posicion})`
                          : `${j.nombre} — natural: ${j.posicion_especifica || j.posicion}`
                      }
                    >
                      <PlayerFace player={j} API_URL={API_URL} className="fm-pitch-face" />
                      <span className={`fm-pitch-name px-2 py-0.5 rounded-full text-[10px] font-black shadow-lg border bg-[#121e36] text-white whitespace-nowrap ${
                        seleccionado ? 'ring-1 ring-sky-400' : ''
                      } ${fueraDePosicion ? 'border-amber-400' : 'border-sky-400'}`}>
                        {j.nombre.split(' ').slice(-2).join(' ')}
                      </span>
                      <span className="text-[9px] text-sky-300 font-bold bg-[#121e36]/80 px-1 rounded">{j.overall}</span>
                      <span className={`text-[8px] font-black px-1.5 py-px rounded-full ${
                        fueraDePosicion ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {slot.posEspecifica || slot.pos}
                      </span>
                    </div>
                    <div className="flex mt-0.5 items-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleSeleccion(j.id_jugador); }}
                        aria-label={seleccionado ? `Cancelar mover a ${j.nombre}` : `Mover a ${j.nombre}`}
                        aria-pressed={seleccionado}
                        title="Mover con teclado/click (alternativa a arrastrar)"
                        className={`w-3.5 h-3.5 rounded-sm text-[7px] font-black leading-none flex items-center justify-center ml-0.5 ${
                          seleccionado ? 'bg-sky-400 text-slate-950' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        ⇄
                      </button>
                    </div>
                  </>
                ) : (
                  <div
                    className={`w-10 h-10 rounded-full border-2 border-dashed flex items-center justify-center text-[9px] font-bold ${
                      slotSobrevolado === i || modoColocar ? 'border-sky-400 text-sky-400' : 'border-slate-700 text-slate-400'
                    }`}
                  >
                    {slot.posEspecifica || slot.pos}
                  </div>
                )}
              </div>
            );
          })}
        </div>

      </div>

      <div className="fm-tactics-roster min-h-0">
        <BancoSuplentes
          slots={bancoSlots}
          slotSobrevolado={slotBancoSobrevolado}
          onDragOverSlot={setSlotBancoSobrevolado}
          onDragLeaveSlot={(i) => setSlotBancoSobrevolado((s) => (s === i ? null : s))}
          onDropSlot={soltarEnBanco}
          onVerFicha={setJugadorDetalle}
          jugadorSeleccionado={jugadorSeleccionado}
          onToggleSeleccion={toggleSeleccion}
          onColocarEn={(i) => colocarSeleccionadoEn('banco', i)}
          vertical
        />
      </div>

      <div className="fm-tactics-reserves">
        <PanelBanca
          titulo="Reserva" jugadores={reserva} rolDestino="RESERVA" vacio="No hay jugadores en reserva."
          panelSobrevolado={panelSobrevolado}
          onDragOverPanel={setPanelSobrevolado}
          onDragLeavePanel={(rol) => setPanelSobrevolado((s) => (s === rol ? null : s))}
          onDropPanel={soltarEnPanel}
          onVerFicha={setJugadorDetalle}
          jugadorSeleccionado={jugadorSeleccionado}
          onToggleSeleccion={toggleSeleccion}
          onColocarAqui={(rol) => colocarSeleccionadoEn('panel', rol)}
          downward
        />
      </div>

      <PlayerDetailModal jugador={jugadorDetalle} open={!!jugadorDetalle} onClose={() => setJugadorDetalle(null)} API_URL={API_URL} />
      <Modal open={!!jugadorTactica} onClose={() => setJugadorTactica(null)} size="sm" labelledBy="ajuste-tactico-titulo">
        {jugadorTactica && (
          <div className="p-5 space-y-5">
            <div className="flex items-center gap-3">
              <PlayerFace player={jugadorTactica} API_URL={API_URL} className="w-14 h-16" />
              <div>
                <h3 id="ajuste-tactico-titulo" className="font-bold text-white">{jugadorTactica.nombre}</h3>
                <p className="text-xs text-slate-400">Instrucción individual</p>
              </div>
            </div>
            <p className="text-sm text-slate-300">Definí cuánto participa en ataque o prioriza la defensa.</p>
            <div className="grid gap-2">
              {[
                ['DEFENSIVO', 'Defensivo', 'Prioriza la recuperación y la cobertura.', 'border-sky-500 text-sky-200'],
                ['EQUILIBRADO', 'Equilibrado', 'Mantiene su rol natural en ambas fases.', 'border-slate-500 text-slate-100'],
                ['OFENSIVO', 'Ofensivo', 'Se proyecta más durante los ataques.', 'border-emerald-500 text-emerald-200'],
              ].map(([valor, titulo, descripcion, color]) => (
                <button
                  key={valor}
                  onClick={() => { cambiarDuty(jugadorTactica, valor); setJugadorTactica(null); }}
                  className={`rounded-xl border p-3 text-left transition hover:bg-slate-800 ${
                    (jugadorTactica.duty || 'EQUILIBRADO') === valor ? `${color} bg-slate-800` : 'border-slate-700 text-slate-300'
                  }`}
                >
                  <span className="block font-bold text-sm">{titulo}</span>
                  <span className="block text-xs text-slate-400 mt-1">{descripcion}</span>
                </button>
              ))}
            </div>
            <button onClick={() => setJugadorTactica(null)} className="w-full rounded-xl border border-slate-700 py-2 text-sm text-slate-300 hover:bg-slate-800">Cancelar</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
