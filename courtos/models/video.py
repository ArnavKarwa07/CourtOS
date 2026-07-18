from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum

class VideoStatus(str, Enum):
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

class VideoRecord(BaseModel):
    video_id: str
    filename: str
    status: VideoStatus
    uploaded_at: datetime
    completed_at: Optional[datetime] = None
