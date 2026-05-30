@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ====================================================================
echo  W-Sub CUDA 환경 재설치 스크립트
echo  faster-whisper GPU 가속에 필요한 CUDA 12 라이브러리를 설치합니다.
echo ====================================================================
echo.
echo  [주의] 기존 PyTorch / CTranslate2 / faster-whisper를 제거하고
echo         CUDA 12.1 호환 버전으로 재설치합니다.
echo.
pause

:: ── 가상환경 활성화 ────────────────────────────────────────────
echo.
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] 가상환경 활성화: .venv
) else (
    echo [경고] .venv 가상환경을 찾을 수 없습니다.
    echo        현재 Python 환경에 설치합니다.
    echo        (권장: wsub 폴더에서 python -m venv .venv 실행 후 다시 시도)
    echo.
)

:: ── GPU 확인 ───────────────────────────────────────────────────
echo.
echo [확인] NVIDIA GPU 감지 중...
nvidia-smi > nul 2>&1
if errorlevel 1 (
    echo [오류] NVIDIA GPU 또는 드라이버를 찾을 수 없습니다.
    echo        GPU 드라이버를 먼저 설치하세요: https://www.nvidia.com/drivers
    pause & exit /b 1
)
echo [OK] NVIDIA GPU 확인됨
echo.
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
echo.

:: ── 기존 패키지 제거 ───────────────────────────────────────────
echo [제거] 기존 PyTorch 및 CUDA 관련 패키지 제거 중...
pip uninstall -y torch torchvision torchaudio > nul 2>&1
pip uninstall -y nvidia-cublas-cu11 nvidia-cuda-runtime-cu11 > nul 2>&1
pip uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 > nul 2>&1
pip uninstall -y ctranslate2 faster-whisper > nul 2>&1
echo [OK] 기존 패키지 제거 완료

:: ── PyTorch CUDA 12.1 설치 ────────────────────────────────────
echo.
echo [설치] PyTorch 2.x + CUDA 12.1 설치 중...
echo        (약 2~4GB 다운로드, 시간이 걸릴 수 있습니다)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo.
    echo [오류] PyTorch 설치 실패. 네트워크 연결을 확인하세요.
    pause & exit /b 1
)
echo [OK] PyTorch CUDA 12.1 설치 완료

:: ── faster-whisper 재설치 ─────────────────────────────────────
echo.
echo [설치] faster-whisper 최신 버전 설치 중...
pip install faster-whisper --upgrade
if errorlevel 1 (
    echo [오류] faster-whisper 설치 실패
    pause & exit /b 1
)
echo [OK] faster-whisper 설치 완료

:: ── CUDA 12 DLL 휠 설치 ───────────────────────────────────────
echo.
echo [설치] CUDA 12 런타임 DLL (cublas, cudnn) 설치 중...
echo        (cublas64_12.dll / cudnn_ops_infer64_8.dll 등 포함)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
if errorlevel 1 (
    echo [경고] nvidia DLL 휠 설치 실패.
    echo        시스템에 CUDA Toolkit 12.x가 설치된 경우 동작할 수 있습니다.
    echo        그렇지 않으면 https://developer.nvidia.com/cuda-downloads 에서 설치하세요.
) else (
    echo [OK] CUDA 12 DLL 설치 완료
)

:: ── 설치 결과 확인 ─────────────────────────────────────────────
echo.
echo ====================================================================
echo  설치 결과 확인
echo ====================================================================
echo.
python "%~dp0check_cuda.py"

echo.
echo ====================================================================
echo  완료! W-Sub를 다시 실행하세요.
echo    python main.py
echo ====================================================================
echo.
pause
