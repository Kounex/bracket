# Swiss Round Optimizer + Pairing Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the greedy Swiss round auto-scheduler with a globally optimized round planner and add a per-stage-item `pairing_mode` (`social` default / `competitive`) toggle.

**Architecture:** New pure-function optimizer module (`round_optimizer.py`) using bitmask DP over teams; `start_next_round` route calls it once per round instead of the greedy per-match loop. `pairing_mode` is a new `stage_items` column exposed through the API and editable in the frontend stage-item modals.

**Tech Stack:** FastAPI, SQLAlchemy (raw `text` queries via `databases`), Alembic, Pydantic v2, pytest (unit + integration against podman postgres), React + Mantine + @mantine/form, react-i18next.

**Spec:** `docs/superpowers/specs/2026-09-01-swiss-round-optimizer-design.md`

## Global Constraints

- Backend: Python 3.13, ruff format line length **100**, must pass `ruff format --check`, `ruff check`, `mypy`, `pyrefly`, `pylint`, `vulture` (see `backend/AGENTS.md` / CI `backend.yml`).
- Integration tests need postgres: `podman machine start` (if stopped), then
  `podman run -d --name bracket_ci_postgres -e POSTGRES_DB=bracket_ci -e POSTGRES_USER=bracket_ci -e POSTGRES_PASSWORD=bracket_ci -p 5532:5432 postgres:16-alpine`
  (if the container already exists: `podman start bracket_ci_postgres`). Run tests from `backend/` with `uv run pytest`.
- OpenAPI freshness is CI-enforced (`test_openapi_up_to_date`): after any backend route/model change run `cd backend && uv run ./cli.py generate-openapi`, then `cd frontend && pnpm openapi-ts`, and commit both `backend/openapi/openapi.json` and `frontend/src/openapi/**`.
- `PairingMode` enum values are the uppercase names (`SOCIAL`, `COMPETITIVE`), matching the `EnumAutoStr` convention used by `StageType`.
- Frontend checks: `cd frontend && pnpm test` (tsc + prettier).
- Commits: conventional style (`feat:`, `fix:`, `ci:`, `docs:`), on branch `dev`.

---

### Task 1: `pairing_mode` data model, migration, SQL, update route

**Files:**

- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_pairing_mode_to_stage_items.py`
- Modify: `backend/bracket/schema.py:55-72` (stage_items table)
- Modify: `backend/bracket/models/db/stage_item.py` (enum + fields)
- Modify: `backend/bracket/sql/stage_items.py:14-37` (INSERT)
- Modify: `backend/bracket/routes/stage_items.py:101-131` (update query)
- Test: `backend/tests/integration_tests/api/stage_items_test.py` (append test)

**Interfaces:**

- Produces: `PairingMode` enum (`SOCIAL` | `COMPETITIVE`, `EnumAutoStr`) in `bracket.models.db.stage_item`; `StageItem.pairing_mode`, `StageItemCreateBody.pairing_mode` (default `SOCIAL`), `StageItemUpdateBody.pairing_mode` (required); used by Tasks 2-4.

- [ ] **Step 1: Start the test database**

```bash
podman machine start || true
podman start bracket_ci_postgres 2>/dev/null || podman run -d --name bracket_ci_postgres \
  -e POSTGRES_DB=bracket_ci -e POSTGRES_USER=bracket_ci -e POSTGRES_PASSWORD=bracket_ci \
  -p 5532:5432 postgres:16-alpine
```

- [ ] **Step 2: Write the failing integration test**

Append to `backend/tests/integration_tests/api/stage_items_test.py`:

```python
@pytest.mark.asyncio(loop_scope="session")
async def test_stage_item_pairing_mode(
    startup_and_shutdown_uvicorn_server: None, auth_context: AuthContext
) -> None:
    async with inserted_stage(
        DUMMY_STAGE2.model_copy(update={"tournament_id": auth_context.tournament.id})
    ) as stage_inserted:
        # Create without pairing_mode -> defaults to SOCIAL
        assert (
            await send_tournament_request(
                HTTPMethod.POST,
                "stage_items",
                auth_context,
                json={
                    "type": StageType.SWISS.value,
                    "team_count": 4,
                    "stage_id": stage_inserted.id,
                },
            )
            == SUCCESS_RESPONSE
        )
        [stage] = await get_full_tournament_details(auth_context.tournament.id)
        stage_item = max(stage.stage_items, key=lambda si: si.id)
        assert stage_item.pairing_mode is PairingMode.SOCIAL

        # Update to COMPETITIVE
        assert (
            await send_tournament_request(
                HTTPMethod.PUT,
                f"stage_items/{stage_item.id}",
                auth_context,
                json={
                    "name": stage_item.name,
                    "ranking_id": stage_item.ranking_id,
                    "pairing_mode": PairingMode.COMPETITIVE.value,
                },
            )
            == SUCCESS_RESPONSE
        )
        [stage] = await get_full_tournament_details(auth_context.tournament.id)
        assert max(stage.stage_items, key=lambda si: si.id).pairing_mode is PairingMode.COMPETITIVE

        await sql_delete_stage_item_with_foreign_keys(stage_item.id)
