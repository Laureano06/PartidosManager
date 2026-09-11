# AI_CONTEXT.md

Purpose: compact orientation for coding agents. Read this first; inspect only files relevant to the current task.

Stack:
- Backend: FastAPI, SQLAlchemy async, PostgreSQL/SQLite. Entry point: main.py.
- Domain logic: engine/*.py.
- Frontend: React 19 + Vite in soccer-frontend/.
- Frontend source: soccer-frontend/src/.
- Data-pack logic: pack_engine.py and EditorPage.jsx / CrearCarreraPage.jsx.

Context discipline:
- Do NOT recursively read the whole repository.
- Start from README.md + this file, then open only files named by the task or directly imported/called by them.
- Do not inspect generated dependencies, virtual environments, git history, build output, databases, or binary assets unless the task explicitly requires them.
- For broad work, keep a short PROGRESS.md with completed changes, current issue, tests run, and next step so a fresh thread can resume without chat history.
- Prefer one feature/bug per thread.

Important:
- Never print or commit secrets. Use .env locally and .env.example as a template.
- main.py is large; avoid loading it repeatedly. Search for the relevant endpoint/function first, then read only the surrounding section.
