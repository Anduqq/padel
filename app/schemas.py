from __future__ import annotations
from typing import List
from pydantic import BaseModel, validator


class CreateTournamentIn(BaseModel):
    name: str
    players: List[str]
    courts: int = 1


    @validator('players')
    def at_least_four(cls, v: List[str]) -> List[str]:
        if len(v) < 4:
            raise ValueError('players must contain at least 4 names')
        return v


    @validator('courts')
    def ge_one(cls, v: int) -> int:
        if v < 1:
            raise ValueError('courts must be >= 1')
        return v


class TournamentOut(BaseModel):
    id: str
    name: str
    players: List[str]
    courts: int
    round_idx: int


class RoundOut(BaseModel):
    round_idx: int
    matches: List[dict]


class ScoresIn(BaseModel):
    scores: List[str]


class LeaderRow(BaseModel):
    player: str
    points: int
    matches: int
    gf: int
    ga: int