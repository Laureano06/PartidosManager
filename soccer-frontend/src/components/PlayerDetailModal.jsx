import React, { useEffect, useMemo, useState } from 'react';
import Modal from './Modal';
import MiniPitchPosicion from './MiniPitchPosicion';
import { formatearDuracion } from '../utils/formato';
import { formatOverall, formatPotencial } from '../utils/scouting';

const ROL_LABEL = { TITULAR: 'Titular', SUPLENTE: 'Suplente', RESERVA: 'Reserva' };
const ROL_CLASS = {
  TITULAR: 'bg-emerald-950 text-emerald-400 border-emerald-500/40',
  SUPLENTE: 'bg-amber-950 text-amber-400 border-amber-500/40',
  RESERVA: 'bg-slate-800 text-slate-400 border-slate-700',
};

const ATRIBUTOS_TECNICO = [
  ['finalizacion', 'Finalización'], ['regate', 'Regate'], ['primer_toque', 'Primer Toque'], ['centros', 'Centros'],
  ['cabeceo', 'Cabeceo'], ['marcaje', 'Marcaje'], ['entradas', 'Entradas'], ['tiros_lejanos', 'Tiros Lejanos'], ['pase', 'Pase'],
];
const ATRIBUTOS_MENTAL = [
  ['agresividad', 'Agresividad'], ['valentia', 'Valentía'], ['decisiones', 'Decisiones'], ['concentracion', 'Concentración'],
  ['anticipacion', 'Anticipación'], ['compostura', 'Compostura'], ['vision', 'Visión'], ['liderazgo', 'Liderazgo'],
];
const ATRIBUTOS_FISICO = [
  ['ritmo', 'Ritmo'], ['aceleracion', 'Aceleración'], ['resistencia', 'Resistencia'], ['fuerza', 'Fuerza'], ['agilidad', 'Agilidad'],
];

// Roles simplificados por posición amplia (no el motor de roles completo de
// FM) — cada uno es un promedio de los atributos que más pesan en ese rol,
// solo para dar una idea rápida de para qué encaja mejor el jugador.
const ROLES_POR_POSICION = {
  POR: [
    { nombre: 'Arquero Tradicional', attrs: ['porteria', 'valentia', 'compostura', 'anticipacion'] },
    { nombre: 'Arquero-Líbero', attrs: ['porteria', 'pase', 'primer_toque', 'decisiones'] },
  ],
  DEF: [
    { nombre: 'Defensor Central', attrs: ['marcaje', 'entradas', 'cabeceo', 'fuerza'] },
    { nombre: 'Lateral Ofensivo', attrs: ['centros', 'ritmo', 'resistencia', 'entradas'] },
    { nombre: 'Defensor con Salida', attrs: ['pase', 'vision', 'decisiones', 'marcaje'] },
  ],
  MED: [
    { nombre: 'Mediocampista Defensivo', attrs: ['marcaje', 'entradas', 'decisiones', 'resistencia'] },
    { nombre: 'Organizador', attrs: ['pase', 'vision', 'decisiones', 'primer_toque'] },
    { nombre: 'Media Punta', attrs: ['finalizacion', 'regate', 'vision', 'primer_toque'] },
  ],
  DEL: [
    { nombre: 'Cazagoles', attrs: ['finalizacion', 'anticipacion', 'compostura', 'primer_toque'] },
    { nombre: 'Extremo', attrs: ['regate', 'ritmo', 'aceleracion', 'centros'] },
    { nombre: 'Falso 9', attrs: ['pase', 'vision', 'primer_toque', 'decisiones'] },
  ],
};

function promedio(jugador, attrs) {
  const valores = attrs.map((a) => jugador[a]).filter((v) => v != null);
  if (!valores.length) return null;
  return Math.round(valores.reduce((a, b) => a + b, 0) / valores.length);
}

function Stat({ label, value }) {
  if (value === undefined || value === null) return null;
  return (
    <div className="flex justify-between border-b border-slate-800/60 py-2.5">
      <span className="text-slate-400">{label}</span>
      <span className="font-bold text-slate-100">{value}</span>
    </div>
  );
}