```

Add imports to that file: `PairingMode` from `bracket.models.db.stage_item`,
`get_full_tournament_details` from `bracket.sql.stages`,
`sql_delete_stage_item_with_foreign_keys` from `bracket.sql.shared`.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration_tests/api/stage_items_test.py::test_stage_item_pairing_mode -v`
Expected: FAIL (AttributeError: no `pairing_mode` on StageItem)

- [ ] **Step 4: Add the enum and model fields**

In `backend/bracket/models/db/stage_item.py`, after `StageType`:

```python
class PairingMode(EnumAutoStr):
    SOCIAL = auto()
    COMPETITIVE = auto()
```

Add to `StageItemInsertable` (after `ranking_id`):

```python
    pairing_mode: PairingMode = PairingMode.SOCIAL
```

Add to `StageItemUpdateBody`:

```python
    pairing_mode: PairingMode
```

Add to `StageItemCreateBody` (after `ranking_id`):

```python
    pairing_mode: PairingMode = PairingMode.SOCIAL
```

- [ ] **Step 5: Add the schema column and migration**

In `backend/bracket/schema.py`, in the `stage_items` table after the `ranking_id` column:

```python
    Column("pairing_mode", Text, nullable=False, server_default="social"),
```

Create `backend/alembic/versions/a1b2c3d4e5f6_add_pairing_mode_to_stage_items.py`:

```python
"""add pairing_mode to stage_items

Revision ID: a1b2c3d4e5f6
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str | None = "a1b2c3d4e5f6"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "stage_items",
        sa.Column("pairing_mode", sa.Text(), server_default="social", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stage_items", "pairing_mode")
```

- [ ] **Step 6: Persist pairing_mode in SQL and the update route**

In `backend/bracket/sql/stage_items.py` `sql_create_stage_item`, change the query and values:

```python
    query = """
            INSERT INTO stage_items (type, stage_id, name, team_count, ranking_id, pairing_mode)
            VALUES (:stage_item_type, :stage_id, :name, :team_count, :ranking_id, :pairing_mode)
            RETURNING *
            """
```

and add to `values`: `"pairing_mode": stage_item.pairing_mode.value,`

In `backend/bracket/routes/stage_items.py` `update_stage_item`, change the query:

```python
    query = """
        UPDATE stage_items
        SET name = :name, pairing_mode = :pairing_mode
        WHERE stage_items.id = :stage_item_id
    """
```

and values: `values={"stage_item_id": stage_item_id, "name": stage_item_body.name, "pairing_mode": stage_item_body.pairing_mode.value},`

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/integration_tests/api/stage_items_test.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 8: Regenerate OpenAPI + frontend types**

```bash
cd backend && uv run ./cli.py generate-openapi
cd frontend && pnpm openapi-ts
```

Verify: `cd backend && uv run pytest tests/unit_tests/openapi_test.py -v` passes.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/a1b2c3d4e5f6_add_pairing_mode_to_stage_items.py \
  backend/bracket/schema.py backend/bracket/models/db/stage_item.py \
  backend/bracket/sql/stage_items.py backend/bracket/routes/stage_items.py \
  backend/tests/integration_tests/api/stage_items_test.py \
  backend/openapi/openapi.json frontend/src/openapi
