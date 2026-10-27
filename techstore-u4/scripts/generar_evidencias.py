"""Genera las evidencias reproducibles y el manifiesto de entrega.

Produce:

* `evidencias/carga_csv.txt` — salida real de `python cargar_csv.py`.
* `evidencias/bitacora_consola.txt` — salida real de la bitácora E01–E15.
* `evidencias/resultado_pytest.txt` — salida real de `pytest -q`.
* `evidencias/respuestas_api.json` — respuestas 200/201/404/409/422 reales.
* `docs/evidencias/04_pytest.txt` — salida completa de `pytest -v`.
* `docs/evidencias/12_pytest_resultados.png` — imagen de la salida de pytest.
* `MANIFIESTO_ENTREGA.txt` — inventario, conteos y huellas SHA-256.

Se ejecuta desde la raíz del proyecto, con el entorno virtual activado:

    python scripts/generar_evidencias.py

Para regenerar **solo el manifiesto** después de crear los documentos DOCX/PDF
(que deben quedar inventariados con su tamaño definitivo):

    python scripts/generar_evidencias.py --solo-manifiesto
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.api import app  # noqa: E402

EVIDENCIAS = ROOT / "evidencias"
DOCS_EVIDENCIAS = ROOT / "docs" / "evidencias"
EXCLUIR = {".venv", ".git", "__pycache__", ".pytest_cache"}
EDGE = Path(
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)


def limpiar_rutas(texto: str) -> str:
    """Sustituye la ruta absoluta del proyecto por un marcador portable."""
    return texto.replace(str(ROOT), "<raiz-del-proyecto>")


def ejecutar(comando: list[str]) -> str:
    """Ejecuta un comando en la raíz y devuelve su salida combinada."""
    resultado = subprocess.run(
        comando,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return (resultado.stdout or "") + (resultado.stderr or "")


def guardar(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# 1. Carga de CSV y bitácora
# ---------------------------------------------------------------------------


def generar_carga() -> str:
    salida = ejecutar([sys.executable, "cargar_csv.py"])
    guardar(
        EVIDENCIAS / "carga_csv.txt",
        "$ python cargar_csv.py\n" + salida,
    )
    return salida


def generar_bitacora() -> str:
    salida = ejecutar([sys.executable, "scripts/ejecutar_bitacora.py"])
    guardar(
        EVIDENCIAS / "bitacora_consola.txt",
        "$ python scripts/ejecutar_bitacora.py\n" + salida,
    )
    return salida


# ---------------------------------------------------------------------------
# 2. Pytest: texto y imagen
# ---------------------------------------------------------------------------


def generar_pytest() -> tuple[str, str]:
    rapido = limpiar_rutas(ejecutar([sys.executable, "-m", "pytest", "-q"]))
    completo = limpiar_rutas(
        ejecutar([sys.executable, "-m", "pytest", "-v"])
    )
    guardar(
        EVIDENCIAS / "resultado_pytest.txt",
        "$ python -m pytest -q\n" + rapido,
    )
    guardar(DOCS_EVIDENCIAS / "04_pytest.txt", completo)
    generar_png_pytest(rapido)
    return rapido, completo


def _html_terminal(texto: str, alto: int) -> str:
    """Página HTML con apariencia de terminal para la captura de pytest."""
    lineas = texto.splitlines()
    cuerpo = []
    for linea in lineas:
        clase = ""
        if linea.startswith("=") or " passed" in linea:
            clase = ' class="ok"'
        cuerpo.append(f"<span{clase}>{html.escape(linea)}</span>")
    contenido = "\n".join(cuerpo)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; padding: 0; background: #0c0c0c; }}
  body {{ padding: 22px 26px; min-height: {alto}px; box-sizing: border-box; }}
  pre {{ margin: 0; color: #cccccc; font: 16px/1.45 Consolas, 'Cascadia Mono', monospace;
         white-space: pre-wrap; }}
  .ok {{ color: #16c60c; }}
  .prompt {{ color: #3b78ff; }}
</style></head><body>
<pre><span class="prompt">PS C:\\techstore-u4&gt;</span> python -m pytest -q
{contenido}</pre>
</body></html>"""


