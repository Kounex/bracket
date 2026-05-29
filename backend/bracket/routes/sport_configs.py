from fastapi import APIRouter, Depends

from bracket.config import config
from bracket.models.db.sport import SPORT_PRESETS, SportConfigBody
from bracket.models.db.tournament import Tournament
from bracket.models.db.user import UserPublic
from bracket.routes.auth import (
    user_authenticated_for_tournament,
    user_authenticated_or_public_dashboard,
)
from bracket.routes.models import SportConfigResponse, SuccessResponse
from bracket.routes.util import disallow_archived_tournament
from bracket.sql.sport_configs import (
    get_sport_config,
    sql_create_sport_config,
    sql_delete_sport_config,
    sql_update_sport_config,
)
from bracket.utils.id_types import TournamentId

router = APIRouter(prefix=config.api_prefix)


@router.get(
    "/tournaments/{tournament_id}/sport-config",
    response_model=SportConfigResponse,
)
async def get_tournament_sport_config(
    tournament_id: TournamentId,
    _: UserPublic | None = Depends(user_authenticated_or_public_dashboard),
) -> SportConfigResponse:
    sport_config = await get_sport_config(tournament_id)
    return SportConfigResponse(data=sport_config)


@router.put(
    "/tournaments/{tournament_id}/sport-config",
    response_model=SuccessResponse,
)
async def update_tournament_sport_config(
    tournament_id: TournamentId,
    body: SportConfigBody,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    existing = await get_sport_config(tournament_id)
    if existing is None:
        await sql_create_sport_config(tournament_id, body)
    else:
        await sql_update_sport_config(tournament_id, body)
    return SuccessResponse()


@router.delete(
    "/tournaments/{tournament_id}/sport-config",
    response_model=SuccessResponse,
)
async def delete_tournament_sport_config(
    tournament_id: TournamentId,
    _: UserPublic = Depends(user_authenticated_for_tournament),
    __: Tournament = Depends(disallow_archived_tournament),
) -> SuccessResponse:
    await sql_delete_sport_config(tournament_id)
    return SuccessResponse()


@router.get(
    "/sport-presets",
    response_model=dict[str, SportConfigBody],
)
async def get_sport_presets() -> dict[str, SportConfigBody]:
    return SPORT_PRESETS
