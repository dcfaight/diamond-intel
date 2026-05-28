from pydantic import BaseModel


class TeamRef(BaseModel):
    id: int
    name: str
    abbreviation: str


class ScoreBlock(BaseModel):
    team: int
    opponent: int


class GameBlock(BaseModel):
    date: str
    status: str
    score: ScoreBlock
    result: str
    venue: str


class TopFactor(BaseModel):
    key: str
    title: str
    detail: str


class PlayerTrend(BaseModel):
    player_name: str
    trend_type: str
    detail: str


class WatchNext(BaseModel):
    title: str
    detail: str


class GeneratedFrom(BaseModel):
    source: str
    version: str


class PostgameReportInsight(BaseModel):
    game_id: int
    team: TeamRef
    opponent: TeamRef
    game: GameBlock
    top_factors: list[TopFactor]
    player_trends: list[PlayerTrend]
    watch_next: WatchNext
    confidence: str
    generated_from: GeneratedFrom
