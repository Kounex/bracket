from pydantic import Field

from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import MatchId, MatchSetId


class MatchSetInsertable(BaseModelORM):
    match_id: MatchId
    set_number: int = Field(..., ge=1)
    score1: int = Field(0, ge=0)
    score2: int = Field(0, ge=0)


class MatchSet(MatchSetInsertable):
    id: MatchSetId


class MatchSetBody(BaseModelORM):
    set_number: int = Field(..., ge=1)
    score1: int = Field(0, ge=0)
    score2: int = Field(0, ge=0)
