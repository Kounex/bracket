from bracket.logic.teams import build_auto_team_name, is_auto_team_name


def test_build_auto_team_name_from_players_sorted_alphabetically() -> None:
    assert build_auto_team_name(["Bob", "Alice"], set()) == "Alice / Bob"


def test_build_auto_team_name_single_player() -> None:
    assert build_auto_team_name(["Alice"], set()) == "Alice"


def test_build_auto_team_name_without_players() -> None:
    assert build_auto_team_name([], set()) == "Team 1"


def test_build_auto_team_name_without_players_avoids_taken_numbers() -> None:
    assert build_auto_team_name([], {"Team 1", "Team 2"}) == "Team 3"


def test_build_auto_team_name_deduplicates_with_suffix() -> None:
    assert build_auto_team_name(["Alice", "Bob"], {"Alice / Bob"}) == "Alice / Bob (2)"
    assert (
        build_auto_team_name(["Alice", "Bob"], {"Alice / Bob", "Alice / Bob (2)"})
        == "Alice / Bob (3)"
    )


def test_build_auto_team_name_truncates_long_names() -> None:
    long_name = "A very long player name that exceeds the limit"
    result = build_auto_team_name([long_name, "Bob"], set())
    assert len(result) <= 30
    assert result == "A very long player name that e"


def test_is_auto_team_name_matches_derivation() -> None:
    assert is_auto_team_name("Alice / Bob", ["Bob", "Alice"], set()) is True
    assert is_auto_team_name("Team 1", [], set()) is True


def test_is_auto_team_name_matches_suffixed_derivation() -> None:
    assert is_auto_team_name("Alice / Bob (2)", ["Alice", "Bob"], {"Alice / Bob"}) is True


def test_is_auto_team_name_rejects_custom_name() -> None:
    assert is_auto_team_name("The Smashers", ["Alice", "Bob"], set()) is False
    assert is_auto_team_name("Alice / Bob!", ["Alice", "Bob"], set()) is False
