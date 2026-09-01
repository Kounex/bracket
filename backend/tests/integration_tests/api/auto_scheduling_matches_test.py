import pytest
from heliclockter import datetime_utc

from bracket.models.db.match import MatchBody, MatchWithDetailsDefinitive
from bracket.models.db.round import RoundInsertable
from bracket.models.db.stage_item import PairingMode, StageItemWithInputsCreate, StageType
from bracket.models.db.stage_item_inputs import (
    StageItemInputCreateBodyFinal,
)
from bracket.sql.matches import sql_update_match
from bracket.sql.rounds import sql_create_round
from bracket.sql.shared import sql_delete_stage_item_with_foreign_keys
from bracket.sql.stage_items import sql_create_stage_item_with_inputs
from bracket.sql.stages import get_full_tournament_details
from bracket.utils.dummy_records import (
    DUMMY_COURT1,
    DUMMY_COURT2,
    DUMMY_STAGE2,
    DUMMY_STAGE_ITEM1,
    DUMMY_TEAM1,
)
from bracket.utils.http import HTTPMethod
from tests.integration_tests.api.shared import (
    SUCCESS_RESPONSE,
    send_tournament_request,
)
from tests.integration_tests.mocks import MOCK_NOW
from tests.integration_tests.models import AuthContext
from tests.integration_tests.sql import (
    inserted_court,
    inserted_stage,
    inserted_team,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_start_next_round(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_court(
            DUMMY_COURT1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ),
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_inserted_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_inserted_2,
    ):
        tournament_id = auth_context.tournament.id
        stage_item_1 = await sql_create_stage_item_with_inputs(
            tournament_id,
            StageItemWithInputsCreate(
                stage_id=stage_inserted_1.id,
                name=DUMMY_STAGE_ITEM1.name,
                team_count=2,
                type=StageType.SWISS,
                inputs=[
                    StageItemInputCreateBodyFinal(
                        slot=1,
                        team_id=team_inserted_1.id,
                    ),
                    StageItemInputCreateBodyFinal(
                        slot=2,
                        team_id=team_inserted_2.id,
                    ),
                ],
            ),
        )
        await sql_create_round(
            RoundInsertable(
                stage_item_id=stage_item_1.id,
                name="",
                is_draft=False,
                created=MOCK_NOW,
            ),
        )

        try:
            response = await send_tournament_request(
                HTTPMethod.POST,
                f"stage_items/{stage_item_1.id}/start_next_round",
                auth_context,
                json={},
            )

            assert response == SUCCESS_RESPONSE

            response = await send_tournament_request(
                HTTPMethod.POST,
                f"stage_items/{stage_item_1.id}/start_next_round",
                auth_context,
                json={"adjust_to_time": datetime_utc.now().isoformat()},
            )
            msg = "No more matches to schedule, all combinations of teams have been added already"
            assert response == {"detail": msg}
        finally:
            await sql_delete_stage_item_with_foreign_keys(stage_item_1.id)


@pytest.mark.asyncio(loop_scope="session")
async def test_start_next_round_competitive_pairs_winners(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with (
        inserted_court(
            DUMMY_COURT1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ),
        inserted_court(
            DUMMY_COURT2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ),
        inserted_stage(
            DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as stage_inserted_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_1,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_2,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_3,
        inserted_team(
            DUMMY_TEAM1.model_copy(update={"tournament_id": auth_context.tournament.id})
        ) as team_4,
    ):
        tournament_id = auth_context.tournament.id
        stage_item = await sql_create_stage_item_with_inputs(
            tournament_id,
            StageItemWithInputsCreate(
                stage_id=stage_inserted_1.id,
                name=DUMMY_STAGE_ITEM1.name,
                team_count=4,
                type=StageType.SWISS,
                pairing_mode=PairingMode.COMPETITIVE,
                inputs=[
                    StageItemInputCreateBodyFinal(slot=1, team_id=team_1.id),
                    StageItemInputCreateBodyFinal(slot=2, team_id=team_2.id),
                    StageItemInputCreateBodyFinal(slot=3, team_id=team_3.id),
                    StageItemInputCreateBodyFinal(slot=4, team_id=team_4.id),
                ],
            ),
        )

        # Round 1
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stage_items/{stage_item.id}/start_next_round",
            auth_context,
            json={},
        )
        assert response == SUCCESS_RESPONSE

        [stage] = await get_full_tournament_details(tournament_id)
        round_1 = stage.stage_items[0].rounds[0]
        assert len(round_1.matches) == 2

        # team_1 and team_3 win their matches
        for match in round_1.matches:
            assert isinstance(match, MatchWithDetailsDefinitive)
            winner_is_input1 = match.stage_item_input1.team_id in (team_1.id, team_3.id)
            update = (
                {"stage_item_input1_score": 1}
                if winner_is_input1
                else {"stage_item_input2_score": 1}
            )
            await sql_update_match(
                match.id,
                MatchBody(**match.model_copy(update=update).model_dump()),
                auth_context.tournament,
            )

        # Round 2: winners must play winners, losers play losers
        response = await send_tournament_request(
            HTTPMethod.POST,
            f"stage_items/{stage_item.id}/start_next_round",
            auth_context,
            json={},
        )
        assert response == SUCCESS_RESPONSE

        [stage] = await get_full_tournament_details(tournament_id)
        rounds = stage.stage_items[0].rounds
        assert len(rounds) == 2
        round_2 = max(rounds, key=lambda r: r.id)
        pair_sets = {
            frozenset((m.stage_item_input1.team_id, m.stage_item_input2.team_id))
            for m in round_2.matches
            if isinstance(m, MatchWithDetailsDefinitive)
        }
        assert pair_sets == {
            frozenset((team_1.id, team_3.id)),
            frozenset((team_2.id, team_4.id)),
        }

        await sql_delete_stage_item_with_foreign_keys(stage_item.id)
