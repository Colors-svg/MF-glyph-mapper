"""Worker de vista previa (Fase 5). Proceso independiente: renderiza la
transformacion real con Manim y extrae el fotograma final con ffmpeg."""
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _manim() -> list[str]:
    return [sys.executable, "-m", "manim", "render"]


def _quiet_kwargs() -> dict:
    """Sin ventanas de consola en Windows (los flashes de latex/dvisvgm/ffmpeg)."""
    if sys.platform != "win32":
        return {}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
                "startupinfo": si}
    except Exception:
        return {}


def main() -> int:
    try:
        raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
        req = json.loads(raw)
        latex_a = req["latex_a"]
        latex_b = req["latex_b"]
        glyph_map = req.get("glyph_map", [])
        quality = req.get("quality", "l")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"request invalido: {e}"}))
        return 0
    root = Path.cwd()
    t0 = time.time()
    log_tail = ""
    try:
        with tempfile.TemporaryDirectory(dir=str(root), prefix=".tmp_prev_") as tmp:
            scene = Path(tmp) / "prev_scene.py"
            rows = []
            for e in glyph_map:
                f = sorted(e[0]) if len(e) > 0 else []
                t = sorted(e[1]) if len(e) > 1 else []
                if len(e) > 2 and isinstance(e[2], dict) and "path_arc" in e[2]:
                    try:
                        rows.append(f"        ({f}, {t}, {{\"path_arc\": {float(e[2]['path_arc']):.6g}}}),")
                        continue
                    except Exception:
                        pass
                rows.append(f"        ({f}, {t}),")
            body = "\n".join(rows)
            scene.write_text(
                "from manim import *\nfrom MF_Tools import TransformByGlyphMap\n\n"
                "class PrevScene(Scene):\n"
                "    def construct(self):\n"
                f"        mobA = MathTex(r\"{latex_a}\")\n"
                f"        mobB = MathTex(r\"{latex_b}\")\n"
                "        self.add(mobA)\n"
                "        glyph_map = [\n" + body + "\n        ]\n"
                "        self.play(TransformByGlyphMap(mobA, mobB, *glyph_map))\n"
                # D38: el video debe TERMINAR en la fórmula final asentada, no en
                # el último instante de la interpolación. La pausa fija el final.
                "        self.wait(0.5)\n",
                encoding="utf-8",
            )
            p = subprocess.run(
                _manim() + ["-q" + quality, "--media_dir", str(Path(tmp) / "media"),
                            str(scene), "PrevScene"],
                capture_output=True, text=True, timeout=300, cwd=str(root),
                **_quiet_kwargs(),
            )
            log_tail = (p.stdout + p.stderr)[-2000:]
            if p.returncode != 0:
                print(json.dumps({"ok": False, "error": f"manim rc={p.returncode}",
                                            "log": log_tail}))
                return 0
            mp4s = sorted(Path(tmp).rglob("PrevScene.mp4"))
            if not mp4s:
                print(json.dumps({"ok": False, "error": "sin mp4 generado", "log": log_tail}))
                return 0
            out_dir = root / "previews"
            out_dir.mkdir(exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{int(time.time() * 1000) % 1000:03d}"
            mp4 = out_dir / f"preview_{stamp}.mp4"
            png = out_dir / f"preview_{stamp}_final.png"
            shutil.copy(mp4s[0], mp4)
            # D38: extraer dentro de la pausa final (frame asentado), no a mitad
            # de la transición como hacía el -0.3 anterior.
            f = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(mp4),
                 "-vframes", "1", str(png)],
                capture_output=True, text=True, timeout=60,
                **_quiet_kwargs(),
            )
            if f.returncode != 0 or not png.exists():
                print(json.dumps({"ok": False, "error": "ffmpeg no extrajo fotograma",
                                            "log": log_tail + (f.stderr or "")[-500:]}))
                return 0
            print(json.dumps({"ok": True, "mp4": str(mp4), "png": str(png),
                                        "seconds": round(time.time() - t0, 1),
                                        "log": log_tail[-500:]}))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}", "log": log_tail}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
