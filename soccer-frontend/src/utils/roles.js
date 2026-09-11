// Cupos de titulares por posición (4-4-2 base: 1 POR, 4 DEF, 4 MED, 2 DEL).
// Se usan para decidir a quién bajar a SUPLENTE cuando se promueve a alguien
// y ya no queda lugar en su posición.
export const CUPOS_TITULAR = { POR: 1, DEF: 4, MED: 4, DEL: 2 };

// Dado el plantel actual y un jugador a promover a TITULAR, devuelve el
// jugador que hay que bajar a SUPLENTE (o null si hay lugar sin bajar a nadie).
export function jugadorASacar(plantilla, jugador) {
  if (jugador.rol === 'TITULAR') return null;
  const titularesPos = plantilla.filter((j) => j.rol === 'TITULAR' && j.posicion === jugador.posicion);
  const cupo = CUPOS_TITULAR[jugador.posicion] ?? 0;
  if (titularesPos.length < cupo) return null;
  return titularesPos.reduce((peor, j) => (j.overall < peor.overall ? j : peor), titularesPos[0]);
}

export async function setRolJugador(API_URL, idJugador, rol) {
  return fetch(`${API_URL}/jugadores/${idJugador}/rol`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rol }),
  });
}

// Promueve `jugador` a TITULAR, degradando (si hace falta) al peor titular
// de su misma posición. Actualiza el estado local (optimista) y persiste
// ambos cambios en el backend.
export async function promoverATitular(API_URL, plantilla, setPlantilla, jugador) {
  const saliente = jugadorASacar(plantilla, jugador);
  setPlantilla((prev) => prev.map((j) => {
    if (j.id_jugador === jugador.id_jugador) return { ...j, rol: 'TITULAR' };
    if (saliente && j.id_jugador === saliente.id_jugador) return { ...j, rol: 'SUPLENTE' };
    return j;
  }));
  try {
    await setRolJugador(API_URL, jugador.id_jugador, 'TITULAR');
    if (saliente) await setRolJugador(API_URL, saliente.id_jugador, 'SUPLENTE');
  } catch (error) {
    console.error('Error promoviendo a titular:', error);
  }
}

export async function cambiarRol(API_URL, setPlantilla, jugador, nuevoRol) {
  setPlantilla((prev) => prev.map((j) => (j.id_jugador === jugador.id_jugador ? { ...j, rol: nuevoRol } : j)));
  try {
    await setRolJugador(API_URL, jugador.id_jugador, nuevoRol);
  } catch (error) {
    console.error('Error cambiando rol:', error);
  }
}

// Instrucción individual del jugador dentro de la táctica (DEFENSIVO,
// EQUILIBRADO, OFENSIVO) — independiente del rol titular/suplente/reserva.
export async function setDutyJugador(API_URL, idJugador, duty) {
  return fetch(`${API_URL}/jugadores/${idJugador}/duty`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ duty }),
  });
}
