path = 'E:/Glory/glory-rooms/proxy/lm-proxy.py'
with open(path, encoding='utf-8') as f:
    data = f.read()

replacements = {
    '“': '"',
    '”': '"',
    '‘': "'",
    '’': "'",
}
for bad, good in replacements.items():
    data = data.replace(bad, good)

with open(path, 'w', encoding='utf-8') as f:
    f.write(data)

import subprocess
r = subprocess.run(['python', '-m', 'py_compile', path], capture_output=True, text=True)
print('Syntax OK' if r.returncode == 0 else r.stderr)