function ListaAtributos({ titulo, items, jugador }) {
  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-4">
      <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-2">{titulo}</h4>
      <div className="space-y-0.5">
        {items.map(([clave, label]) => (
          <div key={clave} className="flex justify-between text-xs py-1.5 border-b border-slate-800/40 last:border-0">
            <span className="text-slate-400">{label}</span>
            <span className="font-bold text-slate-100">{jugador[clave] ?? '-'}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RadarChart({ ejes }) {
  const cx = 100, cy = 100, r = 80;
  const n = ejes.length;
  const angulo = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const punto = (i, valor) => {
    const a = angulo(i);
    const radio = r * (Math.max(0, Math.min(99, valor)) / 99);
    return [cx + radio * Math.cos(a), cy + radio * Math.sin(a)];
  };
  const poligono = (factor) =>
    Array.from({ length: n }, (_, i) => punto(i, 99 * factor).join(',')).join(' ');
  const valores = ejes.map((e, i) => punto(i, e.valor).join(',')).join(' ');
  // Etiquetas afuera del SVG (una leyenda chica abajo) en vez de texto sobre
  // el propio radar: con solo 3-4 ejes el radio queda chico y el texto de
  // categorías como "Portería" no entra sin recortarse contra el viewBox.
  return (
    <div>
      <svg viewBox="0 0 200 200" className="w-full max-w-[200px] mx-auto">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <polygon key={f} points={poligono(f)} fill="none" stroke="#1e293b" strokeWidth="1" />
        ))}
        {ejes.map((_, i) => {
          const [x, y] = punto(i, 99);
          return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="#1e293b" strokeWidth="1" />;
        })}
        <polygon points={valores} fill="rgba(56,189,248,0.35)" stroke="#38bdf8" strokeWidth="2" />
        {ejes.map((e, i) => {
          const [x, y] = punto(i, e.valor);
          return <circle key={i} cx={x} cy={y} r="3" fill="#38bdf8" />;
        })}
      </svg>
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
        {ejes.map((e) => (
          <span key={e.label} className="text-[11px] text-slate-400">
            <span className="text-sky-300 font-bold">{e.label}</span> {e.valor}
          </span>
        ))}
      </div>
    </div>
  );
}

function RolesEfectivos({ jugador }) {
  const roles = ROLES_POR_POSICION[jugador.posicion] || [];
  const puntuados = roles
    .map((r) => ({ ...r, puntaje: promedio(jugador, r.attrs) }))
    .filter((r) => r.puntaje != null)
    .sort((a, b) => b.puntaje - a.puntaje);

  if (!puntuados.length) return null;

  return (
    <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-4">
      <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Roles más efectivos</h4>
      <div className="space-y-3">
        {puntuados.map((r) => (
          <div key={r.nombre}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-300 font-bold">{r.nombre}</span>
              <span className="text-sky-400 font-bold">{r.puntaje}</span>
            </div>
            <div className="w-full bg-[#121e36] h-1.5 rounded-full overflow-hidden border border-slate-800">
              <div className="bg-sky-400 h-full" style={{ width: `${r.puntaje}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PlayerDetailModal({ jugador, open, onClose, API_URL, onNegociar, onRenovar, onPrecontrato, onFicharLibre, onToggleTransferible, onOfrecer, onCeder, onEnviarOjeador, onHablar }) {
  const [historial, setHistorial] = useState([]);
  const [detalle, setDetalle] = useState(null);

  useEffect(() => {
    if (!open || !jugador?.id_jugador || !API_URL) { setHistorial([]); setDetalle(null); return; }
    fetch(`${API_URL}/jugadores/${jugador.id_jugador}/historial`)
      .then((r) => r.json())
      .then((data) => setHistorial(data.historial || []))
      .catch(() => setHistorial([]));
    // El listado que abrió el modal puede traer solo una versión liviana del
    // jugador (mercado, recomendaciones, etc.) — pedimos la ficha completa
    // acá para tener siempre el desglose de atributos nuevos disponible,
    // sin tener que tocar cada endpoint de listado.
    fetch(`${API_URL}/jugadores/${jugador.id_jugador}`)
      .then((r) => r.json())
      .then(setDetalle)
      .catch(() => setDetalle(null));
  }, [open, jugador?.id_jugador, API_URL]);

  const datos = useMemo(() => ({ ...jugador, ...detalle }), [jugador, detalle]);

  if (!jugador) return null;

  const esLibre = datos.es_libre || datos.club === 'Agente Libre';
  const diasRestantes = datos.dias_restantes_contrato ?? datos.dias_restantes;
  // Desglose completo solo para plantel propio (nunca fogueado, scouting_progreso
  // no viene en la respuesta) o para un ajeno ya scouteado al 100%.
  const desgloseDisponible = datos.finalizacion != null && (datos.scouting_progreso === undefined || datos.scouting_progreso >= 100);

  const ejesRadar = desgloseDisponible
    ? [
        { label: 'Técnico', valor: promedio(datos, ATRIBUTOS_TECNICO.map(([c]) => c)) ?? 0 },
        { label: 'Mental', valor: promedio(datos, ATRIBUTOS_MENTAL.map(([c]) => c)) ?? 0 },
        { label: 'Físico', valor: promedio(datos, ATRIBUTOS_FISICO.map(([c]) => c)) ?? 0 },
        ...(datos.posicion === 'POR' ? [{ label: 'Portería', valor: datos.porteria ?? 0 }] : []),
      ]
    : [];

  return (
    <Modal open={open} onClose={onClose}>
      <div className="p-8 sm:p-12 max-w-5xl mx-auto space-y-8">
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h3 className="text-3xl font-black text-white">{datos.nombre}</h3>
            <p className="text-sm text-slate-400 mt-1">{datos.club || 'Tu plantel'} · {datos.nacionalidad}</p>
            {datos.rol && (
              <span className={`inline-block mt-3 text-xs font-bold px-3 py-1 rounded-full border ${ROL_CLASS[datos.rol] || ROL_CLASS.RESERVA}`}>
                {ROL_LABEL[datos.rol] || datos.rol}
              </span>
            )}
            {esLibre ? (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-sky-950 text-sky-300 border-sky-500/40">
                Agente Libre
              </span>
            ) : diasRestantes != null && (
              <span className={`inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border ${
                diasRestantes <= 180 ? 'bg-amber-950 text-amber-300 border-amber-500/40' : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
                Contrato: {formatearDuracion(diasRestantes)}
              </span>
            )}
            {datos.en_transferible && (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-amber-950 text-amber-300 border-amber-500/40">
                En lista de transferibles
              </span>
            )}
            {datos.id_equipo_dueno != null && (
              <span className="inline-block mt-3 ml-2 text-xs font-bold px-3 py-1 rounded-full border bg-sky-950 text-sky-300 border-sky-500/40">
                A préstamo en {datos.club_prestamista || '?'}{datos.fin_cesion ? ` hasta ${new Date(`${datos.fin_cesion}T00:00:00`).toLocaleDateString('es-AR')}` : ''}
              </span>
            )}
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className="bg-sky-500 text-slate-950 font-black text-2xl px-4 py-2 rounded-2xl">
              {formatOverall(datos)}
            </span>
            <span className="text-[10px] text-slate-500 font-bold">POT {formatPotencial(datos)}</span>
          </div>
        </div>

        <div className="grid grid-cols-[140px_1fr] gap-4 sm:gap-6 items-start">
          <MiniPitchPosicion posicion={datos.posicion} posicionEspecifica={datos.posicion_especifica} />

          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-x-4 gap-y-1 text-xs bg-[#0b1326] border border-slate-800 rounded-2xl p-4">
              <Stat label="Edad" value={datos.edad} />
              <Stat label="Energía" value={datos.energia != null ? `${datos.energia}%` : null} />
              <Stat label="Moral" value={datos.moral != null ? `${datos.moral}%` : null} />
              <Stat label="Valor" value={`$${(datos.val ?? datos.valor_mercado ?? 0).toLocaleString('es-AR')}`} />
              <Stat label="Salario/sem" value={`$${(datos.sal ?? datos.salario ?? 0).toLocaleString('es-AR')}`} />
            </div>

            {desgloseDisponible ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                  <ListaAtributos titulo="Técnico" items={ATRIBUTOS_TECNICO} jugador={datos} />
                  <ListaAtributos titulo="Mental" items={ATRIBUTOS_MENTAL} jugador={datos} />
                  <ListaAtributos titulo="Físico" items={ATRIBUTOS_FISICO} jugador={datos} />
                  {datos.posicion === 'POR' && (
                    <ListaAtributos titulo="Portería" items={[['porteria', 'Portería']]} jugador={datos} />
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-[#0b1326] border border-slate-800 rounded-2xl p-4">
                    <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-2 text-center">Perfil</h4>
                    <RadarChart ejes={ejesRadar} />
                  </div>
                  <RolesEfectivos jugador={datos} />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-1 text-sm content-start">
                <Stat
                  label="Posición"
                  value={datos.posicion_especifica ? `${datos.posicion_especifica} (${datos.pos || datos.posicion})` : (datos.pos || datos.posicion)}
                />
                <Stat label="Ataque" value={datos.atq ?? datos.ataque} />
                <Stat label="Defensa" value={datos.def ?? datos.defensa} />
                <Stat label="Pase" value={datos.pase} />
                <Stat label="Físico" value={datos.fis ?? datos.fisico} />
                {datos.scouting_progreso != null && (
                  <p className="col-span-full text-xs text-slate-500 pt-2">
                    Desglose de atributos disponible al llegar a 100% de scouting (hoy {datos.scouting_progreso}%).
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        {historial.length > 0 && (
          <div className="border-t border-slate-800 pt-5">
            <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider mb-3">Evolución de carrera</h4>
            <div className="overflow-x-auto scroll-slide">
              <table className="w-full text-xs min-w-[420px]">
                <thead>
                  <tr className="text-slate-500 text-left">
                    <th className="pb-2 pr-4">Temporada</th>
                    <th className="pb-2 pr-4">Club</th>
                    <th className="pb-2 pr-4">Edad</th>
                    <th className="pb-2 pr-4">Ovr</th>
                    <th className="pb-2 pr-4">Pot</th>
                    <th className="pb-2">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.map((h) => (
                    <tr key={h.temporada} className="border-t border-slate-800/60">
                      <td className="py-1.5 pr-4 text-slate-300 font-bold">{h.temporada}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{h.nombre_equipo}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{h.edad}</td>
                      <td className="py-1.5 pr-4 text-white font-bold">{formatOverall(h)}</td>
                      <td className="py-1.5 pr-4 text-slate-400">{formatPotencial(h)}</td>
                      <td className="py-1.5 text-sky-400 font-bold">${h.valor_mercado.toLocaleString('es-AR')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-4 flex-wrap">
          {onHablar && (
            <button
              onClick={onHablar}
              className="flex-1 bg-slate-800 hover:bg-slate-700 border border-sky-500/40 text-sky-300 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Hablar
            </button>
          )}
          {onNegociar && (
            <button
              onClick={onNegociar}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Negociar fichaje
            </button>
          )}
          {onPrecontrato && (
            <button
              onClick={onPrecontrato}
              className="flex-1 bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Precontrato (firma libre)
            </button>
          )}
          {onFicharLibre && (
            <button
              onClick={onFicharLibre}
              className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Fichar libre
            </button>
          )}
          {onRenovar && (
            <button
              onClick={onRenovar}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Renovar contrato
            </button>
          )}
          {onToggleTransferible && (
            <button
              onClick={onToggleTransferible}
              className={`flex-1 font-bold px-4 py-3 rounded-xl text-sm ${
                datos.en_transferible
                  ? 'bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300'
                  : 'bg-amber-400 hover:bg-amber-300 text-slate-950'
              }`}
            >
              {datos.en_transferible ? 'Sacar de la lista de transferibles' : 'Poner en lista de transferibles'}
            </button>
          )}
          {onOfrecer && (
            <button
              onClick={onOfrecer}
              className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Ofrecer a otros equipos
            </button>
          )}
          {onCeder && (
            <button
              onClick={onCeder}
              className="flex-1 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Ceder a préstamo
            </button>
          )}
          {onEnviarOjeador && (
            <button
              onClick={onEnviarOjeador}
              className="flex-1 bg-slate-800 hover:bg-slate-700 border border-sky-500/40 text-sky-300 font-bold px-4 py-3 rounded-xl text-sm"
            >
              Enviar ojeador
            </button>
          )}
          <button onClick={onClose} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 rounded-xl text-sm">
            Cerrar
          </button>
        </div>
      </div>
    </Modal>
  );
}
