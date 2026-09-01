# Partidos Soccer Manager

Backend real (FastAPI + PostgreSQL/SQLite) + frontend (React/Vite) para el
manager de fútbol. Datos 100% ficticios (sin nombres ni clubes reales, ver
sección "Sobre los datos" más abajo).

## Qué cambió en esta vuelta

- **Seguridad:** se sacó la contraseña de Neon que estaba hardcodeada en
  `main.py` y en `.env`. Ese archivo ahora es una plantilla — completalo con
  tu connection string nueva (la que reseteaste) y **nunca lo subas a git**.
- **Datos reales fuera:** `App.jsx` tenía la Selección Argentina real
  (Messi incluido) como plantel por defecto. Se reemplazó por un generador
  ficticio (mismo patrón que el resto del proyecto).
- **Backend conectado de verdad:** `main.py` ahora usa SQLAlchemy + los
  motores (`engine/`) en vez de devolver resultados fijos. Endpoints reales:
  equipos, plantillas, tabla, calendario, simulación de partidos/jornadas,
  tácticas, entrenamiento y mercado de fichajes.
- **IA rival jugable:**
  - **Mercado:** cada jornada, los clubes que no manejás intentan fichar en
    su posición más floja. Si le compran a otro club de la IA, se resuelve
    solo. Si le ofertan a un jugador tuyo, queda como oferta pendiente que
    aceptás o rechazás vos (`/fichajes/ofertas-recibidas`, `/fichajes/responder`).
  - **Táctica en el partido:** los equipos de la IA ajustan su mentalidad
    solos según el marcador (minuto 65+ perdiendo → ofensiva, minuto 80+
    ganando → defensiva).

## Cómo correrlo

### 1. Backend

```bash
cd proyectoSoccerManager
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

Completá `.env` con tu URL de Neon (la contraseña nueva). Si querés probar
rápido sin depender de internet, usá en cambio:
```
DATABASE_URL=sqlite+aiosqlite:///./soccer.db
```

Poblar la liga (8 clubes ficticios + fixture):
```bash
python seed.py          # primera vez
python seed.py --reset  # para regenerar todo de cero
```

Levantar el servidor:
```bash
uvicorn main:app --reload
```
Documentación interactiva: http://127.0.0.1:8000/docs

### 2. Frontend

```bash
cd soccer-frontend
npm install
npm run dev
```

## Sobre los datos

Todo lo que genera `engine/data_gen.py` es inventado: nombres, apellidos y
nacionalidades de sabor (Argentina, Brasil, España, Inglaterra, Italia,
Francia, Alemania), sin ningún jugador ni club real. Los atributos de
juego siempre se calculan acá, nunca se copian de FIFA/FM/Opta ni de
ninguna base con licencia. Si en algún momento querés cargar nombres
reales, hacelo vos por tu cuenta bajo tu responsabilidad (mismo criterio
que usan los juegos indie del género, tipo F11 Football Manager).

## Estructura

```
proyectoSoccerManager/
├── main.py                 # API FastAPI
├── database.py             # conexión SQLAlchemy async
├── models.py                # modelos ORM
├── schemas.py                # esquemas Pydantic
├── seed.py                   # poblar la liga inicial
├── engine/
│   ├── data_gen.py           # generador de nombres/atributos ficticios
│   ├── match_engine.py       # simulación minuto a minuto + IA táctica
│   ├── tactics_engine.py     # modificadores de formación/mentalidad
│   ├── injury_engine.py      # lesiones
│   ├── training_engine.py    # entrenamiento semanal
│   ├── season_engine.py      # desgaste, envejecimiento, retiros
│   ├── transfer_engine.py    # evaluación de ofertas
│   └── ai_engine.py          # IA de mercado de los rivales
└── soccer-frontend/          # React + Vite
```
