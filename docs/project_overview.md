# Project Overview

**Title:** Speech Recognition and Meeting Summarization Using AI
**Student:** Atharv Shetty (Reg. No. 8080110), GTTC Belagavi, Dept. of AI & ML

## Purpose
Convert meeting audio into a transcript and an actionable report (summary, key points, decisions, action items) using only open-source AI models that run locally.

## Main modules
| Module | File | Responsibility |
|---|---|---|
| Web app / config | `app.py`, `config.py` | Flask factory, error handlers, `.env` configuration |
| Routes | `backend/routes.py` | Pages, REST API, secure download |
| Services | `backend/services.py` | Workflow: validate -> convert -> chunk -> transcribe -> summarise -> save report |
| Validators | `backend/validators.py` | Input validation with proper HTTP status codes |
| Speech model | `models/speech_model.py` | Lazy Whisper loading, chunk transcription, merging |
| Summariser | `models/summarization_model.py` | Lazy Transformers model, chunked summarisation |
| Audio utils | `utils/audio_processing.py` | `validate_audio`, `convert_audio`, `get_audio_duration`, `normalize_audio`, `split_audio_into_chunks` |
| Text utils | `utils/text_utils.py` | Cleaning, chunking, extraction of key points/decisions/action items, TXT reports |
| File utils | `utils/file_utils.py` | Safe names, temp folders, cleanup, traversal-proof export paths |

## Models
- **Whisper** `base` (default) or `small`: speech to text, language detection.
- **sshleifer/distilbart-cnn-12-6** (default, configurable via `SUMMARIZER_MODEL`): abstractive summaries.

## Grounding of results
- *Meeting Summary* = AI-generated text (labelled as such).
- *Key points, decisions, action items* = sentences taken verbatim from the transcript by rule-based extraction. Owner or deadline absent -> "Not specified."; no tasks -> "No specific action items identified."

## Viva quick answers
- **Why Whisper?** Open-source, multilingual, robust to noise, runs on CPU.
- **Why chunk audio/text?** Memory limits and model input limits (BART accepts about 1024 tokens).
- **Why rule-based action items?** A generative model could invent tasks or names; extraction guarantees every item exists in the transcript.
- **Why 16 kHz mono WAV?** That is the format Whisper's feature extractor expects.
