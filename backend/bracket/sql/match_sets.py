from bracket.database import database
from bracket.models.db.match_set import MatchSetBody
from bracket.utils.id_types import MatchId


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
