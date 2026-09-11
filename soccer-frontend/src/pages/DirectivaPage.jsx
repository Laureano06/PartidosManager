import React, { useEffect, useState } from 'react';
import { formatearDuracion } from '../utils/formato';

function textoRiesgo(confianza) {
  if (confianza <= 15) return { texto: 'CRÍTICO (Despido inminente)', color: 'text-rose-400' };
  if (confianza <= 35) return { texto: 'ALTO (Riesgo de despido)', color: 'text-red-400' };
  if (confianza <= 60) return { texto: 'MEDIO', color: 'text-amber-400' };
  return { texto: 'BAJO', color: 'text-emerald-400' };
}

function textoHinchada(humor) {
  if (humor >= 75) return { texto: 'ILUSIONADA', color: 'text-emerald-400' };
  if (humor >= 50) return { texto: 'EXPECTANTE', color: 'text-sky-400' };
  if (humor >= 30) return { texto: 'INQUIETA', color: 'text-amber-400' };
  return { texto: 'MOLESTA', color: 'text-rose-400' };
}

const MODULOS_AUTOMATICOS = [
  ['selecciones', 'Selecciones y fechas internacionales'],
  ['relaciones', 'Relaciones de jugadores y agentes'],
  ['mercado', 'Mercado y decisiones de clubes rivales'],
  ['multiclub', 'Redes multiclub y cesiones internas'],
  ['academia', 'Academia y progresión juvenil'],
  ['club_ciudad', 'Club, ciudad e hinchada'],
  ['direccion_deportiva', 'Dirección deportiva'],
  ['prensa_vestuario', 'Prensa y vestuario'],
  ['documental', 'Resumen documental de temporada'],
];

