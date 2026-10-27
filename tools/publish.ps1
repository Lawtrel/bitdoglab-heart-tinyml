param()
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$gitCommand = Get-Command git -ErrorAction Stop
$remote = (& $gitCommand.Source remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $remote -ne 'https://github.com/Lawtrel/bitdoglab-heart-tinyml.git') {
    throw 'O origin não corresponde ao repositório preparado. Nada foi enviado.'
}
$branch = (& $gitCommand.Source branch --show-current).Trim()
if ($branch -ne 'main') { throw 'Esperada a branch main. Nada foi enviado.' }
$pending = & $gitCommand.Source status --porcelain
if ($pending) { throw 'Há arquivos sem commit. Revise as alterações antes de publicar; este iniciador não adiciona arquivos.' }
Write-Host 'Enviando o commit preparado para Lawtrel/bitdoglab-heart-tinyml (PUBLICO).'
Write-Host 'Se o Git pedir autenticação, use sua conta Lawtrel no navegador. Não compartilhe tokens.'
& $gitCommand.Source push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'O envio não concluiu. Consulte a mensagem do Git acima.' }
Write-Host 'PUSH_CONCLUIDO: https://github.com/Lawtrel/bitdoglab-heart-tinyml'