git commit -m "feat: add pairing_mode to stage items (model, migration, API)"
```

---

### Task 2: `round_optimizer` module with exact round optimization

**Files:**

- Create: `backend/bracket/logic/scheduling/round_optimizer.py`
- Test: `backend/tests/unit_tests/round_optimizer_test.py`

**Interfaces:**

- Consumes: `PairingMode` (Task 1), `get_match_hash` from `bracket.models.db.match`, `StageItemInputFinal` from `bracket.models.db.stage_item_inputs`.
- Produces:

```python
def get_optimal_round_pairings(
    inputs: list[StageItemInputFinal],
    times_played_per_input: dict[StageItemInputId, int],
    courts_count: int,
    previous_match_hashes: frozenset[str],
    mode: PairingMode,
) -> list[tuple[StageItemInputFinal, StageItemInputFinal]] | None
```

Returns `None` when `len(inputs) > MAX_INPUTS_FOR_EXACT_OPTIMIZATION` (caller falls back to greedy). Returns `[]` when no valid pairing exists (e.g. all remaining pairs are rematches). Consumed by Task 3.

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit_tests/round_optimizer_test.py`:

```python
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
    pairings = get_optimal_round_pairings(
        inputs, times_played, 2, frozenset(), PairingMode.SOCIAL
    )
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
        {get_match_hash(StageItemInputId(1), StageItemInputId(2)),
         get_match_hash(StageItemInputId(2), StageItemInputId(1))}
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
        {get_match_hash(StageItemInputId(1), StageItemInputId(2)),
         get_match_hash(StageItemInputId(2), StageItemInputId(1))}
    )
    pairings = get_optimal_round_pairings(
        inputs, played_map([(1, 0), (2, 0)]), 1, previous, PairingMode.SOCIAL
    )
    assert pairings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit_tests/round_optimizer_test.py -v`
Expected: FAIL (ModuleNotFoundError: bracket.logic.scheduling.round_optimizer)

- [ ] **Step 3: Implement the optimizer**

Create `backend/bracket/logic/scheduling/round_optimizer.py`:

```python
from decimal import Decimal
from functools import lru_cache

from bracket.models.db.match import get_match_hash
from bracket.models.db.stage_item import PairingMode
from bracket.models.db.stage_item_inputs import StageItemInputFinal
from bracket.utils.id_types import StageItemInputId
from bracket.utils.types import assert_some

MAX_INPUTS_FOR_EXACT_OPTIMIZATION = 20
"""
Above this number of teams the exact bitmask DP (2^N states) is too slow and the caller
should fall back to the greedy suggestion-based scheduling.
"""

_SOCIAL_FAIRNESS_WEIGHT = Decimal("1000000")
_COMPETITIVE_FAIRNESS_WEIGHT = Decimal("0.01")
_INF = Decimal("Infinity")


def get_optimal_round_pairings(
    inputs: list[StageItemInputFinal],
    times_played_per_input: dict[StageItemInputId, int],
    courts_count: int,
    previous_match_hashes: frozenset[str],
    mode: PairingMode,
) -> list[tuple[StageItemInputFinal, StageItemInputFinal]] | None:
    n = len(inputs)
    if n > MAX_INPUTS_FOR_EXACT_OPTIMIZATION:
        return None
    pairs_needed = min(courts_count, n // 2)
    if pairs_needed < 1:
        return []

    fairness_weight = (
        _SOCIAL_FAIRNESS_WEIGHT if mode is PairingMode.SOCIAL else _COMPETITIVE_FAIRNESS_WEIGHT
    )
    elos = [input_.elo for input_ in inputs]
    played = [times_played_per_input.get(assert_some(input_.id), 0) for input_ in inputs]
    input_ids = [assert_some(input_.id) for input_ in inputs]

    def pair_cost(i: int, j: int) -> Decimal:
        return fairness_weight * (played[i] + played[j]) + abs(elos[i] - elos[j])

    @lru_cache(maxsize=None)
    def dp(avail: int, pairs_left: int) -> tuple[Decimal, tuple[tuple[int, int], ...]]:
        """Min cost to schedule `pairs_left` more matches from the teams set in `avail`."""
        if pairs_left == 0:
            return (Decimal(0), ())
        if avail.bit_count() < pairs_left * 2:
            return (_INF, ())
        i = (avail & -avail).bit_length() - 1
        rest = avail ^ (1 << i)
        best = dp(rest, pairs_left)  # team i sits out this round
        jbits = rest
        while jbits:
            j = (jbits & -jbits).bit_length() - 1
            jbits &= jbits - 1
            if get_match_hash(input_ids[i], input_ids[j]) in previous_match_hashes:
                continue
            sub_cost, sub_pairs = dp(rest ^ (1 << j), pairs_left - 1)
            candidate = (sub_cost + pair_cost(i, j), (*sub_pairs, (i, j)))
            if candidate[0] < best[0]:
                best = candidate
        return best

    cost, pair_indices = dp((1 << n) - 1, pairs_needed)
    if cost >= _INF:
        return []
    return [(inputs[i], inputs[j]) for i, j in pair_indices]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit_tests/round_optimizer_test.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Lint**

Run: `cd backend && uv run ruff format --check bracket/ tests/ && uv run ruff check bracket/ tests/ && uv run mypy bracket/`
Expected: all clean (fix formatting with `uv run ruff format` if needed)

- [ ] **Step 6: Commit**

```bash
git add backend/bracket/logic/scheduling/round_optimizer.py backend/tests/unit_tests/round_optimizer_test.py
git commit -m "feat: exact Swiss round optimizer with social/competitive pairing modes"
```

---

### Task 3: Wire optimizer into `start_next_round`

**Files:**

- Modify: `backend/bracket/routes/stage_items.py:134-238` (`start_next_round`)
- Test: `backend/tests/integration_tests/api/auto_scheduling_matches_test.py` (append test)

**Interfaces:**

- Consumes: `get_optimal_round_pairings` (Task 2); `get_previous_matches_hashes`, `get_number_of_inputs_played_per_input` from `bracket.logic.scheduling.ladder_teams`; `PairingMode` (Task 1).

- [ ] **Step 1: Write the failing integration test**

Append to `backend/tests/integration_tests/api/auto_scheduling_matches_test.py`:

```python
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
        }
        assert pair_sets == {
            frozenset((team_1.id, team_3.id)),
            frozenset((team_2.id, team_4.id)),
        }

        await sql_delete_stage_item_with_foreign_keys(stage_item.id)
