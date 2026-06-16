@echo off
REM Run the narrative ingest loop (polls all sources, stores to hype.db).
cd /d "%~dp0"
uv run python -m glory_hype ingest
