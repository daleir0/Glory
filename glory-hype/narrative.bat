@echo off
REM Synthesize the current narrative conclusion and print it.
cd /d "%~dp0"
uv run python -m glory_hype narrative
