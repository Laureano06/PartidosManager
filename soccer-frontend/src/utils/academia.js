// Espejo en JS de las reglas de engine/academia_engine.py — solo para
// pre-filtrar opciones en la UI; el backend valida igual, esto es nada más
// para no mostrarle al usuario un destino que va a terminar rechazado.

export const CATEGORIAS_ACADEMIA = ['SUB13', 'SUB15', 'SUB18', 'SUB21'];
export const EDAD_MINIMA_CONTRATO = 15;

const ORDEN = { SUB13: 0, SUB15: 1, SUB18: 2, SUB21: 3 };

export function categoriaMinimaPorEdad(edad) {
  if (edad <= 13) return 'SUB13';
  if (edad <= 15) return 'SUB15';
  if (edad <= 18) return 'SUB18';
  return 'SUB21';
}

export function puedeMoverACategoria(edad, categoriaDestino) {
  if (categoriaDestino === 'PRIMERA') return edad >= EDAD_MINIMA_CONTRATO;
  return ORDEN[categoriaDestino] >= ORDEN[categoriaMinimaPorEdad(edad)];
}

export const CATEGORIA_LABEL = {
  PRIMERA: 'Primera',
  SUB13: 'Sub-13',
  SUB15: 'Sub-15',
  SUB18: 'Sub-18',
  SUB21: 'Sub-21',
};

export const CATEGORIA_CLASS = {
  PRIMERA: 'bg-sky-950 text-sky-400 border border-sky-500/40',
  SUB13: 'bg-slate-800 text-slate-300 border border-slate-600/40',
  SUB15: 'bg-slate-800 text-slate-300 border border-slate-600/40',
  SUB18: 'bg-amber-950 text-amber-400 border border-amber-500/40',
  SUB21: 'bg-emerald-950 text-emerald-400 border border-emerald-500/40',
};