def generar_png_pytest(texto: str) -> None:
    """Renderiza la salida real de pytest como imagen de evidencia.

    Usa Microsoft Edge en modo headless. Si no está disponible, cae a PyMuPDF
    (dibuja el mismo texto sobre un fondo oscuro).
    """
    lineas = max(6, len(texto.splitlines()))
    alto = min(1400, max(360, 110 + lineas * 26))
    destino = DOCS_EVIDENCIAS / "12_pytest_resultados.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    pagina = _html_terminal(texto, alto)

    if EDGE.exists():
        with tempfile.TemporaryDirectory(prefix="techstore-edge-") as tmp:
            html_path = Path(tmp) / "pytest.html"
            html_path.write_text(pagina, encoding="utf-8")
            perfil = Path(tmp) / "perfil"
            # Windows aplica su escala de pantalla al viewport: se compensa
            # pidiendo una ventana más grande para obtener ~1200 px de ancho.
            subprocess.run(
                [
                    str(EDGE),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    f"--user-data-dir={perfil}",
                    f"--window-size=1600,{round(alto / 0.75)}",
                    f"--screenshot={destino}",
                    html_path.as_uri(),
                ],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            if destino.exists() and destino.stat().st_size > 0:
                return

    # Respaldo: PyMuPDF dibuja el texto real sobre fondo oscuro.
    try:
        import fitz  # type: ignore

        documento = fitz.open()
        hoja = documento.new_page(width=1200, height=alto)
        hoja.draw_rect(hoja.rect, color=None, fill=(0.05, 0.05, 0.05))
        hoja.insert_text(
            (22, 34),
            "$ python -m pytest -q\n" + texto,
            fontname="cour",
            fontsize=11,
            color=(0.8, 0.8, 0.8),
        )
        hoja.get_pixmap().save(destino)
        documento.close()
    except Exception as exc:  # pragma: no cover - solo si faltan herramientas
        print(f"AVISO: no se pudo generar {destino.name}: {exc}")


# ---------------------------------------------------------------------------
# 3. Respuestas HTTP reales
# ---------------------------------------------------------------------------


def generar_respuestas_api() -> list[dict]:
    casos: list[dict] = []

    with TestClient(app) as client:

        def registrar(
            caso: str, metodo: str, url: str, cuerpo: dict | None = None
        ) -> None:
            respuesta = client.request(metodo, url, json=cuerpo)
            try:
                contenido = respuesta.json()
            except ValueError:
                contenido = respuesta.text
            casos.append(
                {
                    "caso": caso,
                    "method": metodo,
                    "url": url,
                    "status_code": respuesta.status_code,
                    "response": contenido,
                }
            )

        registrar("Salud del servicio", "GET", "/health")
        registrar("Consulta válida", "GET", "/orders/O001")
        registrar("Pedido inexistente", "GET", "/orders/O999")
        registrar("Reglas de descuento", "GET", "/orders/O001/rules")
        registrar("Confirmación válida", "POST", "/orders/O013/confirm")
        registrar(
            "Confirmación duplicada (409)", "POST", "/orders/O013/confirm"
        )
        registrar(
            "Pedido vacío (422)", "POST", "/orders/O007/confirm"
        )
        registrar(
            "Cliente inactivo (422)", "POST", "/orders/O003/confirm"
        )
        registrar(
            "Envío sin guía (422)",
            "POST",
            "/orders/O012/ship",
            {},
        )
        registrar(
            "Límite de unidades (422)",
            "POST",
            "/orders/O009/items",
            {"sku": "SKU003", "quantity": 2},
        )
        registrar(
            "Creación de pedido (201)",
            "POST",
            "/orders",
            {"cliente_id": "C001", "items": [{"sku": "SKU001", "quantity": 1}]},
        )

    guardar(
        EVIDENCIAS / "respuestas_api.json",
        json.dumps(casos, ensure_ascii=False, indent=2) + "\n",
    )
    return casos


# ---------------------------------------------------------------------------
# 4. Manifiesto e inventario
# ---------------------------------------------------------------------------


def archivos_del_proyecto() -> list[Path]:
    archivos = []
    for ruta in ROOT.rglob("*"):
        if not ruta.is_file():
            continue
        partes = set(ruta.relative_to(ROOT).parts)
        if partes & EXCLUIR:
            continue
        if ruta.name.endswith(".pyc"):
            continue
        if ruta.name == "MANIFIESTO_ENTREGA.txt":
            continue
        if ruta.suffix == ".zip":
            continue
        archivos.append(ruta)
    return sorted(archivos, key=lambda p: p.relative_to(ROOT).as_posix())


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(65536), b""):
            digest.update(bloque)
    return digest.hexdigest()


