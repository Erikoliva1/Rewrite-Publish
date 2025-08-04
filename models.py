from pydantic import BaseModel

class NewsRequest(BaseModel):
    news: str
    api: str
