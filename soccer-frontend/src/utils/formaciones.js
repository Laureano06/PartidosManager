// Formaciones compartidas entre Tácticas y la pantalla de partido (los
// cambios en el entretiempo usan la misma cancha, para que se vea igual).
// `posEspecifica` es la posición concreta dentro de la amplia (`pos`) —
// solo cambia qué label se muestra y qué tan "fuera de posición" se marca
// dentro de su propia categoría; el resto del juego (mercado, cupos, motor
// de partido) sigue funcionando con `pos` (POR/DEF/MED/DEL) sin cambios.
export const FORMACIONES_SLOTS = {
  '4-4-2': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 15, y: 28 }, { pos: 'DEF', posEspecifica: 'DFC', x: 38, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 62, y: 25 }, { pos: 'DEF', posEspecifica: 'DFD', x: 85, y: 28 },
    { pos: 'MED', posEspecifica: 'MI', x: 15, y: 55 }, { pos: 'MED', posEspecifica: 'MC', x: 38, y: 50 }, { pos: 'MED', posEspecifica: 'MC', x: 62, y: 50 }, { pos: 'MED', posEspecifica: 'MD', x: 85, y: 55 },
    { pos: 'DEL', posEspecifica: 'DC', x: 38, y: 80 }, { pos: 'DEL', posEspecifica: 'DC', x: 62, y: 80 },
  ],
  '4-3-3': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 15, y: 28 }, { pos: 'DEF', posEspecifica: 'DFC', x: 38, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 62, y: 25 }, { pos: 'DEF', posEspecifica: 'DFD', x: 85, y: 28 },
    { pos: 'MED', posEspecifica: 'MCD', x: 30, y: 52 }, { pos: 'MED', posEspecifica: 'MC', x: 50, y: 48 }, { pos: 'MED', posEspecifica: 'MCO', x: 70, y: 52 },
    { pos: 'DEL', posEspecifica: 'EI', x: 20, y: 80 }, { pos: 'DEL', posEspecifica: 'DC', x: 50, y: 78 }, { pos: 'DEL', posEspecifica: 'ED', x: 80, y: 80 },
  ],
  '4-2-3-1': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 15, y: 28 }, { pos: 'DEF', posEspecifica: 'DFC', x: 38, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 62, y: 25 }, { pos: 'DEF', posEspecifica: 'DFD', x: 85, y: 28 },
    { pos: 'MED', posEspecifica: 'MCD', x: 35, y: 45 }, { pos: 'MED', posEspecifica: 'MCD', x: 65, y: 45 },
    { pos: 'MED', posEspecifica: 'MI', x: 18, y: 65 }, { pos: 'MED', posEspecifica: 'MCO', x: 50, y: 62 }, { pos: 'MED', posEspecifica: 'MD', x: 82, y: 65 },
    { pos: 'DEL', posEspecifica: 'DC', x: 50, y: 85 },
  ],
  '4-5-1': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 15, y: 28 }, { pos: 'DEF', posEspecifica: 'DFC', x: 38, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 62, y: 25 }, { pos: 'DEF', posEspecifica: 'DFD', x: 85, y: 28 },
    { pos: 'MED', posEspecifica: 'MI', x: 8, y: 52 }, { pos: 'MED', posEspecifica: 'MCD', x: 30, y: 48 }, { pos: 'MED', posEspecifica: 'MC', x: 50, y: 45 }, { pos: 'MED', posEspecifica: 'MCO', x: 70, y: 48 }, { pos: 'MED', posEspecifica: 'MD', x: 92, y: 52 },
    { pos: 'DEL', posEspecifica: 'DC', x: 50, y: 82 },
  ],
  '3-5-2': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFC', x: 25, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 50, y: 20 }, { pos: 'DEF', posEspecifica: 'DFC', x: 75, y: 25 },
    { pos: 'MED', posEspecifica: 'MI', x: 8, y: 50 }, { pos: 'MED', posEspecifica: 'MCD', x: 30, y: 45 }, { pos: 'MED', posEspecifica: 'MC', x: 50, y: 42 }, { pos: 'MED', posEspecifica: 'MCO', x: 70, y: 45 }, { pos: 'MED', posEspecifica: 'MD', x: 92, y: 50 },
    { pos: 'DEL', posEspecifica: 'DC', x: 38, y: 80 }, { pos: 'DEL', posEspecifica: 'MP', x: 62, y: 80 },
  ],
  '3-4-3': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFC', x: 25, y: 25 }, { pos: 'DEF', posEspecifica: 'DFC', x: 50, y: 20 }, { pos: 'DEF', posEspecifica: 'DFC', x: 75, y: 25 },
    { pos: 'MED', posEspecifica: 'MI', x: 15, y: 50 }, { pos: 'MED', posEspecifica: 'MC', x: 38, y: 48 }, { pos: 'MED', posEspecifica: 'MC', x: 62, y: 48 }, { pos: 'MED', posEspecifica: 'MD', x: 85, y: 50 },
    { pos: 'DEL', posEspecifica: 'EI', x: 20, y: 80 }, { pos: 'DEL', posEspecifica: 'DC', x: 50, y: 78 }, { pos: 'DEL', posEspecifica: 'ED', x: 80, y: 80 },
  ],
  '5-4-1': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 8, y: 30 }, { pos: 'DEF', posEspecifica: 'DFC', x: 28, y: 24 }, { pos: 'DEF', posEspecifica: 'DFC', x: 50, y: 22 }, { pos: 'DEF', posEspecifica: 'DFC', x: 72, y: 24 }, { pos: 'DEF', posEspecifica: 'DFD', x: 92, y: 30 },
    { pos: 'MED', posEspecifica: 'MI', x: 15, y: 55 }, { pos: 'MED', posEspecifica: 'MC', x: 38, y: 50 }, { pos: 'MED', posEspecifica: 'MC', x: 62, y: 50 }, { pos: 'MED', posEspecifica: 'MD', x: 85, y: 55 },
    { pos: 'DEL', posEspecifica: 'DC', x: 50, y: 80 },
  ],
  '5-3-2': [
    { pos: 'POR', posEspecifica: 'POR', x: 50, y: 8 },
    { pos: 'DEF', posEspecifica: 'DFI', x: 10, y: 30 }, { pos: 'DEF', posEspecifica: 'DFC', x: 30, y: 24 }, { pos: 'DEF', posEspecifica: 'DFC', x: 50, y: 22 }, { pos: 'DEF', posEspecifica: 'DFC', x: 70, y: 24 }, { pos: 'DEF', posEspecifica: 'DFD', x: 90, y: 30 },
    { pos: 'MED', posEspecifica: 'MCD', x: 25, y: 55 }, { pos: 'MED', posEspecifica: 'MC', x: 50, y: 50 }, { pos: 'MED', posEspecifica: 'MCO', x: 75, y: 55 },
    { pos: 'DEL', posEspecifica: 'DC', x: 38, y: 80 }, { pos: 'DEL', posEspecifica: 'DC', x: 62, y: 80 },
  ],
};

