from pydantic import BaseModel
from typing import Optional, List

class NewsRequest(BaseModel):
    news: str
    api: str

class PublishRequest(BaseModel):
    news: str
    featured_image_id: Optional[int] = None
    categories: List[str] = []
    tags: List[str] = []
    post_status: str = "publish" # Added for draft/publish option
