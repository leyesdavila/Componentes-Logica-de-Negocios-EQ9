# Regenera todas las evidencias y documentos de TechStore U4.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\generar_evidencias.ps1
#
# Requiere:
#   * .venv con fastapi, uvicorn, pytest y httpx;
#   * Python del sistema con python-docx (para los documentos);
#   * Microsoft Word (para exportar los PDF).
#
# El manifiesto se regenera al final, cuando los DOCX y PDF ya existen, para
# que el inventario registre su tamano definitivo.

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

$PythonVenv = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonVenv)) {
    throw "No existe .venv. Cree el entorno con: python -m venv .venv"
}

$PythonDocs = "C:\Python314\python.exe"
if (-not (Test-Path $PythonDocs)) {
    $PythonDocs = (Get-Command python).Source
}

function Invoke-Native {
    param(
        [string]$Mensaje,
        [string]$Ejecutable,
        [string[]]$Argumentos
    )
    Write-Host $Mensaje
    # PowerShell 5.1 trata cualquier linea de stderr como error nativo; se
    # permite la salida y se decide por el codigo de salida real.
    $anterior = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Ejecutable @Argumentos
    $codigo = $LASTEXITCODE
    $ErrorActionPreference = $anterior
    if ($codigo -ne 0) {
        throw "El comando $Ejecutable termino con codigo $codigo"
    }
}

Invoke-Native "1/6 Cargador de CSV..." $PythonVenv @("cargar_csv.py")
Invoke-Native "2/6 Bitacora E01-E15..." $PythonVenv @("scripts\ejecutar_bitacora.py")
Invoke-Native "3/6 Evidencias de pruebas y API..." $PythonVenv @("scripts\generar_evidencias.py")
Invoke-Native "4/6 Documentos DOCX..." $PythonDocs @("scripts\generar_documentos.py")

Write-Host "5/6 Exportacion a PDF..."
& (Join-Path $PSScriptRoot "exportar_pdf.ps1")

Invoke-Native "6/6 Manifiesto con los documentos definitivos..." $PythonVenv @("scripts\generar_evidencias.py", "--solo-manifiesto")

Write-Host "Listo. Revise MANIFIESTO_ENTREGA.txt y docs\."
