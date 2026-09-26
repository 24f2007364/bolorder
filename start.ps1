$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$workspacePython = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) {
    if (Test-Path -LiteralPath $workspacePython) {
        $pythonPath = (Resolve-Path -LiteralPath $workspacePython).Path
    } else {
        python -m venv .venv
        & $pythonPath -m pip install -r requirements.txt
    }
}
& $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
