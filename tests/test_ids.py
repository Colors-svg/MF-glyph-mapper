"""Guarda: sin ids duplicados en el frontend (el bug del #stage duplicado)."""
import re
from pathlib import Path

for html in (Path(__file__).resolve().parent.parent / "web" / "static").glob("*.html"):
    ids = re.findall(r'id="([^"]+)"', html.read_text(encoding="utf-8"))
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"{html.name}: ids duplicados {dupes}"
    print(html.name, f"{len(ids)} ids unicos OK")

# el lienzo y su contenedor deben tener ids distintos y existir una sola vez
idx = (Path(__file__).resolve().parent.parent / "web" / "static" / "index.html").read_text(encoding="utf-8")
assert idx.count('id="workspace"') == 1 and idx.count('id="stage"') == 1
print("workspace/stage unicos OK")
print("ALL ID TESTS PASSED")
