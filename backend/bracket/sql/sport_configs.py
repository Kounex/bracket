from bracket.database import database
from bracket.models.db.sport import SportConfig, SportConfigBody
from bracket.utils.id_types import SportConfigId, TournamentId


async def get_sport_config(tournament_id: TournamentId) -> SportConfig | None:
    query = """
        SELECT *
        FROM sport_configs
        WHERE tournament_id = :tournament_id
        """
    result = await database.fetch_one(query=query, values={"tournament_id": tournament_id})
    return SportConfig.model_validate(result) if result is not None else None


async def sql_create_sport_config(
    tournament_id: TournamentId, body: SportConfigBody
) -> SportConfigId:
    query = """
        INSERT INTO sport_configs (
            tournament_id, name, num_sets, points_per_set,
            points_last_set, min_point_difference, max_score
        )
        VALUES (
            :tournament_id, :name, :num_sets, :points_per_set,
            :points_last_set, :min_point_difference, :max_score
        )
        RETURNING id
        """
    new_id = await database.fetch_val(
        query=query,
        values={"tournament_id": tournament_id, **body.model_dump()},
    )
    return SportConfigId(new_id)


async def sql_update_sport_config(tournament_id: TournamentId, body: SportConfigBody) -> None:
    query = """
        UPDATE sport_configs
        SET name = :name,
            num_sets = :num_sets,
            points_per_set = :points_per_set,
            points_last_set = :points_last_set,
            min_point_difference = :min_point_difference,
            max_score = :max_score
        WHERE tournament_id = :tournament_id
        """
    await database.execute(
        query=query,
        values={"tournament_id": tournament_id, **body.model_dump()},
    )


async def sql_delete_sport_config(tournament_id: TournamentId) -> None:
    query = """
        DELETE FROM sport_configs
        WHERE tournament_id = :tournament_id
        """
    await database.execute(query=query, values={"tournament_id": tournament_id})


async def ensure_sport_config(tournament_id: TournamentId, body: SportConfigBody | None) -> None:
    """Create or update the sport config for a tournament.

    If body is None, delete any existing config (switch to simple mode).
    """
    if body is None:
        await sql_delete_sport_config(tournament_id)
        return

    existing = await get_sport_config(tournament_id)
    if existing is None:
        await sql_create_sport_config(tournament_id, body)
    else:
        await sql_update_sport_config(tournament_id, body)
