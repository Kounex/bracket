# Design: Global Swiss round optimizer + pairing mode

Date: 2026-09-01
Status: approved by user (design phase)

## Problem

Bracket's Swiss auto-scheduler fills a draft round greedily, one match at a time
(`backend/bracket/routes/stage_items.py`, `activate_next_stage_item`), picking each match from
suggestions sorted by `times_played_sum` first and `elo_diff` second
(`backend/bracket/logic/scheduling/ladder_teams.py:139-140`). Consequences, observed on real data
(DR Cup, 18 teams, 5 courts, 10 rounds):

- Match-count fairness strictly dominates pairing strength: a 4-0 leader got paired against a
  0-win team (round 8) while the other 4-0 team sat out.
- The greedy loop has no global view of the round; pairings within the selected participants are
  near-optimal, but participant selection is not strength-aware.
- There is no way for an organizer to choose "winners play winners" (classic Swiss behavior).

## Goals

- Globally optimize each auto-scheduled Swiss round: participant selection and pairings together.
- Let the organizer choose the pairing philosophy per Swiss stage item: `social` (default,
  current fairness-first behavior) or `competitive` (strength-first, classic Swiss style).
- No behavior change for existing tournaments after upgrade.

## Non-goals

- Changing the manual scheduling suggestion endpoint (`upcoming_matches`) semantics.
- Changing ELO/rating calculation (`backend/bracket/logic/ranking/calculation.py`).
- Touching other stage types (ROUND_ROBIN, SINGLE_ELIMINATION).

## Data model

- New column on `stage_items`: `pairing_mode TEXT NOT NULL DEFAULT 'social'`.
- New enum `PairingMode` (`social` | `competitive`), following the existing `EnumAutoStr`
  pattern used by `StageType`.
- Alembic migration adds the column; existing rows get `social`.
- `StageItemInsertable` / `StageItem` gain `pairing_mode: PairingMode` (default `SOCIAL`).
- `StageItemCreateBody` gains optional `pairing_mode` (default `SOCIAL`).
- `StageItemUpdateBody` gains `pairing_mode: PairingMode`; the update route
  (`PUT /tournaments/{id}/stage_items/{stage_item_id}`) currently only writes `name` and must be
  extended to also persist `pairing_mode`.
- Regenerate `backend/openapi/openapi.json` and `frontend/src/openapi/**` per AGENTS.md.

## Optimizer

New module `backend/bracket/logic/scheduling/round_optimizer.py` with one public function:

```python
def get_optimal_swiss_round(
    inputs: list[StageItemInput],       # active, not yet in the draft round
    courts_count: int,
    previous_match_hashes: frozenset[str],
    mode: PairingMode,
) -> list[tuple[StageItemInput, StageItemInput]]
```

Algorithm:

- Exact bitmask DP over teams: states `2^N` for N candidate teams. Each transition either leaves
  a team out of this round or pairs it with another team, subject to:
  - exactly `min(2 * courts_count, N // 2 * 2)` participants,
  - no pair whose match hash is in `previous_match_hashes` (no rematches),
  - each team plays at most once.
- Single cost function, mode-dependent weights:
  `cost = fairness_weight * sum(played counts of participants) + sum(|elo diff| of each match)`
  - `social`: `fairness_weight` is large (must exceed any possible sum of ELO diffs, e.g. 10x
    max rating range times matches) so match-count equalization dominates, then pairing is
    globally optimal within that. Reproduces today's fairness with better pairings.
  - `competitive`: `fairness_weight` near zero (tiebreak only), so cost is essentially the sum of
    ELO diffs: winners vs winners; byes fall to the bottom of the standings.
- Cap: if N > 24 (2^24 states is the practical ceiling), fall back to the existing greedy
  suggestion loop. The cap is a constant documented in the module.
- Ratings come from `StageItemInput.elo` (live points), same source as the current suggester.

## Wire-in

- `activate_next_stage_item` (`backend/bracket/routes/stage_items.py:140-216`): replace the
  greedy `for` loop over courts with one call to `get_optimal_swiss_round`, then create the
  returned matches. Everything else (round creation, court assignment, response) stays.
- The `elo_diff_threshold` / `only_recommended` / `iterations` query params on that route become
  unused for the optimized path; they still apply to the N > 24 fallback and to the manual
  `upcoming_matches` endpoint. The threshold must never prevent the auto-scheduler from
  completing a round (optimizer has no ELO cutoff).

## Frontend

- `frontend/src/components/modals/create_stage_item.tsx` and `update_stage_item.tsx`: when the
  stage item type is SWISS, show a `Switch` labeled "Pairing mode" (checked = competitive),
  with an `IconInfoCircle` `ActionIcon` inside/next to the label that opens a hover `Tooltip`:
  - Social: "Everyone plays about equally often. Opponents rotate fairly."
  - Competitive: "Teams with similar records face each other (winners vs winners). Weaker teams
    sit out more often."
- The update modal pre-fills from `stageItem.pairing_mode`; the create modal defaults to social.
- `frontend/src/services/stage_item.tsx`: extend `createStageItem` / `updateStageItem` payloads.
- New i18n keys in `frontend/public/locales/en/common.json` (label + both tooltip strings);
  other locales fall back to English automatically.

## Testing

- Unit tests (`backend/tests/unit_tests/logic/round_optimizer_test.py` or matching existing test
  layout):
  - participant count = exactly 2 x courts (or all teams if fewer),
  - no rematches, no team twice in a round,
  - social mode keeps per-team played counts within +/- 1 of each other,
  - competitive mode: given two 4-0 teams and weaker teams (the DR Cup round-8 reconstruction),
    the two leaders are paired together; social mode does not guarantee that.
- Integration test: `activate_next_stage_item` for both modes on a small Swiss stage item.
- Migration: covered by existing alembic/test setup; verify `test_openapi_up_to_date` passes
  after regenerating the spec.
- Frontend: `pnpm test` (tsc + prettier). No component test infra exists; manual check of the
  two modals.

## Rollout

- Single feature branch off `dev`, PR-free flow (commit to `dev` directly, per repo convention).
- No release needed until user asks; NAS deployment is manual via image tag bump.
