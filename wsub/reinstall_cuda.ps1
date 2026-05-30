# W-Sub CUDA reinstall script (PowerShell / Windows Terminal)
#
# How to run (from the wsub folder):
#   Double-click reinstall_cuda_run.bat
#   or in PowerShell:  powershell -ExecutionPolicy Bypass -File .\reinstall_cuda.ps1
#
# Installs the CUDA 12 libraries required for faster-whisper GPU acceleration.
# (ASCII-only to avoid PowerShell file-encoding issues.)

$ErrorActionPreference = "Continue"

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " W-Sub CUDA reinstall" -ForegroundColor Cyan
Write-Host " Installs CUDA 12 libraries for faster-whisper GPU acceleration." -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " [WARNING] This removes existing PyTorch / CTranslate2 / faster-whisper" -ForegroundColor Yellow
Write-Host "           and reinstalls CUDA 12.1 compatible versions." -ForegroundColor Yellow
Write-Host ""
Read-Host "Press Enter to continue (Ctrl+C to cancel)"

# Move to the script folder
Set-Location -Path $PSScriptRoot

# -- Activate venv --------------------------------------------------
Write-Host ""
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
    Write-Host "[OK] venv activated: .venv" -ForegroundColor Green
} else {
    Write-Host "[WARN] .venv not found. Installing into current Python env." -ForegroundColor Yellow
    Write-Host "       (Recommended: python -m venv .venv, then retry)" -ForegroundColor Yellow
}

# -- Check Python ---------------------------------------------------
Write-Host ""
try {
    $pyver = (python --version) 2>&1
    Write-Host "[OK] $pyver" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found. https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# -- Check GPU ------------------------------------------------------
Write-Host ""
Write-Host "[CHECK] Detecting NVIDIA GPU..." -ForegroundColor Cyan
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($null -eq $nvidiaSmi) {
    Write-Host "[ERROR] nvidia-smi not found. Install the GPU driver:" -ForegroundColor Red
    Write-Host "        https://www.nvidia.com/drivers" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
Write-Host "[OK] NVIDIA GPU detected" -ForegroundColor Green

# -- Remove existing packages ---------------------------------------
Write-Host ""
Write-Host "[REMOVE] Uninstalling existing PyTorch / CUDA packages..." -ForegroundColor Cyan
python -m pip uninstall -y torch torchvision torchaudio 2>&1 | Out-Null
python -m pip uninstall -y nvidia-cublas-cu11 nvidia-cuda-runtime-cu11 2>&1 | Out-Null
python -m pip uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 2>&1 | Out-Null
python -m pip uninstall -y ctranslate2 faster-whisper 2>&1 | Out-Null
Write-Host "[OK] Removed" -ForegroundColor Green

# -- Install PyTorch CUDA 12.1 --------------------------------------
Write-Host ""
Write-Host "[INSTALL] PyTorch 2.x + CUDA 12.1 (about 2-4GB, may take a while)..." -ForegroundColor Cyan
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyTorch install failed. Check your network connection." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] PyTorch CUDA 12.1 installed" -ForegroundColor Green

# -- Reinstall faster-whisper ---------------------------------------
Write-Host ""
Write-Host "[INSTALL] faster-whisper (latest)..." -ForegroundColor Cyan
python -m pip install faster-whisper --upgrade
Write-Host "[OK] faster-whisper installed" -ForegroundColor Green

# -- Install CUDA 12 DLL wheels -------------------------------------
Write-Host ""
Write-Host "[INSTALL] CUDA 12 runtime DLLs (cublas, cudnn)..." -ForegroundColor Cyan
python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] nvidia DLL wheels failed. May still work if CUDA Toolkit 12.x is installed." -ForegroundColor Yellow
} else {
    Write-Host "[OK] CUDA 12 DLLs installed" -ForegroundColor Green
}

# -- Verify ---------------------------------------------------------
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " Verification" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
python (Join-Path $PSScriptRoot "check_cuda.py")

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host " Done. Restart W-Sub:  python main.py" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
