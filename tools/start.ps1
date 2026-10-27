param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) {
    throw 'Execute SETUP_WINDOWS.cmd uma vez para preparar o ambiente Python 3.12.'
}
# Executa o checkout atual mesmo se uma instalacao anterior ainda estiver aberta.
$env:PYTHONPATH = Join-Path $projectRoot 'src'
& $pythonExe -m heart_tinyml serve
if ($LASTEXITCODE -ne 0) { throw 'Consulte a mensagem do aplicativo acima.' }
