# W-Sub CUDA 환경 재설치 스크립트 (PowerShell / Windows 11 Terminal)
#
# 실행 방법 (wsub 폴더에서):
#   powershell -ExecutionPolicy Bypass -File .\reinstall_cuda.ps1
# 또는 PowerShell 창에서:
#   .\reinstall_cuda.ps1
#
# faster-whisper GPU 가속에 필요한 CUDA 12 라이브러리를 설치합니다.

$ErrorActionPreference = "Continue"
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 > $null

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " W-Sub CUDA 환경 재설치 스크립트" -ForegroundColor Cyan
Write-Host " faster-whisper GPU 가속에 필요한 CUDA 12 라이브러리를 설치합니다." -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " [주의] 기존 PyTorch / CTranslate2 / faster-whisper를 제거하고" -ForegroundColor Yellow
Write-Host "        CUDA 12.1 호환 버전으로 재설치합니다." -ForegroundColor Yellow
Write-Host ""
Read-Host "계속하려면 Enter 키를 누르세요 (취소: Ctrl+C)"

# 스크립트가 위치한 폴더로 이동
Set-Location -Path $PSScriptRoot

# ── 가상환경 활성화 ────────────────────────────────────────────
Write-Host ""
$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
    Write-Host "[OK] 가상환경 활성화: .venv" -ForegroundColor Green
} else {
    Write-Host "[경고] .venv 가상환경을 찾을 수 없습니다. 현재 Python 환경에 설치합니다." -ForegroundColor Yellow
    Write-Host "       (권장: python -m venv .venv 실행 후 다시 시도)" -ForegroundColor Yellow
}

# ── Python 확인 ────────────────────────────────────────────────
Write-Host ""
try {
    $pyver = (python --version) 2>&1
    Write-Host "[OK] $pyver" -ForegroundColor Green
} catch {
    Write-Host "[오류] Python을 찾을 수 없습니다. https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Enter 키를 눌러 종료"
    exit 1
}

# ── GPU 확인 ───────────────────────────────────────────────────
Write-Host ""
Write-Host "[확인] NVIDIA GPU 감지 중..." -ForegroundColor Cyan
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($null -eq $nvidiaSmi) {
    Write-Host "[오류] nvidia-smi를 찾을 수 없습니다. GPU 드라이버를 설치하세요." -ForegroundColor Red
    Write-Host "       https://www.nvidia.com/drivers" -ForegroundColor Red
    Read-Host "Enter 키를 눌러 종료"
    exit 1
}
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
Write-Host "[OK] NVIDIA GPU 확인됨" -ForegroundColor Green

# ── 기존 패키지 제거 ───────────────────────────────────────────
Write-Host ""
Write-Host "[제거] 기존 PyTorch 및 CUDA 관련 패키지 제거 중..." -ForegroundColor Cyan
python -m pip uninstall -y torch torchvision torchaudio 2>&1 | Out-Null
python -m pip uninstall -y nvidia-cublas-cu11 nvidia-cuda-runtime-cu11 2>&1 | Out-Null
python -m pip uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 2>&1 | Out-Null
python -m pip uninstall -y ctranslate2 faster-whisper 2>&1 | Out-Null
Write-Host "[OK] 기존 패키지 제거 완료" -ForegroundColor Green

# ── PyTorch CUDA 12.1 설치 ────────────────────────────────────
Write-Host ""
Write-Host "[설치] PyTorch 2.x + CUDA 12.1 설치 중... (약 2~4GB, 시간이 걸립니다)" -ForegroundColor Cyan
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if ($LASTEXITCODE -ne 0) {
    Write-Host "[오류] PyTorch 설치 실패. 네트워크 연결을 확인하세요." -ForegroundColor Red
    Read-Host "Enter 키를 눌러 종료"
    exit 1
}
Write-Host "[OK] PyTorch CUDA 12.1 설치 완료" -ForegroundColor Green

# ── faster-whisper 재설치 ─────────────────────────────────────
Write-Host ""
Write-Host "[설치] faster-whisper 최신 버전 설치 중..." -ForegroundColor Cyan
python -m pip install faster-whisper --upgrade
Write-Host "[OK] faster-whisper 설치 완료" -ForegroundColor Green

# ── CUDA 12 DLL 휠 설치 ───────────────────────────────────────
Write-Host ""
Write-Host "[설치] CUDA 12 런타임 DLL (cublas, cudnn) 설치 중..." -ForegroundColor Cyan
python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
if ($LASTEXITCODE -ne 0) {
    Write-Host "[경고] nvidia DLL 휠 설치 실패. CUDA Toolkit 12.x가 설치되어 있으면 동작할 수 있습니다." -ForegroundColor Yellow
} else {
    Write-Host "[OK] CUDA 12 DLL 설치 완료" -ForegroundColor Green
}

# ── 설치 결과 확인 ─────────────────────────────────────────────
Write-Host ""
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host " 설치 결과 확인" -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""
python (Join-Path $PSScriptRoot "check_cuda.py")

Write-Host ""
Write-Host "====================================================================" -ForegroundColor Green
Write-Host " 완료! W-Sub를 다시 실행하세요:  python main.py" -ForegroundColor Green
Write-Host "====================================================================" -ForegroundColor Green
Write-Host ""
Read-Host "Enter 키를 눌러 종료"
