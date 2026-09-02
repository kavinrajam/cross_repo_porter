from pathlib import Path

# Config key names (stored in ~/.cross-repo-porter/.paths.json)
SOURCE_REPO_PATH = "SOURCE_REPO_PATH"
TARGET_REPO_PATH = "TARGET_REPO_PATH"
PATH_MAPPINGS = "PATH_MAPPINGS"       # dict of source_prefix -> target_prefix
DEFAULT_SOURCE_BRANCH = "DEFAULT_SOURCE_BRANCH"
DEFAULT_TARGET_BRANCH = "DEFAULT_TARGET_BRANCH"
LOGGING_NAME = "LOG_NAME"

# Filesystem location for all tool state and config
CONFIG_DIR = Path.home() / ".cross-repo-porter"
