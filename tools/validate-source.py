"""Source/configuration checks only. Does not compile C# or replace Unity tests."""
from pathlib import Path
import json
import re
root = Path(__file__).resolve().parent.parent
for p in [root/'Packages/manifest.json', *root.glob('Assets/**/*.asmdef')]:
    json.loads(p.read_text())
assets = list(root.glob('Assets/**/*.cs')) + list(root.glob('Assets/**/*.asmdef'))
guids = []
for p in assets:
    meta = Path(str(p)+'.meta')
    assert meta.exists(), f'Missing metadata: {p}'
    guids.append(re.search(r'^guid: ([0-9a-f]{32})$', meta.read_text(), re.M)[1])
assert len(guids) == len(set(guids)), 'Duplicate GUIDs'
source = (root/'Assets/Scripts/WorldBuilderRuntime.cs').read_text()
assert not re.search(r'\bInput\.(GetAxis|GetMouseButton|mouseScrollDelta)', source)
assert 'cullingMask = 1 << 30' in source and 'cullingMask = 1 << 31' in source
assert 'RuntimeInitializeOnLoadMethod' in source
print(f'PASS: JSON configuration, {len(assets)} asset GUIDs, input migration and bootstrap source checks')
