# W-Sub

Whisper 계열 오픈소스 음성 인식 모델을 활용하여 동영상·음성 파일에서 자막(SRT/TXT)을 추출하는 Windows용 GUI 프로그램입니다.

---

## 주요 기능

- **다양한 모델 지원**: Whisper Tiny ~ Large v3, Kotoba Whisper, Anime Whisper
- **다중 엔진**: faster-whisper (기본), openai-whisper, HuggingFace Transformers
- **GPU 가속**: CUDA 자동 감지, CPU 폴백
- **배치 처리**: 드래그앤드롭으로 여러 파일 일괄 처리
- **오디오 전처리**: FFmpeg 기반 노이즈 감소, 음량 정규화 등
- **SRT / TXT 출력**: 자동 중복 자막 제거 포함
- **다크 모드 UI**: PySide6(Qt6) 기반 현대적 인터페이스

---

## 지원 포맷

| 구분 | 형식 |
|---|---|
| 영상 | mp4, mkv, avi, mov, wmv, asf, mpg, mpeg, flv, webm, ts, m2ts |
| 음성 | mp3, wav, aac, flac, ogg, opus, m4a, wma |

---

## 설치

### 1. Python 환경 설정

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. FFmpeg 설치

[https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) 에서 다운로드 후 PATH에 추가하세요.

Windows 간편 설치:
```powershell
winget install ffmpeg
```

### 3. CUDA (선택사항)

CUDA를 사용하려면 NVIDIA 드라이버와 CUDA Toolkit을 설치하고 `torch`를 CUDA 버전으로 재설치하세요:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 실행

```bash
python main.py
```

시작 시 자동으로 환경 검사(Python 버전, FFmpeg, CUDA, 디스크 공간 등)를 수행합니다.

---

## EXE 빌드 (배포용)

```bash
pip install pyinstaller
pyinstaller build.spec
```

`dist/W-Sub.exe` 파일이 생성됩니다. FFmpeg가 PATH에 있으면 자동으로 EXE에 포함됩니다.

---

## 프로젝트 구조

```
wsub/
├── main.py                    # 진입점
├── requirements.txt
├── build.spec                 # PyInstaller 설정
└── app/
    ├── config/                # 상수, 설정 저장/로드
    ├── core/                  # 비즈니스 로직 (전사, FFmpeg, 모델 관리)
    ├── engines/               # Whisper 엔진 추상화
    ├── models/                # 데이터 모델
    ├── viewmodels/            # MVVM ViewModel
    └── views/                 # PySide6 UI (위젯, 다이얼로그)
```

---

## 설정 파일 위치

`~/.wsub/config.json`

---

## 지원 모델

| 모델 | 크기 | 특징 |
|---|---|---|
| Whisper Tiny | 0.15 GB | 초고속, 낮은 정확도 |
| Whisper Base | 0.29 GB | 빠름 |
| Whisper Small | 0.97 GB | 균형 |
| Whisper Medium | 3.06 GB | 높은 정확도 |
| Whisper Large v3 | 6.17 GB | 최고 정확도 |
| Whisper Large Turbo | 3.09 GB | Large 수준 정확도, 빠른 속도 |
| Kotoba Whisper v2 | 6.17 GB | 일본어 특화 |
| Anime Whisper | 6.17 GB | 애니메이션 음성 특화 |

---

## 라이선스

MIT License
