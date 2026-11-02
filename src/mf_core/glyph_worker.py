"""Worker en proceso independiente: recibe JSON, devuelve JSON. La UI nunca compila LaTeX en su hilo."""
import json
import sys


def main() -> int:
    try:
        raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
        req = json.loads(raw)
        latex = req.get("latex", "")
        path = req.get("path", [0])
        args = req.get("args", None)
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            args = None
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"request invalido: {e}"}))
        return 0
    sys.path.insert(0, "src")
    try:
        from mf_core.extractor import extract_glyphs
    except ImportError:  # fallback si se invoca desde otro cwd
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        sys.path.insert(0, os.path.join(os.getcwd(), "src"))
        from mf_core.extractor import extract_glyphs
    print(json.dumps(_render_with_retry(extract_glyphs, latex, path, args=args)))
    return 0


def _render_with_retry(extract_glyphs, latex: str, path: list[int], attempts: int = 6,
                       args: list[str] | None = None) -> dict:
    """Reintenta errores transitorios de .dvi bloqueado por otro render paralelo (WinError 32)."""
    import time
    last: dict = {"ok": False, "error": "sin intentos"}
    for i in range(attempts):
        last = extract_glyphs(latex, path, args=args)
        if last.get("ok"):
            return last
        err = str(last.get("error", ""))
        transient = ("dvi" in err.lower() or "WinError 32" in err
                     or "being used by another process" in err
                     or "PermissionError" in err)
        if not transient or i == attempts - 1:
            return last
        time.sleep(1 + i)  # backoff 1,2,3...s
    return last


if __name__ == "__main__":
    raise SystemExit(main())
