# Speech Recognition and Meeting Summarization Using AI

## 1. Project title
**Speech Recognition and Meeting Summarization Using AI** (web application name: *AI Meeting Assistant*)

## 2. Student details
| | |
|---|---|
| Student name | ATHARV SHETTY |
| Register number | 8080110 |
| College | GTTC Belagavi |
| Department | Artificial Intelligence and Machine Learning (5th semester Diploma) |

## 3. Project overview
AI Meeting Assistant turns a meeting recording into a written transcript and a concise report containing a summary, key discussion points, decisions and action items. Audio can be uploaded or recorded in the browser. Speech recognition uses **OpenAI Whisper** and summarisation uses a **Hugging Face Transformers** model. Both are open-source and run locally, so no paid API key is required.

## 4. Problem statement
Meetings contain decisions and tasks that are easily forgotten. Writing minutes by hand is slow and error-prone. This project automates the process: audio to text, text to a short summary, and extraction of action items, while keeping the extracted facts grounded in what was actually said.

## 5. Objectives
1. Convert meeting audio to text with an AI speech recognition model.
2. Generate a concise summary of long transcripts using a lightweight model that runs on a CPU.
3. Extract decisions and action items (task, responsible person, deadline) without inventing information.
4. Let users review and edit the transcript and regenerate the summary.
5. Export the transcript, summary and full report as TXT files.
6. Provide a clean, responsive, secure web interface.

## 6. Features
- Upload (drag-and-drop) or record audio in the browser; audio preview player
- Formats: WAV, MP3, M4A, FLAC, OGG, WEBM (anything FFmpeg can decode); 100 MB default limit
- Whisper `base` or `small`, automatic language detection or manual language choice, CPU by default and GPU when available
- Long audio is split into chunks at quiet moments, transcribed, and merged
- Long transcripts are chunked for summarisation; short / medium / detailed summary lengths
- Key points, decisions and action items are **extracted from transcript sentences** (never invented). Missing owners/deadlines show "Not specified."; no tasks shows "No specific action items identified."
- Results page with editable transcript, copy button, action-items table, regenerate summary, TXT downloads, "Process Another Meeting"
- Secure file handling, input validation, JSON API, logging, automatic cleanup of temporary files and old reports

## 7. Technology stack
| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons |
| Backend | Python, Flask, REST API, Werkzeug, python-dotenv |
| Speech recognition | OpenAI Whisper (open-source), PyTorch |
| Summarisation | Hugging Face Transformers (`sshleifer/distilbart-cnn-12-6` by default) |
| Audio | FFmpeg, librosa, soundfile, pydub, NumPy |

## 8. System architecture
```
Browser (upload / record)
        |  multipart POST /api/process
        v
Flask routes (backend/routes.py)  -->  validators.py
        v
services.py  -->  utils/audio_processing.py   validate -> convert (16 kHz mono WAV) -> split into chunks
        |
        +--> models/speech_model.py           Whisper (lazy-loaded, cached)  -> transcript
        +--> models/summarization_model.py    Transformers (lazy-loaded)     -> summary
        +--> utils/text_utils.py              key points, decisions, action items (from transcript)
        v
exports/<id>_*.txt + <id>.json  -->  /result/<id>  and  /download/<file>
```
More detail: `docs/system_architecture.md`.

## 9. Project folder structure
```
Speech-Recognition-Meeting-Summarization/
├── app.py  config.py  requirements.txt  README.md  .env.example  .gitignore  run.bat  run.sh
├── backend/    __init__.py  routes.py  services.py  validators.py
├── models/     __init__.py  speech_model.py  summarization_model.py
├── utils/      __init__.py  audio_processing.py  file_utils.py  text_utils.py
├── templates/  base.html  index.html  result.html  about.html  error.html
├── static/     css/style.css  js/main.js  images/
├── uploads/    (temporary working files, auto-deleted)
├── exports/    (generated reports, auto-deleted after 24 h)
├── tests/      test_audio_processing.py  test_text_utils.py  test_routes.py
└── docs/       project_overview.md  system_architecture.md  user_manual.md
```

## 10. Installation instructions

### Python version (important)
The AI libraries (PyTorch, Whisper and their dependencies) release support for new Python versions with a delay. **This project is configured for Python 3.12 (3.11 also works).** Compatibility with Python 3.14 was **not verified** while preparing this project (the build environment had no internet access to check package wheels), so it is not claimed. Python 3.12 can be installed side by side with 3.14; your existing Python is not affected.

