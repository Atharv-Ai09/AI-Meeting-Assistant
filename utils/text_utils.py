"""Text cleaning, chunking and transcript-grounded extraction helpers.

Key points, decisions and action items are *extracted* from sentences that
really appear in the transcript. Nothing is invented: when a responsible
person or deadline is not stated, "Not specified." is used.
"""
import re
from collections import Counter

NO_ACTION_ITEMS = "No specific action items identified."
NO_DECISIONS = "No explicit decisions identified."
NO_KEY_POINTS = "No key discussion points could be extracted."
NOT_SPECIFIED = "Not specified."
MAX_TRANSCRIPT_CHARS = 300_000

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACE_RE = re.compile(r"[ \t\u00a0]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u2026\u0964])\s+|\n+")

STOPWORDS = frozenset(
    """a about above after again all also am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having he her here hers him his how i if in into is it its just let like me more most my no nor not
    now of off on once only or other our out over own really same she should so some such than that the
    their them then there these they this those through to too under until up us very was we were what
    when where which while who whom why will with would you your yeah okay um uh going get got one""".split()
)


# --------------------------------------------------------------------------- cleaning
def sanitize_text(text):
    """Remove control characters; always returns a string."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return _CONTROL_RE.sub("", text)


def clean_text(text):
    """Normalise whitespace and line breaks."""
    text = sanitize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def count_words(text):
    return len(re.findall(r"\S+", text or ""))


def validate_transcript(text, min_words=5):
    """Return the cleaned transcript or raise ValueError with a user-safe message."""
    if text is None or not isinstance(text, str):
        raise ValueError("The transcript must be provided as text.")
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("The transcript is empty.")
    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        raise ValueError("The transcript is too long to process.")
    if count_words(cleaned) < min_words:
        raise ValueError(f"The transcript is too short to summarise (minimum {min_words} words).")
    return cleaned


# --------------------------------------------------------------------------- chunking
def split_sentences(text, max_words=60):
    """Split text into sentences; very long sentences are cut into pieces."""
    cleaned = clean_text(text)
    if not cleaned:
        return []
    sentences = []
    for part in _SENTENCE_SPLIT_RE.split(cleaned):
        part = (part or "").strip()
        if not part:
            continue
        words = part.split()
        if len(words) <= max_words:
            sentences.append(part)
        else:
            for i in range(0, len(words), max_words):
                sentences.append(" ".join(words[i:i + max_words]))
    return sentences


def chunk_text(text, max_words=350, overlap_sentences=0):
    """Group sentences into chunks of at most `max_words` words."""
    if max_words <= 0:
        raise ValueError("max_words must be positive.")
    sentences = split_sentences(text, max_words=min(60, max_words))
    chunks, current, current_words = [], [], 0
    for sentence in sentences:
        size = len(sentence.split())
        if current and current_words + size > max_words:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences > 0 else []
            current_words = sum(len(s.split()) for s in current)
        current.append(sentence)
        current_words += size
    if current:
        chunks.append(" ".join(current))
    return chunks


def join_transcripts(parts):
    """Combine transcript segments into one text."""
    return clean_text(" ".join(p.strip() for p in parts if p and p.strip()))


# --------------------------------------------------------------------------- extraction
def _tokens(sentence):
    return [w for w in re.findall(r"[a-zA-Z']{3,}", sentence.lower()) if w not in STOPWORDS]


def extract_key_points(text, max_points=5):
    """Pick the most informative transcript sentences (extractive, order preserved)."""
    sentences = split_sentences(text)
    candidates = [(i, s) for i, s in enumerate(sentences) if 6 <= len(s.split()) <= 45]
    if not candidates:
        return []
    frequency = Counter(w for _, s in candidates for w in _tokens(s))
    scored, seen = [], set()
    for index, sentence in candidates:
        tokens = _tokens(sentence)
        key = sentence.lower()
        if not tokens or key in seen:
            continue
        seen.add(key)
        scored.append((sum(frequency[t] for t in tokens) / (len(tokens) ** 0.5), index, sentence))
    limit = min(max_points, max(1, len(scored) // 3))
    top = sorted(scored, key=lambda item: -item[0])[:limit]
    return [s for _, _, s in sorted(top, key=lambda item: item[1])]


_DECISION_RE = re.compile(
    r"\b(?:decided|decision|agreed|agree to|approved|finali[sz]ed|confirmed|resolved to|settled on|"
    r"concluded that|go(?:ing)? ahead with|we(?:'ll| will) go with|going with|let'?s go with|signed off)\b",
    re.I,
)
_DECISION_NEGATIVE_RE = re.compile(
    r"\b(?:need to (?:make a )?decid|to be decided|yet to|haven'?t|hasn'?t|not yet|undecided|unable to|can'?t decide)\b",
    re.I,
)


def extract_decisions(text, max_items=10):
    """Sentences that state a decision or agreement."""
    results, seen = [], set()
    for sentence in split_sentences(text):
        normalized = sentence.replace("\u2019", "'")
        if len(sentence.split()) < 4 or sentence.lower() in seen:
            continue
        if _DECISION_RE.search(normalized) and not _DECISION_NEGATIVE_RE.search(normalized):
            seen.add(sentence.lower())
            results.append(sentence)
        if len(results) >= max_items:
            break
    return results


_VERBS = (
    "send|prepare|review|update|complete|finish|submit|schedule|create|write|share|check|fix|draft|call|email|"
    "contact|organi[sz]e|arrange|follow up|deliver|test|implement|design|set up|book|confirm|ask|collect|compile|"
    "present|upload|publish|plan|investigate|look into|finali[sz]e|circulate|coordinate|prepare|research|"
    "document|report|notify|inform|remind|handle|take care|work on|get back|reach out|provide|build|develop|"
    "make|setup|arrange|assign|approve|sign|order|purchase|pay|gather"
)
_NAME = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)"
_MODAL = r"(?:will|shall|is going to|are going to|needs? to|has to|have to|must|should|to|can|could|would)"

_ACTION_CUE_RE = re.compile(
    r"\b(?:action items?|follow[- ]?ups?|to-?do|assigned to|takes? ownership|responsible for)\b", re.I
)
_ACTION_VERB_RE = re.compile(
    rf"\b(?:will|shall|is going to|are going to|am going to|i'll|we'll|they'll|he'll|she'll|needs? to|"
    rf"has to|have to|must|should|can you|could you|would you|please|let'?s)\s+(?:also\s+)?(?:{_VERBS})\b",
    re.I,
)
_NAME_MODAL_RE = re.compile(rf"\b{_NAME}\s+(?i:(?:also\s+)?{_MODAL}\s+(?:also\s+)?(?:{_VERBS}))\b")
_NAME_QUESTION_RE = re.compile(rf"\b{_NAME},?\s+(?i:can|could|would|will)\s+you\b")
_ASSIGNED_RE = re.compile(
    rf"(?i:assigned to|owned by|handled by|taken care of by|led by|owner|responsible person)\s*[:\-]?\s*{_NAME}"
)
_RESPONSIBLE_RE = re.compile(
    rf"\b{_NAME}\s+(?i:is|are|will be)\s+(?i:responsible for|in charge of|taking|owning|leading|handling)\b"
)
_NOT_NAMES = frozenset(
    "I We You They He She It The This That These Those And But So Then Also Please Let Lets Okay Ok Yes No "
    "Now Next First Second Finally Today Tomorrow Everyone Someone Anyone Team Maybe Thanks Thank".split()
)

_DAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_MONTH = (
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
)
_NUM = r"(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
_DEADLINE_TARGET = (
    r"(?:end of (?:the )?(?:day|week|month|quarter|year)|eod|eow|cob|tomorrow|today|tonight|"
    r"next (?:" + _DAY + r"|week|month|quarter|year)|this (?:" + _DAY + r"|week|month|quarter|year|afternoon|evening)|"
    + _DAY + r"|" + _MONTH + r"\.? \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?|"
    r"\d{1,2}(?:st|nd|rd|th)? (?:of )?" + _MONTH + r"(?:,? \d{4})?|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
)
_DEADLINE_RE = re.compile(
    r"\b(?:(?:by|before|until|due(?: on| by)?|on)\s+(?:the\s+)?" + _DEADLINE_TARGET
    + r"|within " + _NUM + r" (?:hours?|days?|weeks?|months?)"
    + r"|tomorrow|next week|next month|end of (?:the )?(?:day|week|month)|this week)\b",
    re.I,
)


def _find_responsible(sentence):
    for pattern in (_ASSIGNED_RE, _RESPONSIBLE_RE, _NAME_QUESTION_RE, _NAME_MODAL_RE):
        for match in pattern.finditer(sentence):
            name = match.group(1).strip()
            if name.split()[0] not in _NOT_NAMES:
                return name
    return NOT_SPECIFIED


def _find_deadline(sentence):
    match = _DEADLINE_RE.search(sentence)
    return match.group(0).strip() if match else NOT_SPECIFIED


def _is_action_sentence(sentence):
    return bool(
        _ACTION_CUE_RE.search(sentence)
        or _ACTION_VERB_RE.search(sentence)
        or _NAME_MODAL_RE.search(sentence)
        or _NAME_QUESTION_RE.search(sentence)
    )


def extract_action_items(text, max_items=20):
    """Return a list of {"task", "responsible", "deadline"} taken from the transcript."""
    items, seen = [], set()
    for sentence in split_sentences(text):
        normalized = sentence.replace("\u2019", "'")
        if len(sentence.split()) < 4 or sentence.lower() in seen:
            continue
        if _is_action_sentence(normalized):
            seen.add(sentence.lower())
            items.append(
                {
                    "task": sentence.strip(),
                    "responsible": _find_responsible(normalized),
                    "deadline": _find_deadline(normalized),
                }
            )
        if len(items) >= max_items:
            break
    return items


# --------------------------------------------------------------------------- report text
_SOURCE_NOTE = (
    "Note: the Meeting Summary is AI-generated (it may rephrase the transcript). Key points, decisions "
    "and action items are sentences extracted directly from the transcript; nothing is invented."
)


def _numbered(lines, empty_message):
    if not lines:
        return [empty_message]
    return [f"{i}. {line}" for i, line in enumerate(lines, 1)]


def _header(report, title):
    return [
        title,
        "=" * len(title),
        f"File: {report.get('filename', 'N/A')}",
        f"Duration: {report.get('duration_text', 'N/A')}",
        f"Language: {report.get('language', 'N/A')}",
        f"Generated: {report.get('created_at', 'N/A')}",
        "",
    ]


def _action_lines(items):
    if not items:
        return [NO_ACTION_ITEMS]
    return [
        f"{i}. Task: {it.get('task', '')}\n   Responsible: {it.get('responsible', NOT_SPECIFIED)}"
        f" | Deadline: {it.get('deadline', NOT_SPECIFIED)}"
        for i, it in enumerate(items, 1)
    ]


def build_transcript_txt(report):
    lines = _header(report, "MEETING TRANSCRIPT")
    lines.append(report.get("transcript", ""))
    return "\n".join(lines).rstrip() + "\n"


def _summary_sections(report):
    summary = report.get("summary") or "A summary is not available."
    sections = [
        "MEETING SUMMARY (AI-generated)", "-" * 30, summary, "",
        "KEY DISCUSSION POINTS (extracted from transcript)", "-" * 30,
        *_numbered(report.get("key_points", []), NO_KEY_POINTS), "",
        "DECISIONS MADE (extracted from transcript)", "-" * 30,
        *_numbered(report.get("decisions", []), NO_DECISIONS), "",
        "ACTION ITEMS (extracted from transcript)", "-" * 30,
        *_action_lines(report.get("action_items", [])), "",
        _SOURCE_NOTE,
    ]
    return sections


def build_summary_txt(report):
    lines = _header(report, "MEETING SUMMARY") + _summary_sections(report)
    return "\n".join(lines).rstrip() + "\n"


def build_report_txt(report):
    lines = _header(report, "COMPLETE MEETING REPORT")
    lines += _summary_sections(report)
    lines += ["", "FULL TRANSCRIPT", "-" * 30, report.get("transcript", "")]
    return "\n".join(lines).rstrip() + "\n"
