@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ================================================
echo  W-Sub 개발 환경 설정
echo ================================================
echo.

:: ── Python 버전 확인 ───────────────────────────────
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo        https://www.python.org/downloads/ 에서 Python 3.11+ 설치
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version') do set PY_VER=%%v
echo [확인] Python %PY_VER%

:: Python 3.11+ 확인
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    if %%a LSS 3 ( echo [오류] Python 3.11+ 필요 & pause & exit /b 1 )
    if %%a EQU 3 if %%b LSS 11 ( echo [오류] Python 3.11+ 필요 & pause & exit /b 1 )
)

:: ── 가상환경 생성 ──────────────────────────────────
if not exist ".venv" (
    echo [생성] 가상환경 생성 중...
    python -m venv .venv
    if errorlevel 1 ( echo [오류] 가상환경 생성 실패 & pause & exit /b 1 )
    echo [완료] .venv 생성됨
) else (
    echo [확인] 가상환경 이미 존재: .venv
)

:: ── 가상환경 활성화 ────────────────────────────────
call .venv\Scripts\activate
if errorlevel 1 ( echo [오류] 가상환경 활성화 실패 & pause & exit /b 1 )
echo [활성화] 가상환경 활성화됨

:: ── pip 업그레이드 ─────────────────────────────────
echo.
echo [업그레이드] pip 업그레이드 중...
python -m pip install --upgrade pip --quiet

:: ── CUDA 여부 확인 ─────────────────────────────────
echo.
echo [확인] GPU/CUDA 환경 감지 중...
set CUDA_AVAILABLE=0
nvidia-smi > nul 2>&1
if not errorlevel 1 (
    set CUDA_AVAILABLE=1
    echo [감지] NVIDIA GPU 확인됨 — CUDA 버전 torch 설치 예정
) else (
    echo [정보] NVIDIA GPU 미감지 — CPU 버전 torch 설치
)

:: ── PyTorch 설치 ───────────────────────────────────
echo.
python -c "import torch" > nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%v in ('python -c "import torch; print(torch.__version__)"') do echo [확인] PyTorch %%v 이미 설치됨
    goto :install_other
)

echo [설치] PyTorch 설치 중 (시간이 걸릴 수 있습니다)...
if "%CUDA_AVAILABLE%"=="1" (
    echo       CUDA 12.1 버전으로 설치합니다.
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
) else (
    echo       CPU 버전으로 설치합니다.
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
)
if errorlevel 1 ( echo [오류] PyTorch 설치 실패 & pause & exit /b 1 )
echo [완료] PyTorch 설치됨

:install_other
:: ── 나머지 패키지 설치 ─────────────────────────────
echo.
echo [설치] 의존 패키지 설치 중...
pip install PySide6 faster-whisper openai-whisper transformers ^
    huggingface-hub ffmpeg-python numpy psutil requests ^
    pyinstaller --quiet
if errorlevel 1 ( echo [오류] 패키지 설치 실패 & pause & exit /b 1 )
echo [완료] 모든 패키지 설치됨

:: ── FFmpeg 확인 ────────────────────────────────────
echo.
where ffmpeg > nul 2>&1
if errorlevel 1 (
    echo [경고] FFmpeg가 PATH에 없습니다.
    echo        아래 명령으로 설치하세요:
    echo        winget install ffmpeg
    echo        또는 https://ffmpeg.org/download.html
) else (
    for /f "tokens=*" %%f in ('where ffmpeg') do echo [확인] FFmpeg: %%f
)

:: ── 완료 ──────────────────────────────────────────
echo.
echo ================================================
echo  환경 설정 완료!
echo.
echo  실행 방법:
echo    .venv\Scripts\activate
echo    python main.py
echo.
echo  EXE 빌드:
echo    build.bat          (폴더 배포 — 권장)
echo    build.bat onefile  (단일 EXE)
echo ================================================
echo.
pause
