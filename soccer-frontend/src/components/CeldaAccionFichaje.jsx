import React from 'react';

// Si ya hay un pase ACORDADO (ACEPTADA, pendiente de hacerse efectivo) para
// este jugador con tu club, o ya firmó un PRECONTRATO con vos (se incorpora
// libre cuando termine su contrato actual — eso vive en id_equipo_precontrato,
// no en OfertaFichaje), no tiene sentido seguir mostrando el botón de
// negociar — se muestra cuándo se va a incorporar en su lugar.
//
// Compartido entre TransferenciasPage y MercadoPage: antes vivía duplicado
// en cada archivo, con riesgo de que una corrección de reglas en uno no se
// propagara al otro.
export default function CeldaAccionFichaje({ j, idsComprando, onAccion, label, idEquipoUsuario }) {
  const acordado = idsComprando.get(j.id_jugador);
  if (acordado) {
    return <span className="text-[10px] font-bold text-emerald-400">Se unirá a tu club {acordado.texto_incorporacion}</span>;
  }
  if (j.id_equipo_precontrato && j.id_equipo_precontrato === idEquipoUsuario) {
    const fecha = j.fecha_fin_contrato ? new Date(`${j.fecha_fin_contrato}T00:00:00`).toLocaleDateString('es-AR') : '?';
    return <span className="text-[10px] font-bold text-emerald-400">Se unirá a tu club libre el {fecha}</span>;
  }
  if (j.id_equipo_precontrato && j.id_equipo_precontrato !== idEquipoUsuario) {
    return <span className="text-[10px] text-slate-400">Ya firmó precontrato con otro club</span>;
  }
  if (!j.asequible && j.asequible !== undefined) {
    return <span className="text-[10px] text-rose-400 font-bold">Sin presupuesto</span>;
  }
  return (
    <button onClick={() => onAccion(j)} className="bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold px-3 py-1 rounded text-xs">
      {label}
    </button>
  );
}