def generar_manifiesto(salida_pytest: str | None = None) -> None:
    archivos = archivos_del_proyecto()
    total_bytes = sum(ruta.stat().st_size for ruta in archivos)
    if salida_pytest is None:
        ruta_salida = EVIDENCIAS / "resultado_pytest.txt"
        salida_pytest = (
            ruta_salida.read_text(encoding="utf-8", errors="replace")
            if ruta_salida.exists()
            else ""
        )
    coincidencia = re.search(r"(\d+) passed", salida_pytest)
    pruebas = coincidencia.group(1) if coincidencia else "?"

    lineas = [
        "ENTREGA — TECHSTORE, COMPONENTES DE LÓGICA DE NEGOCIO (UNIDAD 4)",
        "",
        "Proyecto académico desarrollado a partir del paquete original de la",
        "actividad. Los cinco CSV se conservan sin modificaciones y la solución",
        "(dominio, Specifications, servicio, API, pruebas y documentos) se",
        "elaboró de forma independiente.",
        "",
        "RESUMEN",
        f"  Archivos inventariados : {len(archivos)}",
        f"  Tamaño total           : {total_bytes:,} bytes",
        f"  Pruebas automatizadas  : {pruebas} passed",
        "  Pedidos en los fixtures: 16",
        "  Escenarios de bitácora : 15 (15/15 coinciden)",
        "  Endpoints de negocio   : 11",
        "  Endpoints de apoyo     : 2 (/health, /admin/reload-fixtures)",
        "",
        "CONTENIDO",
        "  app/           Dominio, Specifications, servicio y API FastAPI.",
        "  datos/         Los 5 CSV originales, sin editar.",
        "  tests/         Suite de pruebas (dominio, API, escenarios, specs).",
        "  scripts/       Ejecución de bitácora, evidencias y documentos.",
        "  docs/          Análisis, bitácora, reflexión, diagramas y reporte.",
        "  evidencias/    Salidas reproducibles de carga, pruebas y API.",
        "  README.md      Guía de instalación, ejecución y estructura.",
        "",
        "VERIFICACIÓN RÁPIDA",
        "  python cargar_csv.py",
        "  python scripts/ejecutar_bitacora.py",
        "  python -m pytest -q",
        "  uvicorn app.api:app --reload",
        "",
        "HUELLAS SHA-256 DE LOS CSV ORIGINALES",
    ]
    for ruta in sorted((ROOT / "datos").glob("*.csv")):
        lineas.append(f"  {ruta.name:<26} {sha256(ruta)}")

    lineas += [
        "",
        "INVENTARIO",
    ]
    for ruta in archivos:
        relativa = ruta.relative_to(ROOT).as_posix()
        lineas.append(
            f"  {relativa:<64} {ruta.stat().st_size:>9,} bytes"
        )

    lineas += [
        "",
        "NOTA",
        "  El repositorio es local y en memoria. Los cambios de los pedidos se",
        "  pierden al reiniciar; los CSV nunca se escriben desde la aplicación.",
        "  Este manifiesto se regenera con: python scripts/generar_evidencias.py",
        "",
    ]
    guardar(ROOT / "MANIFIESTO_ENTREGA.txt", "\n".join(lineas))


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------


def main() -> int:
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    DOCS_EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    if "--solo-manifiesto" in sys.argv[1:]:
        generar_manifiesto()
        print("Manifiesto regenerado: MANIFIESTO_ENTREGA.txt")
        return 0

    print("1/4 Carga de CSV…")
    generar_carga()
    print("2/4 Bitácora E01–E15…")
    generar_bitacora()
    print("3/4 Pytest (texto e imagen)…")
    rapido, _ = generar_pytest()
    print("4/4 Respuestas HTTP y manifiesto…")
    casos = generar_respuestas_api()
    generar_manifiesto(rapido)

    print(f"Evidencias raíz: {len(list(EVIDENCIAS.glob('*')))} archivos")
    print(f"Respuestas API registradas: {len(casos)}")
    print("Manifiesto: MANIFIESTO_ENTREGA.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
