@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ================================================
echo  W-Sub 빌드 스크립트
echo ================================================
echo.

:: ── 모드 선택 ──────────────────────────────────────
set BUILD_MODE=onedir
if "%1"=="onefile" set BUILD_MODE=onefile
if "%1"=="--onefile" set BUILD_MODE=onefile

if "%BUILD_MODE%"=="onefile" (
    echo [모드] 단일 EXE ^(onefile^) — 파일 크기 크고 시작 느림
    set SPEC_FILE=build_onefile.spec
) else (
    echo [모드] 폴더 배포 ^(onedir^) — 권장, 빠른 시작
    set SPEC_FILE=build.spec
)
echo.

:: ── Python 확인 ────────────────────────────────────
python --version > nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않거나 PATH에 없습니다.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo [확인] %%v

:: ── 가상환경 확인 ──────────────────────────────────
if defined VIRTUAL_ENV (
    echo [확인] 가상환경: %VIRTUAL_ENV%
) else (
    echo [경고] 가상환경이 활성화되지 않았습니다.
    echo        .venv\Scripts\activate 후 다시 실행하세요.
    echo        계속하려면 아무 키나 누르세요...
    pause > nul
)
echo.

:: ── PyInstaller 확인 및 설치 ───────────────────────
python -c "import PyInstaller" > nul 2>&1
if errorlevel 1 (
    echo [설치] PyInstaller 설치 중...
    pip install pyinstaller
    if errorlevel 1 ( echo [오류] PyInstaller 설치 실패 & pause & exit /b 1 )
)
for /f "tokens=*" %%v in ('pyinstaller --version') do echo [확인] PyInstaller %%v

:: ── FFmpeg 확인 ────────────────────────────────────
where ffmpeg > nul 2>&1
if errorlevel 1 (
    echo [경고] FFmpeg가 PATH에 없습니다.
    echo        빌드는 계속되지만 EXE 실행 시 FFmpeg가 별도로 필요합니다.
    echo        https://ffmpeg.org 또는 winget install ffmpeg
) else (
    for /f "tokens=*" %%f in ('where ffmpeg') do echo [확인] FFmpeg: %%f
)
echo.

:: ── 이전 빌드 정리 ─────────────────────────────────
if exist "dist\W-Sub" (
    echo [정리] 이전 빌드 폴더 삭제 중...
    rmdir /s /q "dist\W-Sub"
)
if exist "build" (
    echo [정리] build 폴더 삭제 중...
    rmdir /s /q "build"
)
echo.

:: ── 빌드 실행 ──────────────────────────────────────
echo [빌드] %SPEC_FILE% 으로 빌드 시작...
echo.
pyinstaller "%SPEC_FILE%" --noconfirm --clean

if errorlevel 1 (
    echo.
    echo [실패] 빌드 중 오류가 발생했습니다.
    echo        위 오류 메시지를 확인하세요.
    pause & exit /b 1
)

:: ── 빌드 후처리 ────────────────────────────────────
echo.
if "%BUILD_MODE%"=="onedir" (
    echo [완료] dist\W-Sub\W-Sub.exe 생성됨
    echo.

    :: ffmpeg가 PATH에 있으면 dist 폴더에도 복사
    where ffmpeg > nul 2>&1
    if not errorlevel 1 (
        echo [복사] FFmpeg 바이너리를 dist\W-Sub\ 에 복사 중...
        for /f "tokens=*" %%f in ('where ffmpeg') do copy "%%f" "dist\W-Sub\" > nul
        for /f "tokens=*" %%f in ('where ffprobe 2^>nul') do copy "%%f" "dist\W-Sub\" > nul
        echo [완료] FFmpeg 복사 완료
    )

    echo.
    echo ================================================
    echo  빌드 성공!
    echo  실행 파일: dist\W-Sub\W-Sub.exe
    echo  배포 시:  dist\W-Sub\ 폴더 전체를 압축하여 배포
    echo ================================================
) else (
    echo ================================================
    echo  빌드 성공!
    echo  실행 파일: dist\W-Sub.exe
    echo ================================================
)
echo.
pause
