"""Shim Windows: silencia las ventanas de consola de latex/dvisvgm/ffmpeg.

Python importa `sitecustomize` al arrancar si esta carpeta esta en PYTHONPATH.
El servidor la inyecta en `_run_worker`, asi todo el arbol (workers -> manim ->
latex, dvisvgm, ffmpeg) hereda el silencio sin tocar codigo de Manim.
Defensivo: cualquier fallo desactiva el parche en silencio.
"""
try:
    import sys

    if sys.platform == "win32":
        import subprocess

        _CREATION = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _USESHOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        _HIDE = getattr(subprocess, "SW_HIDE", 0)
        _orig_init = subprocess.Popen.__init__

        def _quiet_init(self, *args, **kwargs):
            try:
                kwargs.setdefault("creationflags", _CREATION)
                if kwargs.get("startupinfo") is None and _USESHOW:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= _USESHOW
                    si.wShowWindow = _HIDE
                    kwargs["startupinfo"] = si
            except Exception:
                pass
            _orig_init(self, *args, **kwargs)

        subprocess.Popen.__init__ = _quiet_init
except Exception:
    pass
