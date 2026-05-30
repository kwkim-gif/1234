# W-Sub CUDA reinstall script (PowerShell / Windows Terminal)
# Run via: reinstall_cuda_run.bat  (handles ExecutionPolicy automatically)
# ASCII-only to avoid PowerShell file-encoding issues.

$ErrorActionPreference = "Continue"

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " W-Sub CUDA reinstall" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Removes CPU PyTorch and installs CUDA 12.1 versions." -ForegroundColor Yellow
Write-Host " Also installs nvidia-cublas-cu12 / nvidia-cudnn-cu12 DLL wheels." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to continue (Ctrl+C to cancel)"

Set-Location -Path $PSScriptRoot

# ?? Activate venv -------------------------------------------------
Write-Host ""
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$venvPip    = Join-Path $PSScriptRoot ".venv\Scripts\pip.exe"
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

if (Test-Path $venvPython) {
    Write-Host "[OK] Found .venv" -ForegroundColor Green
    # Use venv python/pip directly (Activate.ps1 may fail on restricted policy)
    $PY  = $venvPython
    $PIP = $venvPip
} else {
    Write-Host "[WARN] .venv not found -- using system Python." -ForegroundColor Yellow
    Write-Host "       Run:  python -m venv .venv   then retry." -ForegroundColor Yellow
    $PY  = "python"
    $PIP = "pip"
}

# Show which python is being used
& $PY --version
Write-Host "Python path: $PY" -ForegroundColor Gray

# ?? Check GPU -------------------------------------------------------
Write-Host ""
Write-Host "[CHECK] Detecting NVIDIA GPU..." -ForegroundColor Cyan
if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] nvidia-smi not found. Install the GPU driver:" -ForegroundColor Red
    Write-Host "        https://www.nvidia.com/drivers" -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
Write-Host "[OK] NVIDIA GPU detected" -ForegroundColor Green

# ?? Uninstall existing packages ------------------------------------
Write-Host ""
Write-Host "[REMOVE] Uninstalling existing PyTorch / CUDA packages..." -ForegroundColor Cyan
& $PIP uninstall -y torch torchvision torchaudio 2>&1 | Out-Null
& $PIP uninstall -y nvidia-cublas-cu11 nvidia-cuda-runtime-cu11 2>&1 | Out-Null
& $PIP uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 2>&1 | Out-Null
& $PIP uninstall -y ctranslate2 faster-whisper 2>&1 | Out-Null
Write-Host "[OK] Uninstall done" -ForegroundColor Green

# ?? Install PyTorch CUDA 12.1 --------------------------------------
Write-Host ""
Write-Host "[INSTALL] PyTorch 2.x + CUDA 12.1  (~2-4 GB download)..." -ForegroundColor Cyan
& $PIP install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyTorch install failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

# Verify CUDA torch
$torchCheck = & $PY -c "import torch; print(torch.__version__, torch.cuda.is_available())"
Write-Host "[PyTorch] $torchCheck" -ForegroundColor Cyan
if ($torchCheck -notmatch "True") {
    Write-Host "[WARN] torch.cuda.is_available() = False" -ForegroundColor Yellow
    Write-Host "       Check your GPU driver or CUDA toolkit." -ForegroundColor Yellow
} else {
    Write-Host "[OK] PyTorch CUDA 12.1 installed and CUDA is available" -ForegroundColor Green
}

# ?? Install faster-whisper -----------------------------------------
Write-Host ""
Write-Host "[INSTALL] faster-whisper (latest)..." -ForegroundColor Cyan
& $PIP install faster-whisper --upgrade
Write-Host "[OK] faster-whisper installed" -ForegroundColor Green

# ?? Install CUDA 12 DLL wheels ------------------------------------
Write-Host ""
Write-Host "[INSTALL] nvidia-cublas-cu12 nvidia-cudnn-cu12..." -ForegroundColor Cyan
& $PIP install nvidia-cublas-cu12 nvidia-cudnn-cu12
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] nvidia DLL wheels failed -- torch/lib will be used as fallback." -ForegroundColor Yellow
} else {
    Write-Host "[OK] CUDA 12 DLL wheels installed" -ForegroundColor Green
}

# ?? Verify --------------------------------------------------------
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " Verification" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
& $PY (Join-Path $PSScriptRoot "check_cuda.py")

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host " Done. Run W-Sub:  python main.py" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