```

Add imports: `PairingMode` from `bracket.models.db.stage_item`,
`MatchWithDetailsDefinitive` from `bracket.models.db.match`,
`sql_update_match` from `bracket.sql.matches`,
`get_full_tournament_details` from `bracket.sql.stages`,
`DUMMY_COURT2` from `bracket.utils.dummy_records`
(check the file's existing imports first; some may already be present).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/integration_tests/api/auto_scheduling_matches_test.py::test_start_next_round_competitive_pairs_winners -v`
Expected: FAIL — round 2 pairings are greedy/rotation-based, not winners-vs-winners (or 422 from `pairing_mode` in `StageItemWithInputsCreate` if run before Task 1 — Task 1 must be done first).

- [ ] **Step 3: Rework `start_next_round` to use the optimizer**

In `backend/bracket/routes/stage_items.py`, in `start_next_round`, replace everything from
`match_filter = MatchFilter(...)` through the greedy `for ___ in range(limit):` loop with:

```python
    eligible_inputs = [
        input_
        for input_ in stage_item.inputs
        if isinstance(input_, StageItemInputFinal) and input_.team.active
    ]
    previous_match_hashes = get_previous_matches_hashes(stage_item.rounds)
    times_played_per_input = get_number_of_inputs_played_per_input(
        stage_item.rounds, frozenset()
    )
    courts = await get_all_courts_in_tournament(tournament_id)

    pairings = get_optimal_round_pairings(
        eligible_inputs,
        times_played_per_input,
        len(courts),
        previous_match_hashes,
        stage_item.pairing_mode,
    )
    if pairings is not None and len(pairings) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No more matches to schedule, all combinations of teams have been added already",
        )

    match_filter = MatchFilter(
        elo_diff_threshold=elo_diff_threshold,
        only_recommended=only_recommended,
        limit=1,
        iterations=iterations,
    )
    if pairings is None:
        # Too many teams for exact optimization: keep the old greedy path for this stage item.
        if len(get_upcoming_matches_for_swiss(match_filter, stage_item)) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No more matches to schedule, all combinations of teams have been added already",
            )

    stages = await get_full_tournament_details(tournament_id)
    existing_rounds = [
        round_
        for stage in stages
        for stage_item_ in stage.stage_items
        for round_ in stage_item_.rounds
    ]
    check_requirement(existing_rounds, user, "max_rounds")

    round_id = await sql_create_round(
        RoundInsertable(
            created=datetime_utc.now(),
            is_draft=True,
            stage_item_id=stage_item_id,
            name=await get_next_round_name(tournament_id, stage_item_id),
        ),
    )
    draft_round = await get_round_by_id(tournament_id, round_id)
    tournament = await sql_get_tournament(tournament_id)

    if pairings is None:
        # Greedy fallback, one match at a time.
        limit = len(courts) - len(draft_round.matches)
        for ___ in range(limit):
            stage_item = await get_stage_item(tournament_id, stage_item_id)
            draft_round = next(round_ for round_ in stage_item.rounds if round_.is_draft)
            all_matches_to_schedule = get_upcoming_matches_for_swiss(
                match_filter, stage_item, draft_round
            )
            if len(all_matches_to_schedule) < 1:
                break

            match = all_matches_to_schedule[0]
            assert isinstance(match, SuggestedMatch)
            assert draft_round.id and match.stage_item_input1.id and match.stage_item_input2.id
            await sql_create_match(
                MatchCreateBody(
                    round_id=draft_round.id,
                    stage_item_input1_id=match.stage_item_input1.id,
                    stage_item_input2_id=match.stage_item_input2.id,
                    court_id=None,
                    stage_item_input1_winner_from_match_id=None,
                    stage_item_input2_winner_from_match_id=None,
                    duration_minutes=tournament.duration_minutes,
                    margin_minutes=tournament.margin_minutes,
                    custom_duration_minutes=None,
                    custom_margin_minutes=None,
                ),
            )
    else:
        for input1, input2 in pairings:
            await sql_create_match(
                MatchCreateBody(
                    round_id=draft_round.id,
                    stage_item_input1_id=input1.id,
                    stage_item_input2_id=input2.id,
                    court_id=None,
                    stage_item_input1_winner_from_match_id=None,
                    stage_item_input2_winner_from_match_id=None,
                    duration_minutes=tournament.duration_minutes,
                    margin_minutes=tournament.margin_minutes,
                    custom_duration_minutes=None,
                    custom_margin_minutes=None,
                ),
            )
```

