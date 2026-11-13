import test from 'node:test';
import assert from 'node:assert/strict';
import { parsearCsvClubes, parsearCsvJugadores, combinarEscudosSubidos } from './csvClubes.js';

test('CSV normalizes keys and handles headers, BOM, quotes and commas', () => {
  assert.deepEqual(parsearCsvClubes('\uFEFFLIGA,CODIGO,NOMBRE\r\narg1,boc,"Club, Prueba"'), { ARG1: [['BOC', 'Club, Prueba']] });
  const players = parsearCsvJugadores('LIGA,CODIGO_CLUB,NOMBRE,POSICION,POSICION_ESPECIFICA,NACIONALIDAD,EDAD,ATAQUE,DEFENSA,PASE,FISICO\narg1,boc,"Nombre ""Uno"", Prueba",del,DC,,24,80,0,65,78');
  assert.equal(players.ARG1.BOC.length, 1);
  assert.equal(players.ARG1.BOC[0].nombre, 'Nombre "Uno", Prueba');
  assert.equal(players.ARG1.BOC[0].posicion, 'DEL');
  assert.equal(players.ARG1.BOC[0].defensa, 0);
});

test('uploaded badge replaces placeholder and league-specific badge takes priority', () => {
  const clubs = { ARG1: [['ABC', 'Uno', 'https://example.com/placeholder', 'Liga']], BRA1: [['ABC', 'Dos']] };
  const result = combinarEscudosSubidos(clubs, { ABC: '/static/escudos/default.svg', ARG1_ABC: '/static/escudos/arg.svg' });
  assert.equal(result.ARG1[0][2], '/static/escudos/arg.svg');
  assert.equal(result.BRA1[0][2], '/static/escudos/default.svg');
  assert.equal(result.ARG1[0][3], 'Liga');
  assert.equal(clubs.ARG1[0][2], 'https://example.com/placeholder');
});
