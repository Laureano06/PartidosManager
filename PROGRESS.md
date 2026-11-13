# Objetivo actual
Profundizar los sistemas automáticos de carrera y preservar el PMPack como base única de datos reales.

## Completado
El PMPack internacional incluye clubes, jugadores, contratos, valores, cesiones, escudos, caras, multiclub, selecciones y torneos. La carrera crea planteles y calendario por lote, y mantiene los sistemas de selecciones, relaciones, mercado, multiclub, academia, ciudad, dirección deportiva, prensa/vestuario y documental activos por defecto. El calendario de selecciones distingue ventanas próximas, activas y terminadas. Dirección Deportiva ofrece contratos próximos, cobertura por línea y juveniles a seguir. Prensa/Vestuario se gestiona desde Cuerpo Técnico. Plantel y Desarrollo distinguen préstamos enviados y recibidos.

## Tests
Compilación Python y `npm run build`: OK. API de Desarrollo validada en la carrera 73; backend reiniciado.

## Pendiente siguiente paso
Las selecciones inactivas quedan como base real del PMPack y ya no materializan elegibles al abrirse. El PMPack actual no contiene registros de cesión, por lo que la carrera 73 no tiene préstamos para mostrar aunque las pantallas ya los admiten. Incorporar cesiones reales verificadas al PMPack y seguir profundizando los demás sistemas sin añadir cargas masivas durante la creación ni la navegación.
