path = r'E:\Glory\glory-rooms\proxy\lm-proxy.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add claude entry to BACKENDS dict
# The qwen line pattern
import re

# Find BACKENDS block and check if claude is there
if '"claude"' in content[content.find('BACKENDS = {'):content.find('BACKENDS = {') + 800]:
    print('claude already in BACKENDS')
else:
    # Insert claude entry after qwen entry, before closing }
    old = '    "qwen":  {"backend": "lm-studio",  "underlying": QWEN_MODEL,\n              "call": lambda msgs, **opts: lmstudio_call(QWEN_MODEL, msgs, **opts)},\n}'
    new = '    "qwen":  {"backend": "lm-studio",  "underlying": QWEN_MODEL,\n              "call": lambda msgs, **opts: lmstudio_call(QWEN_MODEL, msgs, **opts)},\n    "claude": {"backend": "anthropic", "underlying": CLAUDE_MODEL,\n               "call": lambda msgs, **opts: {\n                   "text": anthropic_call(CLAUDE_MODEL, msgs, **opts),\n                   "raw": None, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0}},\n}'
    if old in content:
        content = content.replace(old, new)
        print('claude entry added to BACKENDS (LF)')
    else:
        # Check what's actually there
        idx = content.find('lmstudio_call(QWEN_MODEL, msgs, **opts)}')
        ctx = repr(content[idx-2:idx+60])
        print(f'Pattern not found. Context around qwen: {ctx}')

        # Try with the actual content
        # Find the BACKENDS closing
        backends_start = content.find('BACKENDS = {')
        backends_end = content.find('\n}', backends_start) + 2
        backends_block = content[backends_start:backends_end]
        print(f'BACKENDS block:\n{repr(backends_block)}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done.')
