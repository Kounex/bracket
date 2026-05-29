from bracket.models.db.shared import BaseModelORM
from bracket.utils.id_types import SportConfigId, TournamentId


class SportConfigInsertable(BaseModelORM):
    tournament_id: TournamentId
    name: str
    num_sets: int
    points_per_set: int | None = None
    points_last_set: int | None = None
    min_point_difference: int | None = None
    max_score: int | None = None


class SportConfig(SportConfigInsertable):
    id: SportConfigId


class SportConfigBody(BaseModelORM):
    name: str = "Custom"
    num_sets: int = 3
    points_per_set: int | None = None
    points_last_set: int | None = None
    min_point_difference: int | None = None
    max_score: int | None = None


SPORT_PRESETS: dict[str, SportConfigBody] = {
    "Tennis": SportConfigBody(
        name="Tennis", num_sets=3, points_per_set=6,
        points_last_set=6, min_point_difference=1, max_score=7,
    ),
    "Badminton": SportConfigBody(
        name="Badminton", num_sets=3, points_per_set=21,
        points_last_set=21, min_point_difference=2, max_score=30,
    ),
    "Table Tennis": SportConfigBody(
        name="Table Tennis", num_sets=5, points_per_set=11,
        points_last_set=11, min_point_difference=2,
    ),
    "Volleyball": SportConfigBody(
        name="Volleyball", num_sets=5, points_per_set=25,
        points_last_set=15, min_point_difference=2,
    ),
    "Padel": SportConfigBody(
        name="Padel", num_sets=3, points_per_set=6,
        points_last_set=6, min_point_difference=1, max_score=7,
    ),
}
