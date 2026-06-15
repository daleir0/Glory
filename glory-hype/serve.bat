@echo off
REM Start the HYPE dashboard (read-only). Open http://localhost:5179
cd /d "%~dp0"
uv run python -m glory_hype serve --port 5179
