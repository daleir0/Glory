path = r'E:\Glory\glory-rooms\proxy\lm-proxy.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add get_anthropic_key before now_iso
marker1 = 'def now_iso():'
insert1 = '''def get_anthropic_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        cfg = os.path.expanduser("~/lm-proxy-config.json")
        if os.path.exists(cfg):
            with open(cfg) as f2:
                key = __import__('json').load(f2).get("anthropic_api_key", "")
    return key


'''
if 'get_anthropic_key' not in content:
    content = content.replace(marker1, insert1 + marker1)
    print('Step 1: get_anthropic_key added')
else:
    print('Step 1: already present')

# 2. Add ANTHROPIC constants + anthropic_call before BACKENDS dict
marker2 = 'BACKENDS = {'
insert2 = '''ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "120"))
CLAUDE_ALIASES = {"claude", "claude-opus", "claude-opus-4-8", "opus", "anthropic"}


def anthropic_call(model_id, messages, max_tokens=1024, temperature=1.0):
    key = get_anthropic_key()
    if not key:
        raise BackendError("ANTHROPIC_API_KEY not set")
    system = ""
    convo = []
    for m in messages:
        if m["role"] == "system":
            system += (m.get("content") or "") + "\\n"
        else:
            convo.append({"role": m["role"], "content": m.get("content") or ""})
    body = {"model": model_id, "max_tokens": max_tokens,
            "temperature": temperature, "messages": convo}
    if system.strip():
        body["system"] = system.strip()
    req = urllib.request.Request(
        ANTHROPIC_URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=CLAUDE_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode("utf-8", errors="replace")
        except Exception:
            err = str(e)
        raise BackendError(f"HTTP {e.code}: {err[:500]}") from e
    except Exception as e:
        raise BackendError(f"network error: {e}") from e
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


'''
if 'anthropic_call' not in content:
    content = content.replace(marker2, insert2 + marker2, 1)
    print('Step 2: anthropic_call added')
else:
    print('Step 2: already present')

# 3. Add claude entry to BACKENDS (find the qwen line and insert after)
old3 = '"qwen":  {"backend": "lm-studio",  "underlying": QWEN_MODEL,\n              "call": lambda msgs, **opts: lmstudio_call(QWEN_MODEL, msgs, **opts)},'
new3 = '"qwen":  {"backend": "lm-studio",  "underlying": QWEN_MODEL,\n              "call": lambda msgs, **opts: lmstudio_call(QWEN_MODEL, msgs, **opts)},\n    "claude": {"backend": "anthropic", "underlying": CLAUDE_MODEL,\n               "call": lambda msgs, **opts: {\n                   "text": anthropic_call(CLAUDE_MODEL, msgs, **opts),\n                   "raw": None, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0}},'
if '"claude"' not in content:
    if old3 in content:
        content = content.replace(old3, new3)
        print('Step 3: claude backend registered')
    else:
        # Try with CRLF
        old3_crlf = old3.replace('\n', '\r\n')
        if old3_crlf in content:
            content = content.replace(old3_crlf, new3)
            print('Step 3: claude backend registered (CRLF)')
        else:
            print('Step 3: FAILED')
            idx = content.find('lmstudio_call(QWEN_MODEL')
            print(f'  qwen pattern at idx {idx}')
            print(f'  context: {repr(content[idx-10:idx+80])}')
else:
    print('Step 3: already present')

# 4. Add CLAUDE_ALIASES routing in call_backend
old4 = '    elif name in GEMMA_ALIASES:\n        name = "gemma"\n    spec = BACKENDS.get(name)'
new4 = '    elif name in GEMMA_ALIASES:\n        name = "gemma"\n    elif name in CLAUDE_ALIASES:\n        name = "claude"\n    spec = BACKENDS.get(name)'
if old4 in content:
    content = content.replace(old4, new4)
    print('Step 4: CLAUDE_ALIASES routing added')
else:
    # Try CRLF
    old4_crlf = old4.replace('\n', '\r\n')
    if old4_crlf in content:
        content = content.replace(old4_crlf, new4)
        print('Step 4: CLAUDE_ALIASES routing added (CRLF)')
    else:
        print('Step 4: FAILED')
        idx = content.find('elif name in GEMMA_ALIASES')
        print(f'  gemma pattern at idx {idx}')
        print(f'  context: {repr(content[idx-5:idx+100])}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done.')
