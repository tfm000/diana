from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    SYNTHESIZING = "synthesizing"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


def parse_page_range(spec: str, total: int) -> list[int]:
    """Parse a page range spec like '1-3, 5, 8-10' into a sorted list of 0-based indices.

    Pages in the spec are 1-based (user-facing). Out-of-range values are clamped.
    Returns an empty list if spec is empty or None (meaning 'all pages').
    """
    if not spec or not spec.strip():
        return []
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            try:
                start = max(1, int(start_s.strip()))
            except ValueError:
                raise ValueError(f"Invalid number in range: '{start_s.strip()}'")
            try:
                end = min(total, int(end_s.strip()))
            except ValueError:
                raise ValueError(f"Invalid number in range: '{end_s.strip()}'")
            pages.update(range(start - 1, end))
        else:
            try:
                p = int(part.strip())
            except ValueError:
                raise ValueError(f"Invalid page number: '{part.strip()}'")
            if 1 <= p <= total:
                pages.add(p - 1)
    return sorted(pages)


@dataclass
class Job:
    id: str
    filename: str
    file_type: str
    upload_path: str
    status: JobStatus
    tts_engine: str
    tts_voice: str
    page_range: Optional[str] = None
    folder: str = ""
    output_path: Optional[str] = None
    total_chunks: int = 0
    completed_chunks: int = 0
    error_message: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        now = datetime.now()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)
        if self.folder is None:
            self.folder = ""

    @property
    def progress(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.completed_chunks / self.total_chunks
