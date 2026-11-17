$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$previous = $env:R36_PROJECT_ROOT
try {
    $env:R36_PROJECT_ROOT = $project
    & python (Join-Path $PSScriptRoot 'tools\acceptance.py') --bundle $PSScriptRoot --wait 180
    $code = $LASTEXITCODE
} finally {
    $env:R36_PROJECT_ROOT = $previous
}
exit $code
