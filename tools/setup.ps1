param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonArgs = @()
if (!$Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = 'py'; $pythonArgs = @('-3.12')
    } else { $Python = 'python' }
}
& $Python @pythonArgs -c "import sys; assert sys.version_info[:2] == (3,12), 'Use Python 3.12'"
if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.12 ou informe -Python com o caminho desse interpretador.' }
$venv = Join-Path $projectRoot '.venv'
if (!(Test-Path -LiteralPath $venv)) {
    & $Python @pythonArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente.' }
}
$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install -e $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Falha na instalação. Consulte o erro acima.' }
Write-Host 'Ambiente pronto. Execute START_WINDOWS.cmd.'
