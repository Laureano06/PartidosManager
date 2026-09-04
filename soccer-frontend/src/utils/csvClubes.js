// Parsea líneas "LIGA,CODIGO,NOMBRE[,ESCUDO_URL[,NOMBRE_COMPETENCIA]]" en el
// formato que espera el backend: { ARG1: [["BOC","Xeneize FC", escudo?, competencia?], ...] }.
export function parsearCsvClubes(texto) {
  const porLiga = {};
  texto.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).forEach((linea) => {
    const partes = linea.split(',').map((s) => s.trim());
    if (partes.length < 3) return;
    const [liga, codigo, nombre, escudoUrl, nombreCompetencia] = partes;
    if (!liga || !codigo || !nombre) return;
    porLiga[liga] = porLiga[liga] || [];
    const fila = [codigo, nombre];
    if (escudoUrl || nombreCompetencia) fila.push(escudoUrl || '');
    if (nombreCompetencia) fila.push(nombreCompetencia);
    porLiga[liga].push(fila);
  });
  return porLiga;
}

// Parsea líneas "LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,
// NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO" agrupadas por liga y código
// de club: { ARG1: { BOC: [{nombre, posicion, ...}, ...] }, ... }. Anidar
// por liga es necesario porque el código de club no es único entre ligas
// (ej. "BOC" existe en ARG1 y en ALE1).
export function parsearCsvJugadores(texto) {
  const porLiga = {};
  texto.split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).forEach((linea) => {
    const partes = linea.split(',').map((s) => s.trim());
    if (partes.length < 11) return;
    const [liga, codigoClub, nombre, posicion, posicionEspecifica, nacionalidad, edad, ataque, defensa, pase, fisico] = partes;
    if (!liga || !codigoClub || !nombre || !posicion) return;
    porLiga[liga] = porLiga[liga] || {};
    porLiga[liga][codigoClub] = porLiga[liga][codigoClub] || [];
    porLiga[liga][codigoClub].push({
      nombre, posicion, posicion_especifica: posicionEspecifica || null,
      nacionalidad: nacionalidad || null, edad: Number(edad) || 24,
      ataque: Number(ataque) || 50, defensa: Number(defensa) || 50,
      pase: Number(pase) || 50, fisico: Number(fisico) || 50,
    });
  });
  return porLiga;
}

export function leerArchivoComoTexto(archivo) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result || ''));
    lector.onerror = reject;
    lector.readAsText(archivo);
  });
}
