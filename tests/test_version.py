"""Version et informations de fabrication (Q18, Design Book v0.43)."""

import json
import re
from datetime import date

import scenix16
from scenix16.paths import resources_dir
from scenix16.version import (BUILD_INFO_NAME, FILE_VERSION, build_info_payload, load_build_info)


def test_version_follows_q18_without_roadmap_step():
    assert scenix16.__version__ == "0.1.0-dev"
    assert re.fullmatch(r"\d+\.\d+\.\d+(-(dev|rc\.\d+))?", scenix16.__version__)
    assert "2.6" not in scenix16.__version__                    # aucune étape de la feuille de route
    assert FILE_VERSION == (0, 1, 0, 0)                          # quatre nombres pour Windows


def test_sources_have_no_build_info():
    assert not (resources_dir() / BUILD_INFO_NAME).exists()     # jamais écrit dans les sources
    assert load_build_info() is None                             # → « Version de développement »


def test_build_info_round_trip(tmp_path):
    path = tmp_path / BUILD_INFO_NAME
    path.write_text(json.dumps(build_info_payload(date(2026, 11, 7), "a83e126", True)), encoding="utf-8")
    info = load_build_info(path)
    assert (info.built_on, info.commit, info.local_changes) == (date(2026, 11, 7), "a83e126", True)


def test_unreadable_build_info_is_ignored(tmp_path):
    path = tmp_path / BUILD_INFO_NAME
    path.write_text("{pas du json", encoding="utf-8")
    assert load_build_info(path) is None
    path.write_text(json.dumps({"built_on": "2026-11-07"}), encoding="utf-8")
    assert load_build_info(path) is None
