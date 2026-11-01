# Checklist de release (puerta verde obligatoria)

```bat
python scripts/release_gates.py        & rem gates rápidos (~1 min)
python scripts/release_gates.py --full & rem + regla de oro y perf (~10-20 min, Manim real)
```

| # | Gate | Qué verifica | Dónde |
|---|------|--------------|-------|
| 1 | Sintaxis JS | `node --check` de `app.js` y `zoom.js` | `release_gates.py` |
| 2 | IDs únicos | Sin `id=` duplicados en el frontend (anti bug "clic borra la app") | `tests/test_ids.py` |
| 3 | Demo | `demo/escena_demo.py` → 4 fórmulas, 3 transiciones, 0 avisos | `release_gates.py` |
| 4 | Humo web | Carga sin `pageerror`/errores de consola, tour visible, botón demo existe | `release_gates.py` |
| 5 | Regla de oro (`--full`) | DOM == API en 6 tipos de ecuación × 3 pares | `tests/test_canvas.py` |
| 6 | Anti-solape (`--full`) | Insignias sin traslapes | `tests/test_canvas.py` |
| 7 | Perf minimapa (`--full`) | Pan ≤ 16.7 ms avg (solo mueve el rect del viewport) | `tests/test_canvas.py` |

Nada se publica con un gate en rojo. Si un gate lento falla, el log queda en
`%LOCALAPPDATA%\Temp\opencode\gates-*.log`.
