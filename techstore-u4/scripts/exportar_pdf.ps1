# Exporta los documentos DOCX de TechStore U4 a PDF con Microsoft Word.
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\exportar_pdf.ps1 -Documentos "docs\Reporte_Tecnico_TechStore_Unidad_4.docx"
#
# El script abre cada DOCX, actualiza los campos (incluido el indice
# automatico), guarda el DOCX actualizado y exporta el PDF en la misma carpeta.

param(
    [string[]]$Documentos = @(
        "docs\Reporte_Tecnico_TechStore_Unidad_4.docx",
        "docs\bitacora\Bitacora_TechStore.docx"
    )
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
$Word = $null
$Abiertos = @()

try {
    $Word = New-Object -ComObject Word.Application
    $Word.Visible = $false
    $Word.DisplayAlerts = 0

    foreach ($relativo in $Documentos) {
        $docx = Join-Path $Raiz $relativo
        if (-not (Test-Path $docx)) {
            Write-Warning "No existe: $docx"
            continue
        }

        $pdf = [System.IO.Path]::ChangeExtension($docx, ".pdf")
        $documento = $Word.Documents.Open($docx, $false, $false)
        $Abiertos += $documento

        # Compactar el indice para que no ocupe paginas casi vacias.
        foreach ($nombreEstilo in @("TOC 1", "TOC 2")) {
            try {
                $estilo = $documento.Styles.Item($nombreEstilo)
                $estilo.Font.Size = 9.5
                $estilo.ParagraphFormat.SpaceBefore = 0
                $estilo.ParagraphFormat.SpaceAfter = 1
                $estilo.ParagraphFormat.LineSpacingRule = 0
            }
            catch { }
        }

        # Actualizar indice y todos los campos (numeracion, referencias).
        foreach ($indice in $documento.TablesOfContents) {
            $indice.Update()
        }
        $documento.Fields.Update() | Out-Null
        $documento.Save()

        # wdExportFormatPDF = 17
        $documento.ExportAsFixedFormat($pdf, 17)
        Write-Host ("PDF: {0}" -f $pdf)

        $documento.Close(0)
        $Abiertos = $Abiertos | Where-Object { $_ -ne $documento }
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($documento) | Out-Null
    }
}
finally {
    foreach ($documento in $Abiertos) {
        try { $documento.Close(0) } catch { }
    }
    if ($Word -ne $null) {
        $Word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($Word) | Out-Null
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Write-Host "Exportacion terminada."
