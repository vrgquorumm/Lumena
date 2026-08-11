---
name: asyncpg Nix package version mismatch (Lumena bot)
description: Why asyncpg silently failed to import even with DATABASE_URL set, breaking PostgreSQL persistence
---

## Symptom
`import asyncpg` raised `ModuleNotFoundError: No module named 'asyncpg.protocol.protocol'`, and the bot logged
"asyncpg не встановлено — PostgreSQL вимкнено" even though `requirements.txt` lists `asyncpg` and pip reported it
as already installed.

## Root cause
`replit.nix` declared `pkgs.python313Packages.asyncpg` as a system-level Nix dependency, but the project's actual
interpreter is Python 3.11 (`.pythonlibs`). Nix injected the 3.13-built asyncpg's compiled `.so` earlier on
`PYTHONPATH` than the correct pip-installed 3.11 wheel in `.pythonlibs/lib/python3.11/site-packages`, so the
mismatched native extension always loaded first and failed to import its C module.

**Why this matters:** for the Lumena bot, this silently disabled all PostgreSQL persistence, which in turn made
one-time destructive migrations (balance wipes/transfers) re-fire on every restart because their "already ran"
version flag never durably persisted — the visible symptom was "everyone's coins keep disappearing."

## Fix
Remove the stray Nix package (`uninstallSystemDependencies(["python313Packages.asyncpg"])`) and let pip manage
`asyncpg` purely through `requirements.txt`/`.pythonlibs`. After removal, `import asyncpg` resolved to the correct
3.11 wheel and PostgreSQL connected successfully.

## How to apply
If a Python (or any language) native package is "installed" per pip/package manager but still fails to import in a
Replit workspace, check `replit.nix` / `.replit` for a duplicate system-level Nix package pinned to a different
language version than the one actually running the code — it silently shadows the correct install via `PYTHONPATH`
(or equivalent) ordering.
