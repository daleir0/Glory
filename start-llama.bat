@echo off
REM Glory llama-server — Gemma 4 E4B, 65536 context, port 1052
REM --jinja required for tool call message formatting.
REM Run this to start or restart after reboot.

set LLAMA="C:\Users\dalei\.unsloth\llama.cpp\build\bin\Release\llama-server.exe"
set MODEL="C:\Users\dalei\.lmstudio\models\lmstudio-community\gemma-4-E4B-it-GGUF\gemma-4-E4B-it-Q4_K_M.gguf"
set MMPROJ="C:\Users\dalei\.lmstudio\models\lmstudio-community\gemma-4-E4B-it-GGUF\mmproj-gemma-4-E4B-it-BF16.gguf"

taskkill /f /im llama-server.exe 2>nul
timeout /t 2 /nobreak >nul

start "" /b %LLAMA% -m %MODEL% --port 1052 -c 65536 --parallel 1 --flash-attn on --fit on --threads -1 --jinja --mmproj %MMPROJ%

echo Gemma 4 E4B started: port 1052, ctx 65536, jinja enabled
