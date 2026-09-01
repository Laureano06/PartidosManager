export function formatOverall(j) {
  if (j.overall != null) return String(j.overall);
  if (j.overall_rango) return `${j.overall_rango[0]}-${j.overall_rango[1]}`;
  return '?';
}

export function formatPotencial(j) {
  if (j.potencial != null) return String(j.potencial);
  if (j.potencial_rango) return `${j.potencial_rango[0]}-${j.potencial_rango[1]}`;
  return '?';
}