Keep the tail (rescheduling operations, `set_round_active_or_draft`, `handle_conflicts`)
unchanged. Add imports:

```python
from bracket.logic.scheduling.ladder_teams import (
    get_number_of_inputs_played_per_input,
    get_previous_matches_hashes,
)
from bracket.logic.scheduling.round_optimizer import get_optimal_round_pairings
```

(`StageItemInputFinal` is likely already imported; check.) Remove now-unused imports if any
linter flags them.

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/integration_tests/api/auto_scheduling_matches_test.py tests/integration_tests/api/stage_items_test.py tests/unit_tests/round_optimizer_test.py tests/unit_tests/swiss_test.py -v`
Expected: PASS (existing `swiss_test.py` and `test_start_next_round` must stay green)

- [ ] **Step 5: Full backend suite + linters**

Run: `cd backend && uv run pytest && uv run ruff format --check bracket/ tests/ && uv run ruff check bracket/ tests/ && uv run mypy bracket/ && uv run pylint bracket/ && uv run vulture bracket/`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add backend/bracket/routes/stage_items.py backend/tests/integration_tests/api/auto_scheduling_matches_test.py
git commit -m "feat: use exact round optimizer in Swiss start_next_round"
```

---

### Task 4: Frontend pairing-mode switch with explainer tooltip

**Files:**

- Create: `frontend/src/components/forms/pairing_mode_switch.tsx`
- Modify: `frontend/src/components/modals/create_stage_item.tsx` (form + submit + conditional render)
- Modify: `frontend/src/components/modals/update_stage_item.tsx` (form + submit + conditional render)
- Modify: `frontend/src/services/stage_item.tsx`
- Modify: `frontend/public/locales/en/common.json` (3 new keys)

**Interfaces:**

- Consumes: regenerated `StageItemWithRounds.pairing_mode` etc. from Task 1 Step 8.
- Produces: UI control; form field `pairing_mode_competitive: boolean`; API payload values `'COMPETITIVE'` / `'SOCIAL'`.

- [ ] **Step 1: Create the switch component**

Create `frontend/src/components/forms/pairing_mode_switch.tsx`:

