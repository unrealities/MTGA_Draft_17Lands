"""
tests/test_linux_log_discovery.py
Linux Player.log discovery across the launchers people actually use.

Before this, the Linux search list held a single hardcoded path
(~/.local/share/Steam/...), so Flatpak Steam -- the default on Fedora, Nobara
and Bazzite -- snap, Lutris, Bottles and secondary Steam libraries all fell back
to manual configuration.
"""

import os
import sys
import pytest

from src import constants
from src import file_extractor


APPDATA_TAIL = constants.LOG_LOCATION_APPDATA_SUFFIX


def _make_steam_log(home, steam_root):
    """Create a Player.log inside a Steam compatdata prefix."""
    path = os.path.join(
        home,
        steam_root,
        "steamapps",
        "compatdata",
        constants.MTGA_STEAM_APPID,
        "pfx",
        "drive_c",
        "users",
        "steamuser",
        APPDATA_TAIL,
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("DETAILED LOGS: ENABLED\n")
    return path


def _make_prefix_log(home, prefix, user="dorian"):
    """Create a Player.log inside a non-Steam Wine prefix."""
    path = os.path.join(home, prefix, "drive_c", "users", user, APPDATA_TAIL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("DETAILED LOGS: ENABLED\n")
    return path


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = str(tmp_path / "home")
    os.makedirs(home, exist_ok=True)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", home, 1))
    monkeypatch.setattr(sys, "platform", constants.PLATFORM_ID_LINUX)
    return home


@pytest.mark.parametrize(
    "steam_root",
    [
        os.path.join(".local", "share", "Steam"),
        os.path.join(".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
        os.path.join("snap", "steam", "common", ".local", "share", "Steam"),
        os.path.join(".steam", "root"),
    ],
    ids=["steam-native", "steam-flatpak", "steam-snap", "steam-root"],
)
def test_finds_log_under_each_steam_root(fake_home, steam_root):
    expected = _make_steam_log(fake_home, steam_root)
    assert file_extractor.search_arena_log_locations() == expected


@pytest.mark.parametrize(
    "prefix",
    [".wine", os.path.join("Games", "magic-the-gathering-arena")],
    ids=["plain-wine", "lutris"],
)
def test_finds_log_in_non_steam_prefix(fake_home, prefix):
    """The user directory is the real login name here, not 'steamuser'."""
    expected = _make_prefix_log(fake_home, prefix)
    assert file_extractor.search_arena_log_locations() == expected


def test_finds_log_in_secondary_steam_library(fake_home, tmp_path):
    """A game installed on a second drive, declared in libraryfolders.vdf."""
    library = str(tmp_path / "second_drive" / "SteamLibrary")
    path = os.path.join(
        library,
        "steamapps",
        "compatdata",
        constants.MTGA_STEAM_APPID,
        "pfx",
        "drive_c",
        "users",
        "steamuser",
        APPDATA_TAIL,
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").close()

    vdf_dir = os.path.join(fake_home, ".local", "share", "Steam", "config")
    os.makedirs(vdf_dir, exist_ok=True)
    with open(os.path.join(vdf_dir, "libraryfolders.vdf"), "w", encoding="utf-8") as f:
        f.write('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' % library)

    assert file_extractor.search_arena_log_locations() == path


def test_prefers_most_recently_written_log(fake_home):
    """Two prefixes, two logs: the one Arena is actually writing to wins."""
    old = _make_steam_log(fake_home, os.path.join(".local", "share", "Steam"))
    new = _make_steam_log(
        fake_home,
        os.path.join(".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"),
    )
    os.utime(old, (1000, 1000))
    os.utime(new, (2000, 2000))

    assert file_extractor.search_arena_log_locations() == new


def test_symlinked_flatpak_path_is_not_returned_twice(fake_home):
    """Flatpak links `data` -> `.local/share`; the same file must appear once."""
    flatpak_root = os.path.join(
        ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam"
    )
    real = _make_steam_log(fake_home, flatpak_root)

    link_parent = os.path.join(fake_home, ".var", "app", "com.valvesoftware.Steam")
    os.symlink(".local/share", os.path.join(link_parent, "data"))

    found = file_extractor.linux_arena_log_locations()
    assert found == [os.path.realpath(real)]


def test_returns_empty_when_nothing_installed(fake_home):
    assert file_extractor.search_arena_log_locations() == ""


def test_command_line_argument_still_wins(fake_home, tmp_path):
    _make_steam_log(fake_home, os.path.join(".local", "share", "Steam"))
    manual = str(tmp_path / "manual.log")
    open(manual, "w", encoding="utf-8").close()

    assert file_extractor.search_arena_log_locations(arg_location=manual) == manual
