from bracket.database import database
from bracket.models.db.match_set import MatchSet, MatchSetBody
from bracket.utils.id_types import MatchId


async def get_match_sets(match_id: MatchId) -> list[MatchSet]:
    query = """
        SELECT *
        FROM match_sets
        WHERE match_id = :match_id
        ORDER BY set_number
        """
    result = await database.fetch_all(query=query, values={"match_id": match_id})
    return [MatchSet.model_validate(x) for x in result]


async def get_match_sets_for_matches(match_ids: list[MatchId]) -> dict[int, list[MatchSet]]:
    """Batch-load sets for multiple matches, keyed by match_id."""
    if not match_ids:
        return {}

    query = """
        SELECT *
        FROM match_sets
        WHERE match_id = ANY(:match_ids)
        ORDER BY match_id, set_number
        """
    result = await database.fetch_all(query=query, values={"match_ids": match_ids})
    sets_by_match: dict[int, list[MatchSet]] = {}
    for row in result:
        ms = MatchSet.model_validate(row)
        sets_by_match.setdefault(ms.match_id, []).append(ms)
    return sets_by_match


async def sql_replace_match_sets(match_id: MatchId, sets: list[MatchSetBody]) -> None:
    """Delete existing sets and insert new ones for a match."""
    delete_query = """
        DELETE FROM match_sets
        WHERE match_id = :match_id
        """
    await database.execute(query=delete_query, values={"match_id": match_id})

    for s in sets:
        insert_query = """
            INSERT INTO match_sets (match_id, set_number, score1, score2)
            VALUES (:match_id, :set_number, :score1, :score2)
            """
        await database.execute(
            query=insert_query,
            values={"match_id": match_id, **s.model_dump()},
        )


async def sql_delete_match_sets(match_id: MatchId) -> None:
    query = """
        DELETE FROM match_sets
        WHERE match_id = :match_id
        """
    await database.execute(query=query, values={"match_id": match_id})
