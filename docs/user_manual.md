# User Manual

## Start the application
Windows: double-click `run.bat`. Linux: `./run.sh`. Then open http://127.0.0.1:5000.
The first transcription downloads AI models (several hundred MB to about 1.2 GB) and can take several minutes.

## Provide audio
- **Upload:** click *Upload audio* or drag a file into the dashed area. Allowed: WAV, MP3, M4A, FLAC, OGG, WEBM, up to 100 MB.
- **Record:** click *Record audio*, allow the microphone, speak, then click *Stop recording*.
- **Clear audio** removes the selected file.
Use the preview player to check the audio.

## Choose options
- **Speech recognition model:** *base* is faster, *small* is more accurate.
- **Summary length:** short, medium or detailed.
- **Language:** automatic detection or a specific language.

## Process
Click **Transcribe & Summarize**. A progress bar shows upload progress and then a "working" state with elapsed time. Do not close the page until it finishes.

## Read the results
- A preview appears on the home page; click **Open full results** for the full dashboard.
- **Transcript** is editable. Fix mistakes, then press **Regenerate summary** to update summary, key points, decisions and action items.
- **Action items** table: No., Task, Responsible Person, Deadline. "Not specified." means the transcript did not say.
- Labels show what is AI-generated (summary) and what is extracted from the transcript.

## Export
Download the transcript, the summary or the complete report as TXT. *Download transcript* next to the editor saves your edited text. Server-side reports are deleted automatically after 24 hours.

## Common messages
| Message | Meaning |
|---|---|
| Unsupported audio format | File type is not in the allowed list |
| File is empty / corrupted | Re-export or re-record the audio |
| No speech was detected | The audio is silent or unintelligible |
| FFmpeg is not installed | Install FFmpeg (see README) |
| Could not load the model | Check internet for first download, disk space, memory |
