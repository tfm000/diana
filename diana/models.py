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


@dataclass
class Job:
    id: str
    filename: str
    file_type: str
    upload_path: str
    status: JobStatus
    tts_engine: str
    tts_voice: str
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

    @property
    def progress(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.completed_chunks / self.total_chunks
