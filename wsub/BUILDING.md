# W-Sub EXE 빌드 가이드

## 사전 요구사항

| 항목 | 최소 버전 | 설치 방법 |
|---|---|---|
| Python | 3.11+ | https://python.org |
| FFmpeg | 6.0+ | `winget install ffmpeg` |
| CUDA (선택) | 11.8+ | NVIDIA 드라이버 설치 |
| 디스크 공간 | 10 GB+ | 빌드 결과 포함 |

---

## 빠른 시작 (Windows)

### 1단계: 환경 설정

```bat
setup_env.bat
```

- 가상환경(`.venv`) 자동 생성
- CUDA GPU 감지 후 적합한 PyTorch 버전 자동 설치
- 모든 의존 패키지 설치

### 2단계: EXE 빌드

```bat
.venv\Scripts\activate
build.bat
```

빌드 완료 후 `dist\W-Sub\W-Sub.exe` 실행

---

## 빌드 방식 선택

### 방식 1: 폴더 배포 (onedir) — **권장**

```bat
build.bat
```

```
dist\
└── W-Sub\
    ├── W-Sub.exe         ← 실행 파일
    ├── ffmpeg.exe        ← 자동 포함
    ├── ffprobe.exe
    ├── _internal\        ← 의존 라이브러리
    └── ...
```

- 시작 속도 빠름 (압축 해제 없음)
- 배포: `dist\W-Sub\` 폴더 전체를 ZIP으로 압축

### 방식 2: 단일 EXE (onefile)

```bat
build.bat onefile
```

```
dist\
└── W-Sub.exe             ← 단일 실행 파일 (~2~5 GB)
```

- 파일 하나로 배포 편리
- 첫 실행 시 30~60초 소요 (temp 압축 해제)
- 이후 실행은 캐시 사용으로 빠름

---

## 수동 빌드

```bat
:: 환경 활성화
.venv\Scripts\activate

:: 이전 빌드 정리
rmdir /s /q dist build

:: onedir 빌드
pyinstaller build.spec --noconfirm --clean

:: 또는 onefile 빌드
pyinstaller build_onefile.spec --noconfirm --clean
```

---

## 아이콘 추가

`resources\icons\wsub.ico` 파일을 생성하면 빌드 시 자동으로 EXE 아이콘이 적용됩니다.

ICO 파일 생성 도구: https://convertico.com

---

## 빌드 트러블슈팅

### `ModuleNotFoundError: No module named 'xxx'`

`build.spec`의 `hidden_imports` 리스트에 해당 모듈을 추가하세요.

### ctranslate2 DLL 오류

`hooks\hook-ctranslate2.py`가 올바른지 확인하고, ctranslate2를 재설치하세요:
```bat
pip install --force-reinstall ctranslate2
```

### PySide6 플랫폼 플러그인 오류 (`platforms\qwindows.dll`)

`build.spec`의 `qt_datas` 섹션이 포함되어 있는지 확인하세요.

### Windows Defender 오탐

빌드 결과 EXE를 Windows Defender 예외 목록에 추가하거나,
공식 코드 서명 인증서로 서명하세요.

### CUDA 관련 오류 (EXE 실행 시)

CUDA 버전 torch를 사용했다면 대상 PC에도 동일한 CUDA 드라이버가 필요합니다.
CPU 전용 배포가 필요하면 `setup_env.bat`에서 CPU 버전 torch를 설치하고 재빌드하세요.

---

## 배포 패키지 구성 (onedir 기준)

```
W-Sub_v1.0.0_win64.zip
└── W-Sub\
    ├── W-Sub.exe
    ├── ffmpeg.exe
    ├── ffprobe.exe
    └── _internal\
```

> 모델 파일(.bin)은 포함하지 않습니다.
> 사용자가 프로그램 내 [모델 관리]에서 직접 다운로드합니다.