```tsx
import { ActionIcon, Group, Switch, Tooltip } from '@mantine/core';
import { UseFormReturnType } from '@mantine/form';
import { IconInfoCircle } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

export function PairingModeSwitch({ form }: { form: UseFormReturnType<any> }) {
  const { t } = useTranslation();
  return (
    <Group mt="md" wrap="nowrap" align="center">
      <Switch
        label={t('pairing_mode_switch_label')}
        {...form.getInputProps('pairing_mode_competitive', { type: 'checkbox' })}
      />
      <Tooltip label={t('pairing_mode_tooltip')} multiline w={340} withArrow>
        <ActionIcon
          variant="subtle"
          color="gray"
          size="sm"
          aria-label={t('pairing_mode_switch_label')}
        >
          <IconInfoCircle size={18} />
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}
```

- [ ] **Step 2: Add i18n keys**

In `frontend/public/locales/en/common.json` add (keep the file's existing key ordering):

```json
"pairing_mode_switch_label": "Competitive pairing",
"pairing_mode_tooltip": "Off (social): everyone plays about equally often and opponents rotate fairly. On (competitive): teams with similar records face each other — winners vs winners — and weaker teams sit out more often.",
```

- [ ] **Step 3: Extend the service functions**

In `frontend/src/services/stage_item.tsx`:

```tsx
export async function createStageItem(
  tournament_id: number,
  stage_id: number,
  type: string,
  team_count: number,
  pairing_mode: string
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/stage_items`, {
      stage_id,
      type,
      team_count,
      pairing_mode,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function updateStageItem(
  tournament_id: number,
  stage_item_id: number,
  name: string,
  ranking_id: string,
  pairing_mode: string
) {
  return createAxios()
    .put(`tournaments/${tournament_id}/stage_items/${stage_item_id}`, {
      name,
      ranking_id,
      pairing_mode,
    })
    .catch((response: any) => handleRequestError(response));
}
```

- [ ] **Step 4: Wire into the create modal (Swiss only)**

In `frontend/src/components/modals/create_stage_item.tsx`:

- Add to `FormValues`: `pairing_mode_competitive: boolean;`
- Add to `initialValues`: `pairing_mode_competitive: false,`
- Change the submit call:

```tsx
await createStageItem(
  tournament.id,
  stage.id,
  values.type,
  getTeamCount(values),
  values.pairing_mode_competitive ? 'COMPETITIVE' : 'SOCIAL'
);
```

- Render below `<TeamCountInput form={form} />`:

```tsx
{form.values.type === 'SWISS' && <PairingModeSwitch form={form} />}
```

- Add import: `import { PairingModeSwitch } from '@components/forms/pairing_mode_switch';`

- [ ] **Step 5: Wire into the update modal (Swiss only)**

In `frontend/src/components/modals/update_stage_item.tsx`:

- Add to `initialValues`:

```tsx
      pairing_mode_competitive: stageItem.pairing_mode === 'COMPETITIVE',
```

- Change the submit call:

```tsx
await updateStageItem(
  tournament.id,
  stageItem.id,
  values.name,
  values.ranking_id,
  values.pairing_mode_competitive ? 'COMPETITIVE' : 'SOCIAL'
);
```

- Render below `<RankingSelect ... />`:

```tsx
{stageItem.type === 'SWISS' && <PairingModeSwitch form={form} />}
```

- Add imports: `PairingModeSwitch` as above. (`stageItem.type` / `stageItem.pairing_mode` come from the regenerated OpenAPI types; if `StageItemWithRounds` types `type` as an enum, compare against the enum value instead of the string literal.)

- [ ] **Step 6: Frontend checks**

Run: `cd frontend && pnpm test`
Expected: tsc + prettier clean

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/forms/pairing_mode_switch.tsx \
  frontend/src/components/modals/create_stage_item.tsx \
  frontend/src/components/modals/update_stage_item.tsx \
  frontend/src/services/stage_item.tsx \
  frontend/public/locales/en/common.json
git commit -m "feat: pairing mode switch with explainer tooltip in stage item modals"
```

---

### Task 5: Final verification

- [ ] **Step 1: Full backend suite and all linters (from `backend/`)**

```bash
uv run pytest
uv run ruff format --check bracket/ tests/ && uv run ruff check bracket/ tests/
uv run mypy bracket/ && uv run pyrefly check bracket/ && uv run pylint bracket/ && uv run vulture bracket/
```

- [ ] **Step 2: Frontend checks (from `frontend/`)**

```bash
pnpm test
```

- [ ] **Step 3: Stop the test database container**

```bash
podman stop bracket_ci_postgres && podman rm bracket_ci_postgres
```

- [ ] **Step 4: Push**

```bash
git push origin dev
```
