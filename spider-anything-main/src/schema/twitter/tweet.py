import typing as t

from pydantic import BaseModel



class Tweet(BaseModel):
    rest_id: str
    core: t.Any
    views: t.Any
    quoted_status_result: t.Any
    legacy: t.Any

class TweetWithVisibilityResults(BaseModel):
    tweet: Tweet