export default function DirectivaPage({ API_URL, idPartida, onEstadoCambiado }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [confirmandoRenuncia, setConfirmandoRenuncia] = useState(false);
  const [renunciando, setRenunciando] = useState(false);
  const [errorRenuncia, setErrorRenuncia] = useState(null);
  const [guardandoAutomatico, setGuardandoAutomatico] = useState(null);
  const [informeDeportivo, setInformeDeportivo] = useState(null);

  useEffect(() => {
    if (!idPartida) return;
    setCargando(true);
    fetch(`${API_URL}/partidas/${idPartida}/directiva`)
      .then((r) => r.json())
      .then(setDatos)
      .catch((e) => console.error('Error cargando directiva:', e))
      .finally(() => setCargando(false));
    fetch(`${API_URL}/partidas/${idPartida}/direccion-deportiva`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setInformeDeportivo)
      .catch(() => setInformeDeportivo(null));
  }, [API_URL, idPartida]);

  if (cargando || !datos) {
    return <p className="text-xs text-slate-400">Cargando...</p>;
  }

  const riesgo = textoRiesgo(datos.confianza_directiva);
  const hinchada = textoHinchada(datos.humor_hinchada ?? 60);

  const renunciar = async () => {
    setRenunciando(true);
    setErrorRenuncia(null);
    try {
      const r = await fetch(`${API_URL}/partidas/${idPartida}/renunciar`, { method: 'POST' });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        setErrorRenuncia(err.detail || 'No se pudo renunciar.');
        setRenunciando(false);
        return;
      }
      onEstadoCambiado?.();
    } catch (e) {
      console.error('Error renunciando:', e);
      setErrorRenuncia('No se pudo conectar con el servidor.');
      setRenunciando(false);
    }
  };

  const cambiarAutomatico = async (clave) => {
    const automatizaciones = { ...datos.automatizaciones, [clave]: !datos.automatizaciones?.[clave] };
    setGuardandoAutomatico(clave);
    try {
      const r = await fetch(`${API_URL}/partidas/${idPartida}/automatizaciones`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ automatizaciones }),
      });
      if (!r.ok) throw new Error('No se pudo guardar');
      const actualizado = await r.json();
      setDatos((anterior) => ({ ...anterior, automatizaciones: actualizado.automatizaciones }));
    } catch (e) {
      console.error('Error guardando automatización:', e);
    } finally {
      setGuardandoAutomatico(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
        <h2 className="text-base font-bold text-white">Evaluación de la Junta Directiva</h2>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between font-bold">
            <span className="text-slate-400">Nivel de riesgo:</span>
            <span className={riesgo.color}>{riesgo.texto}</span>
          </div>
          <div className="flex justify-between font-bold">
            <span className="text-slate-400">Confianza de la Directiva:</span>
            <span className="text-sky-400">{datos.confianza_directiva}%</span>
          </div>
          <div className="flex justify-between font-bold">
            <span className="text-slate-400">Ánimo de la hinchada:</span>
            <span className={hinchada.color}>{hinchada.texto} · {datos.humor_hinchada ?? 60}%</span>
          </div>
          <div className="w-full bg-[#0b1326] h-3 rounded-full overflow-hidden border border-slate-800">
            <div className="bg-sky-400 h-full" style={{ width: `${datos.confianza_directiva}%` }} />
          </div>
        </div>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
        <h2 className="text-sm font-bold text-white mb-1">Objetivo de la temporada</h2>
        <p className="text-xs text-slate-300">{datos.objetivo_temporada}</p>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-2">
        <h2 className="text-sm font-bold text-white mb-1">Tu contrato</h2>
        <p className="text-xs text-slate-400">
          {datos.contrato_dt_anios} año{datos.contrato_dt_anios === 1 ? '' : 's'} — vence en{' '}
          <span className="text-slate-200 font-bold">{formatearDuracion(datos.dias_restantes_contrato)}</span>
        </p>
        <p className="text-[11px] text-slate-400">Trayectoria como DT (balance): {datos.balance_dt}/100</p>
      </div>

      {informeDeportivo && (
        <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-4">
          <div><p className="text-[10px] font-black tracking-wider text-sky-400">DIRECCIÓN DEPORTIVA</p><h2 className="text-sm font-bold text-white">Prioridades del plantel</h2></div>
          <div className="grid lg:grid-cols-3 gap-3 text-xs">
            <InformeColumna titulo="Contratos próximos">{informeDeportivo.contratos.length ? informeDeportivo.contratos.map((j) => <p key={j.id_jugador} className="flex justify-between gap-2 py-1 text-slate-400"><span>{j.nombre} · {j.posicion}</span><strong className="text-amber-300">{j.dias}d</strong></p>) : <p className="text-slate-500">No vencen contratos en 180 días.</p>}</InformeColumna>
            <InformeColumna titulo="Cobertura por línea">{informeDeportivo.cobertura.map((linea) => <p key={linea.posicion} className="flex justify-between gap-2 py-1 text-slate-400"><span>{linea.posicion} · {linea.cantidad} · OVR {linea.overall_medio}</span><strong className={linea.prioridad === 'ALTA' ? 'text-rose-300' : linea.prioridad === 'MEDIA' ? 'text-amber-300' : 'text-emerald-300'}>{linea.prioridad}</strong></p>)}</InformeColumna>
            <InformeColumna titulo="Juveniles a seguir">{informeDeportivo.promesas.length ? informeDeportivo.promesas.map((j) => <p key={j.id_jugador} className="flex justify-between gap-2 py-1 text-slate-400"><span>{j.nombre} · {j.posicion}</span><strong className="text-sky-300">{j.overall} → {j.potencial}</strong></p>) : <p className="text-slate-500">No hay Sub-21 disponibles.</p>}</InformeColumna>
          </div>
        </div>
      )}

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
        <div>
          <h2 className="text-sm font-bold text-white">Modo automático de carrera</h2>
          <p className="text-[11px] text-slate-400 mt-1">Estos sistemas avanzan al continuar el calendario. Podés pausarlos sin perder información.</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-2">
          {MODULOS_AUTOMATICOS.map(([clave, etiqueta]) => {
            const activo = datos.automatizaciones?.[clave] !== false;
            return (
              <button
                key={clave}
                type="button"
                onClick={() => cambiarAutomatico(clave)}
                disabled={guardandoAutomatico === clave}
                className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left text-xs transition-colors ${activo ? 'border-emerald-500/35 bg-emerald-950/25 text-emerald-100' : 'border-slate-700 bg-[#0b1326] text-slate-400'}`}
              >
                <span>{etiqueta}</span>
                <span className={`shrink-0 font-bold ${activo ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {guardandoAutomatico === clave ? '...' : activo ? 'ACTIVO' : 'PAUSADO'}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="bg-[#121e36] border border-slate-800 rounded-2xl p-6 space-y-3">
        <h2 className="text-sm font-bold text-white">Renunciar al cargo</h2>
        <p className="text-[11px] text-slate-400">
          Dejás el club por tu cuenta. Otros clubes te van a ofrecer un puesto acorde a tu trayectoria como DT, no a tu club actual.
        </p>
        {errorRenuncia && <p className="text-xs text-rose-400">{errorRenuncia}</p>}
        {!confirmandoRenuncia ? (
          <button
            onClick={() => setConfirmandoRenuncia(true)}
            className="bg-rose-950 hover:bg-rose-900 border border-rose-500/40 text-rose-300 font-bold px-4 py-2 rounded-lg text-xs"
          >
            Renunciar
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={renunciar}
              disabled={renunciando}
              className="bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold px-4 py-2 rounded-lg text-xs"
            >
              {renunciando ? 'Renunciando...' : 'Confirmar renuncia'}
            </button>
            <button
              onClick={() => setConfirmandoRenuncia(false)}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg text-xs"
            >
              Cancelar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function InformeColumna({ titulo, children }) {
  return <div className="rounded-xl border border-slate-800 bg-[#0b1326] p-3"><p className="font-bold text-slate-200 mb-2">{titulo}</p>{children}</div>;
}
