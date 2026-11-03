# System Architecture

## Layers
1. **Presentation:** Bootstrap 5 pages (`templates/`), `static/js/main.js` handles drag-and-drop, `MediaRecorder` recording, upload progress, results rendering, transcript editing.
2. **API:** Flask blueprint (`backend/routes.py`) returning JSON; `api_errors` converts exceptions to safe messages (no stack traces or server paths).
3. **Services:** `backend/services.py` orchestrates the pipeline and always removes temporary files in a `finally` block.
4. **AI models:** Whisper and Transformers, lazily loaded and cached in module-level state protected by locks.
5. **Storage:** Local `exports/` folder (TXT + JSON per report). Files older than `EXPORT_RETENTION_HOURS` are deleted on the next processing request.

## Processing sequence
```
Upload -> validators (extension) -> save to temp dir -> validate_audio (size, FFprobe)
 -> convert_audio (FFmpeg: 16 kHz, mono, PCM16 WAV) -> get_audio_duration
 -> split_audio_into_chunks (default 300 s, cut at quietest 0.1 s window near boundary)
 -> for each chunk: normalize_audio -> Whisper.transcribe (language detected on first chunk, reused)
 -> merge text -> summarise (chunk -> summarise -> combine -> condense)
 -> extract key points / decisions / action items from transcript
 -> write exports -> respond with report JSON -> temp dir deleted
```

## Security measures
- `secure_filename` plus random internal names; uploaded paths never shown to users
- Extension allow-list, size limit (`MAX_CONTENT_LENGTH`), FFprobe content check, empty/corrupt file handling
- `/download/<filename>` accepts only `^[0-9a-f]{32}_(transcript|summary|report).txt$` and resolves inside `exports/` (no traversal); JSON reports are not downloadable
- Jinja auto-escaping and `textContent` DOM updates (no HTML injection)
- No hard-coded secrets; configuration through `.env`
- Generic error messages for unexpected failures; details only in server logs

## Performance choices
Lazy model loading, one Whisper model kept in memory, chunked audio and text, CPU-friendly models, streaming file handling with `wave` (no whole-file loads for splitting).
