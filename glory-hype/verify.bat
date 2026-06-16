@echo off
REM Diff stored data against the live exchange. Run while collect.bat is running.
cd /d "%~dp0"
uv run python -m glory_hype verify
