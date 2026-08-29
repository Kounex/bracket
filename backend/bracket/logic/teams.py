import aiofiles.os

from bracket.models.db.team import FullTeamWithPlayers
from bracket.sql.players import get_players_by_id
from bracket.sql.teams import get_team_by_id, get_team_names, sql_update_team_name
from bracket.utils.id_types import PlayerId, TeamId, TournamentId

MAX_TEAM_NAME_LENGTH = 30  # matches the StringConstraints on TeamBody.name


def build_auto_team_name(player_names: list[str], existing_names: set[str]) -> str:
    """Derive a unique team name from player names, falling back to 'Team N'."""
    if len(player_names) > 0:
        base = " / ".join(sorted(player_names))
    else:
        number = 1
        while f"Team {number}" in existing_names:
            number += 1
        base = f"Team {number}"

    name = base[:MAX_TEAM_NAME_LENGTH]
    suffix = 2
    while name in existing_names:
        suffix_str = f" ({suffix})"
        name = f"{base[: MAX_TEAM_NAME_LENGTH - len(suffix_str)]}{suffix_str}"
        suffix += 1
    return name


def is_auto_team_name(name: str, player_names: list[str], other_team_names: set[str]) -> bool:
    """Check whether a team name is the untouched result of auto-derivation."""
    return name == build_auto_team_name(player_names, other_team_names)


async def resolve_team_name(
    tournament_id: TournamentId,
    name: str,
    player_ids: set[PlayerId],
    team: FullTeamWithPlayers | None = None,
) -> str:
    """Resolve the name for a team create/update: blank names, and unchanged auto-derived
    names, are (re-)derived from the players."""
    other_names = await get_team_names(tournament_id)
    if team is not None:
        other_names.discard(team.name)

    stripped = name.strip()
    if stripped and (
        team is None
        or stripped != team.name
        or not is_auto_team_name(team.name, [p.name for p in team.players], other_names)
    ):
        return stripped

    player_names = [p.name for p in await get_players_by_id(player_ids, tournament_id)]
    return build_auto_team_name(player_names, other_names)


async def rederive_auto_team_names_for_player(
    tournament_id: TournamentId,
    player_id: PlayerId,
    new_player_name: str | None,
    teams_of_player: list[FullTeamWithPlayers],
) -> None:
    """Re-derive auto-generated team names after a player rename (new_player_name set)
    or removal (new_player_name is None). Teams with custom names are untouched.

    `teams_of_player` must be a snapshot taken before the player change.
    """
    all_names = await get_team_names(tournament_id)
    for team in teams_of_player:
        other_names = all_names - {team.name}
        if not is_auto_team_name(team.name, [p.name for p in team.players], other_names):
            continue

        new_player_names: list[str] = []
        for player in team.players:
            if player.id != player_id:
                new_player_names.append(player.name)
            elif new_player_name is not None:
                new_player_names.append(new_player_name)
        new_name = build_auto_team_name(new_player_names, other_names)
        await sql_update_team_name(tournament_id, team.id, new_name)
        all_names = other_names | {new_name}


async def get_team_logo_path(tournament_id: TournamentId, team_id: TeamId) -> str | None:
    team = await get_team_by_id(team_id, tournament_id)
    logo_path = (
        f"static/team-logos/{team.logo_path}"
        if team is not None and team.logo_path is not None
        else None  # pylint: disable=line-too-long
    )
    return logo_path if logo_path is not None and await aiofiles.os.path.exists(logo_path) else None
