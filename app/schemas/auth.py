from pydantic import Field

from app.schemas.common import APIModel


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=1)
