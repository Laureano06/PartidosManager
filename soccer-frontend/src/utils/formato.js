// Formatea días restantes de contrato como "1 año 2 meses" en vez de "425d",
// para que sea legible cuando falta más de un año.
export function formatearDuracion(dias) {
  if (dias == null) return '—';
  if (dias <= 0) return 'Vencido';
  if (dias < 60) return `${dias}d`;

  const meses = Math.round(dias / 30);
  if (meses < 12) return `${meses} mes${meses === 1 ? '' : 'es'}`;

  const anios = Math.floor(meses / 12);
  const mesesResto = meses % 12;
  const partes = [`${anios} año${anios === 1 ? '' : 's'}`];
  if (mesesResto > 0) partes.push(`${mesesResto} mes${mesesResto === 1 ? '' : 'es'}`);
  return partes.join(' ');
}
