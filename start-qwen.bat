@echo off
REM Glory Qwen launcher — Qwen3.6-35B-A3B Q3_K_S, port 1053
REM Runs alongside Gemma (port 1052). Start this when you need Qwen locally.

set LLAMA="C:\Users\dalei\.unsloth\llama.cpp\build\bin\Release\llama-server.exe"
set MODEL="D:\Glory\huggingface\hub\models--unsloth--Qwen3.6-35B-A3B-GGUF\snapshots\a483e9e6cbd595906af30beda3187c2663a1118c\Qwen3.6-35B-A3B-UD-Q3_K_S.gguf"
set MMPROJ="D:\Glory\huggingface\hub\models--unsloth--Qwen3.6-35B-A3B-GGUF\snapshots\a483e9e6cbd595906af30beda3187c2663a1118c\mmproj-F16.gguf"

taskkill /f /fi "WINDOWTITLE eq qwen-server" 2>nul
timeout /t 1 /nobreak >nul

start "qwen-server" /b %LLAMA% -m %MODEL% --port 1053 -c 8192 --parallel 1 --flash-attn on --fit on --threads -1 --jinja --chat-template-kwargs "{\"enable_thinking\": false}" --mmproj %MMPROJ%

echo Qwen3.6-35B started on port 1053 (ctx 8192 to fit alongside Gemma)
echo Proxy routes "qwen" calls to 127.0.0.1:1053 automatically.