export const FORMACIONES_LABEL = {
  '4-4-2': '4-4-2 (Clásica)',
  '4-3-3': '4-3-3 (Ofensiva)',
  '4-2-3-1': '4-2-3-1 (Equilibrada)',
  '4-5-1': '4-5-1 (Defensiva)',
  '3-5-2': '3-5-2 (Carrileros)',
  '3-4-3': '3-4-3 (Ultra ofensiva)',
  '5-4-1': '5-4-1 (Muy defensiva)',
  '5-3-2': '5-3-2 (Línea de 5)',
};

// Versión simple: bucket por posición natural + overall, sin asignación
// manual fuera de posición (eso solo lo necesita la pantalla de Tácticas).
export function calcularAlineacionSimple(plantilla, slots) {
  const disponibles = { POR: [], DEF: [], MED: [], DEL: [] };
  plantilla.forEach((j) => { if (disponibles[j.posicion]) disponibles[j.posicion].push(j); });
  Object.keys(disponibles).forEach((pos) => {
    disponibles[pos].sort((a, b) => (b.rol === 'TITULAR') - (a.rol === 'TITULAR') || b.overall - a.overall);
  });
  const usados = new Set();
  const resultado = slots.map((slot) => {
    const candidato = disponibles[slot.pos]?.find((j) => !usados.has(j.id_jugador));
    if (candidato) usados.add(candidato.id_jugador);
    return candidato || null;
  });
  // Un cambio fuera de posición (entra un mediocampista por un delantero,
  // por ejemplo) puede dejar un bloque de posición con más titulares que
  // lugares y otro con menos — antes, el sobrante quedaba afuera del
  // resultado (el jugador "desaparecía" de la cancha aunque seguía siendo
  // titular). Acá se acomoda en cualquier hueco libre que haya quedado.
  const sobrantes = plantilla.filter((j) => !usados.has(j.id_jugador));
  let cursor = 0;
  for (const j of sobrantes) {
    while (cursor < resultado.length && resultado[cursor] !== null) cursor++;
    if (cursor >= resultado.length) break;
    resultado[cursor] = j;
    usados.add(j.id_jugador);
  }
  return resultado;
}
