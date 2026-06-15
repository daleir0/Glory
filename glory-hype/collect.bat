@echo off
REM Start the HYPE data collector daemon (backfill + live WebSocket + REST poll).
cd /d "%~dp0"
uv run python -m glory_hype collect
