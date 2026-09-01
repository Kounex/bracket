from decimal import Decimal

from bracket.logic.scheduling.round_optimizer import get_optimal_round_pairings
from bracket.models.db.match import get_match_hash
from bracket.models.db.stage_item import PairingMode
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.models.db.team import Team
from bracket.utils.dummy_records import DUMMY_TEAM1
from bracket.utils.id_types import StageItemInputId, TeamId, TournamentId


def make_input(input_id: int, points: str) -> StageItemInputFinal:
    return StageItemInputFinal(
        id=StageItemInputId(input_id),
        tournament_id=TournamentId(-1),
        team_id=TeamId(input_id),
        slot=0,
        points=Decimal(points),
        wins=0,
        draws=0,
        losses=0,
        team=Team(**DUMMY_TEAM1.model_dump(), id=TeamId(input_id)),
    )


def played_map(ids_and_counts: list[tuple[int, int]]) -> dict[StageItemInputId, int]:
    return {StageItemInputId(i): c for i, c in ids_and_counts}


def pair_team_ids(
    pairings: list[tuple[StageItemInputFinal, StageItemInputFinal]],
) -> set[frozenset[int]]:
    return {frozenset((int(a.team_id), int(b.team_id))) for a, b in pairings}


def test_participant_count_and_no_duplicates() -> None:
    inputs = [make_input(i, "1200") for i in range(1, 9)]
    pairings = get_optimal_round_pairings(
        inputs, played_map([(i, 0) for i in range(1, 9)]), 3, frozenset(), PairingMode.SOCIAL
    )
    assert pairings is not None
    assert len(pairings) == 3  # 3 courts -> 3 matches, 2 teams sit out
    all_teams = [t for pair in pairings for t in pair]
    assert len({t.id for t in all_teams}) == 6  # no team twice


def test_social_mode_selects_least_played() -> None:
    inputs = [make_input(i, "1200") for i in range(1, 7)]
    times_played = played_map([(1, 2), (2, 2), (3, 0), (4, 0), (5, 0), (6, 0)])
    pairings = get_optimal_round_pairings(inputs, times_played, 2, frozenset(), PairingMode.SOCIAL)
    assert pairings is not None
    # The four teams with 0 matches played must be the participants.
    assert pair_team_ids(pairings) == {frozenset((3, 4)), frozenset((5, 6))}


def test_competitive_mode_pairs_leaders() -> None:
    # DR Cup round-8 reconstruction: two leaders (4 played, high rating), six weaker teams
    # with fewer matches played. Social benches the leaders; competitive pairs them together.
    inputs = [
        make_input(1, "1300"),
        make_input(2, "1300"),
        make_input(3, "1200"),
        make_input(4, "1200"),
        make_input(5, "1100"),
        make_input(6, "1100"),
        make_input(7, "1100"),
        make_input(8, "1100"),
    ]
    times_played = played_map([(1, 4), (2, 4), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3)])

    competitive = get_optimal_round_pairings(
        inputs, times_played, 3, frozenset(), PairingMode.COMPETITIVE
    )
    assert competitive is not None
    assert frozenset((1, 2)) in pair_team_ids(competitive)
    assert frozenset((3, 4)) in pair_team_ids(competitive)

    social = get_optimal_round_pairings(inputs, times_played, 3, frozenset(), PairingMode.SOCIAL)
    assert social is not None
    social_teams = pair_team_ids(social)
    assert all(1 not in pair and 2 not in pair for pair in social_teams)


def test_no_rematches() -> None:
    inputs = [make_input(1, "1200"), make_input(2, "1200"), make_input(3, "1200")]
    previous = frozenset(
        {
            get_match_hash(StageItemInputId(1), StageItemInputId(2)),
            get_match_hash(StageItemInputId(2), StageItemInputId(1)),
        }
    )
    pairings = get_optimal_round_pairings(
        inputs, played_map([(1, 1), (2, 1), (3, 1)]), 1, previous, PairingMode.COMPETITIVE
    )
    assert pairings is not None
    assert pair_team_ids(pairings) != {frozenset((1, 2))}
    assert len(pairings) == 1


def test_returns_none_above_exact_cap() -> None:
    inputs = [make_input(i, "1200") for i in range(1, 22)]
    assert (
        get_optimal_round_pairings(
            inputs, played_map([(i, 0) for i in range(1, 22)]), 5, frozenset(), PairingMode.SOCIAL
        )
        is None
    )


def test_no_pairing_possible_returns_empty() -> None:
    inputs = [make_input(1, "1200"), make_input(2, "1200")]
    previous = frozenset(
        {
            get_match_hash(StageItemInputId(1), StageItemInputId(2)),
            get_match_hash(StageItemInputId(2), StageItemInputId(1)),
        }
    )
    pairings = get_optimal_round_pairings(
        inputs, played_map([(1, 0), (2, 0)]), 1, previous, PairingMode.SOCIAL
    )
    assert pairings == []