Windows 11 (PowerShell):
```powershell
winget install Python.Python.3.12
py -0p            # lists installed versions; confirm 3.12 is present
```
Linux (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```
(If your distribution has no `python3.12` package, use 3.11 or install 3.12 from python.org / deadsnakes.)

## 11. FFmpeg installation
FFmpeg is required to decode audio.

Windows 11 (PowerShell):
```powershell
winget install Gyan.FFmpeg
# close and reopen PowerShell, then verify:
ffmpeg -version
ffprobe -version
```
Linux:
```bash
sudo apt install ffmpeg
ffmpeg -version
```
If FFmpeg is installed but not on PATH, set `FFMPEG_BINARY` and `FFPROBE_BINARY` in `.env`.

## 12. Virtual environment setup
Windows PowerShell (inside the project folder):
```powershell
cd path\to\Speech-Recognition-Meeting-Summarization
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.

Linux:
```bash
cd Speech-Recognition-Meeting-Summarization
python3.12 -m venv .venv
source .venv/bin/activate
```

## 13. Dependency installation
Windows PowerShell (venv active):
```powershell
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
copy .env.example .env
```
Linux:
```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
cp .env.example .env
```
This downloads several hundred MB (PyTorch). The default Windows PyTorch wheel runs on the CPU. For an NVIDIA GPU, install the CUDA build from https://pytorch.org/get-started/locally/ and set `DEVICE=auto` (or `cuda`) in `.env`.

## 14. How to run the application
Easiest option:
- Windows: double-click `run.bat` (creates the venv, installs dependencies on first run, starts the server)
- Linux: `./run.sh`

Manual:
```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```
```bash
source .venv/bin/activate && python app.py
```
Open **http://127.0.0.1:5000**.

> **First run:** the first transcription downloads the Whisper model (base ≈ 140 MB, small ≈ 460 MB) and the first summary downloads the summarisation model (≈ 1.2 GB). This may take several minutes and needs internet. Later runs use the cached models.

## 15. How to use the application
1. Open the home page.
2. Upload or drag an audio file, **or** press *Record audio*, speak, then *Stop recording* (allow microphone access; works on `localhost`).
3. Check the preview, then pick the Whisper model, summary length and language (or leave "Automatic detection").
4. Press **Transcribe & Summarize** and wait. Long recordings take time on a CPU; real-time transcription is not supported.
5. Review the result. On the full results page you can edit the transcript, copy it, regenerate the summary and download TXT files.
6. Press **Process Another Meeting** to start again.

## 16. API documentation
All API responses are JSON. Errors look like `{"success": false, "error": "message"}`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Home page |
| GET | `/about` | About page |
| GET | `/result/<report_id>` | Results page for a processed meeting |
| POST | `/api/transcribe` | multipart: `audio` (file), optional `whisper_model` (`base`/`small`), `language` (`auto`, `en`, ...). Returns transcript, duration, language |
| POST | `/api/summarize` | JSON: `transcript`, optional `summary_length` (`short`/`medium`/`detailed`), optional `report_id` (updates a stored report). Returns summary, key points, decisions, action items |
| POST | `/api/process` | multipart (same fields as transcribe + `summary_length`). Full workflow; returns `report`, `result_url`, `downloads` |
| GET | `/health` | Application status (FFmpeg, installed packages, loaded models) |
| GET | `/download/<filename>` | Download a generated TXT report (`<id>_transcript.txt`, `<id>_summary.txt`, `<id>_report.txt`) |

Status codes: `200` OK, `400` invalid input, `404` not found, `413` file too large, `415` unsupported audio type, `422` empty/corrupted audio or empty transcript or no speech, `500` unexpected error, `503` FFmpeg or AI model unavailable.

Example (PowerShell, using curl.exe):
```powershell
curl.exe -X POST -F "audio=@meeting.mp3" -F "summary_length=medium" http://127.0.0.1:5000/api/process
curl.exe -X POST -H "Content-Type: application/json" -d "{\"transcript\":\"John will send the report by Friday. ...\"}" http://127.0.0.1:5000/api/summarize
```

## 17. Testing instructions
The tests use only the standard `unittest` module and mocked model inference, so no AI models are downloaded. Tests that need FFmpeg are skipped automatically if it is missing.

Windows PowerShell (venv active):
```powershell
python -m unittest discover -s tests -t . -v
```
Linux:
```bash
python -m unittest discover -s tests -t . -v
```
(`pytest` also works if you install it: `pip install pytest` then `pytest -v`.)

## 18. Troubleshooting
| Problem | Solution |
|---|---|
| `ffmpeg`/`ffprobe` not found, HTTP 503 | Install FFmpeg (section 11), reopen the terminal, or set `FFMPEG_BINARY`/`FFPROBE_BINARY` in `.env`. |
| `pip install` fails on Python 3.14 | Use Python 3.12 (section 10). |
| `openai-whisper` build error (`pkg_resources`, setuptools) | Run `python -m pip install --upgrade pip setuptools wheel` first, then install requirements again. |
| "Could not load the Whisper model" | Check internet (first download), free disk space and RAM; try the `base` model. |
| Very slow processing | Use `base`, shorter audio, or a GPU build of PyTorch. CPU processing is much slower than real time for long files. |
| Microphone does not work | Allow microphone permission; open the app via `http://127.0.0.1:5000` or `localhost`; use Chrome/Edge/Firefox. |
| Page looks unstyled | Bootstrap loads from a CDN, so the browser needs internet access. |
| `Activate.ps1` blocked | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port already in use | Change `PORT` in `.env`. |
| Nothing detected / "Thank you" only | Whisper can output filler text for silent or very noisy audio; use clearer audio. |

## 19. Limitations
- Accuracy depends on audio quality, accents, overlapping speakers and background noise. There is no speaker identification (diarisation).
- The summary is generated by an AI model and can omit or rephrase details; always compare with the transcript.
- Decisions and action items are found with keyword/pattern rules, so they can miss items phrased unusually or flag a sentence that is not really a task. Responsible person detection relies on names being capitalised in the transcript.
- The summarisation model and extraction rules are designed for English transcripts.
- Processing on a CPU is slower than real time for long recordings. Real-time transcription is not provided.
- Reports are stored on the local machine for 24 hours; the app has no user accounts and is intended for local/demo use (run it behind a production server and HTTPS before any public deployment).

## 20. Future enhancements
Speaker diarisation, multilingual summarisation, PDF/DOCX export, live transcription, background job queue with true progress reporting, user accounts, and fine-tuned meeting-specific models.

## 21. Conclusion
The project demonstrates a complete AI pipeline: audio engineering with FFmpeg, speech recognition with Whisper, abstractive summarisation with Transformers, and transcript-grounded extraction of decisions and action items, delivered through a secure Flask web application with automated tests and documentation.
#   A I - M e e t i n g - A s s i s t a n t  
 