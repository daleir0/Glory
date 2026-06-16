---
type: research-note
domain: Programming
confidence: verified
source: "Unsloth Studio debugging — observations 1432–1440, session May 18 2026"
date: 2026-05-18
tags: [python, pip, dependencies, packaging, unsloth, debugging]
---
# Python Packages Can Ship with Incomplete dependency Declarations

## What

A Python package's declared dependencies (in `pyproject.toml` or `setup.py`) may not match the packages actually required to run the software. Unsloth Studio 2025.3.1 declared only 9 dependencies but required dozens more (fastapi, uvicorn, structlog, matplotlib, python-multipart, websockets, openai, etc.) that had to be installed manually.

The complete list was buried in internal requirements files (`requirements.txt`, `extras.txt`) inside the package directory — never used by pip during installation.

## Why It Matters

When a Python tool crashes with `ModuleNotFoundError` even after a clean install, the package metadata is lying. The fix is: find the package's internal requirements files (in site-packages) and install them directly. Do not trust that `pip install <package>` gives you a runnable environment.

## Source

Unsloth Studio startup debugging, May 18 2026. Observations 1426–1440. Fixed by: `pip install structlog fastapi uvicorn matplotlib python-multipart websockets openai fastmcp`.

## Connected To

- [[05 - Research/Systems/2026-05-17-wsl-mirrored-networking]]
