"""
Configuration management for cross-repo-porter.
Stores repository paths, default branches, and path mappings.
"""

import json
from typing import Dict, Optional

from cross_repo_porter.constants import (
    CONFIG_DIR,
    SOURCE_REPO_PATH,
    TARGET_REPO_PATH,
    PATH_MAPPINGS,
    DEFAULT_SOURCE_BRANCH,
    DEFAULT_TARGET_BRANCH,
    LOGGING_NAME,
)

CONFIG_PATH = CONFIG_DIR / ".paths.json"


def _empty_config() -> dict:
    return {
        SOURCE_REPO_PATH: "",
        TARGET_REPO_PATH: "",
        PATH_MAPPINGS: {},
        DEFAULT_SOURCE_BRANCH: "",
        DEFAULT_TARGET_BRANCH: "",
        LOGGING_NAME: "",
    }


class ConfigManager:

    def _ensure_config_file(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_PATH.exists():
            with CONFIG_PATH.open("w") as f:
                json.dump(_empty_config(), f, indent=4)

    def __init__(self, initial: bool = False):
        if initial:
            self._ensure_config_file()
        with open(CONFIG_PATH, "r") as f:
            self.config = json.load(f)

    # ------------------------------------------------------------------ #
    # Getters                                                              #
    # ------------------------------------------------------------------ #

    def get_source(self) -> Optional[str]:
        return self.config.get(SOURCE_REPO_PATH) or None

    def get_target(self) -> Optional[str]:
        return self.config.get(TARGET_REPO_PATH) or None

    def get_path_mappings(self) -> Dict[str, str]:
        """Return the dict of source_prefix -> target_prefix path mappings."""
        return self.config.get(PATH_MAPPINGS, {})

    def get_default_source_branch(self) -> Optional[str]:
        return self.config.get(DEFAULT_SOURCE_BRANCH) or None

    def get_default_target_branch(self) -> Optional[str]:
        return self.config.get(DEFAULT_TARGET_BRANCH) or None

    # ------------------------------------------------------------------ #
    # Setters                                                              #
    # ------------------------------------------------------------------ #

    def set_source(self, value: str) -> None:
        self._set(SOURCE_REPO_PATH, value)

    def set_target(self, value: str) -> None:
        self._set(TARGET_REPO_PATH, value)

    def set_path_mappings(self, mappings: Dict[str, str]) -> None:
        self._set(PATH_MAPPINGS, mappings)

    def add_path_mapping(self, source_prefix: str, target_prefix: str) -> None:
        """Add or overwrite a single path mapping."""
        self._reload()
        mappings = self.config.get(PATH_MAPPINGS, {})
        mappings[source_prefix] = target_prefix
        self.config[PATH_MAPPINGS] = mappings
        self._flush()

    def remove_path_mapping(self, source_prefix: str) -> bool:
        """Remove a path mapping. Returns True if it existed."""
        self._reload()
        mappings = self.config.get(PATH_MAPPINGS, {})
        if source_prefix not in mappings:
            return False
        del mappings[source_prefix]
        self.config[PATH_MAPPINGS] = mappings
        self._flush()
        return True

    def set_default_source_branch(self, value: str) -> None:
        self._set(DEFAULT_SOURCE_BRANCH, value)

    def set_default_target_branch(self, value: str) -> None:
        self._set(DEFAULT_TARGET_BRANCH, value)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _reload(self) -> None:
        with open(CONFIG_PATH, "r") as f:
            self.config = json.load(f)

    def _flush(self) -> None:
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=4)

    def _set(self, key: str, value) -> None:
        self._reload()
        self.config[key] = value
        self._flush()
