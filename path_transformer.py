"""
Path transformation for cherry-pick operations.
Handles transformation of file paths between repositories.
"""

import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging


class PathTransformer:
    """Transforms file paths between source and target repositories."""

    def __init__(self, mappings: Dict[str, str], logger: Optional[logging.Logger] = None):
        """
        Initialize path transformer.

        Args:
            mappings: Dictionary of source_prefix -> target_prefix mappings.
                      Example: {"src/api/": "lib/openapi/"}
            logger: Optional logger instance
        """
        self.mappings = mappings
        self.logger = logger or logging.getLogger(__name__)

        # Compile regex patterns for efficient matching
        self._patterns = {}
        for source, target in mappings.items():
            escaped = re.escape(source)
            pattern = re.compile(f'^{escaped}')
            self._patterns[source] = (pattern, target)

    def transform_path(self, path: str) -> Tuple[str, bool]:
        """
        Transform a single path.

        Args:
            path: Path to transform

        Returns:
            Tuple of (transformed_path, was_transformed)
        """
        for source, (pattern, target) in self._patterns.items():
            if pattern.match(path):
                transformed = pattern.sub(target, path, count=1)
                self.logger.debug(f"Transformed: {path} -> {transformed}")
                return transformed, True

        return path, False

    def transform_paths(self, paths: List[str]) -> Dict[str, str]:
        """
        Transform multiple paths.

        Returns:
            Dictionary mapping original paths to transformed paths
        """
        result = {}
        for path in paths:
            transformed, _ = self.transform_path(path)
            result[path] = transformed
        return result

    def get_relevant_files(self, files: List[str]) -> List[str]:
        """Return files that match at least one source mapping prefix."""
        relevant = []
        for file in files:
            for source in self.mappings.keys():
                if file.startswith(source):
                    relevant.append(file)
                    break
        return relevant

    def has_relevant_files(self, files: List[str]) -> bool:
        """Return True if any file matches a source mapping prefix."""
        return len(self.get_relevant_files(files)) > 0


class PatchTransformer:
    """Transforms git patch files to use different paths."""

    def __init__(self, path_transformer: PathTransformer, logger: Optional[logging.Logger] = None):
        self.path_transformer = path_transformer
        self.logger = logger or logging.getLogger(__name__)

    def transform_patch_file(self, patch_path: Path) -> Tuple[bool, List[str]]:
        """
        Transform paths in a patch file in-place.

        Returns:
            Tuple of (was_modified, list of transformed source paths)
        """
        with open(patch_path, 'r', encoding='utf-8') as f:
            content = f.read()

        transformed_content, modified_paths = self._transform_patch_content(content)

        if modified_paths:
            with open(patch_path, 'w', encoding='utf-8') as f:
                f.write(transformed_content)
            self.logger.info(f"Transformed {len(modified_paths)} paths in {patch_path.name}")
            return True, modified_paths

        return False, []

    def _transform_patch_content(self, content: str) -> Tuple[str, List[str]]:
        lines = content.split('\n')
        modified_paths = []

        for i, line in enumerate(lines):
            # Transform paths in git diff header: diff --git a/... b/...
            if line.startswith('diff --git a/'):
                match = re.match(r'^diff --git a/(.*) b/(.*)$', line)
                if match:
                    path_a, path_b = match.group(1), match.group(2)
                    transformed_a, was_a = self.path_transformer.transform_path(path_a)
                    transformed_b, was_b = self.path_transformer.transform_path(path_b)
                    if was_a or was_b:
                        lines[i] = f"diff --git a/{transformed_a} b/{transformed_b}"
                        if was_a and path_a not in modified_paths:
                            modified_paths.append(path_a)
                        if was_b and path_b not in modified_paths:
                            modified_paths.append(path_b)

            # Transform paths in diff headers
            elif line.startswith('--- a/'):
                path = line[6:]
                transformed, was_transformed = self.path_transformer.transform_path(path)
                if was_transformed:
                    lines[i] = '--- a/' + transformed
                    if path not in modified_paths:
                        modified_paths.append(path)

            elif line.startswith('+++ b/'):
                path = line[6:]
                transformed, was_transformed = self.path_transformer.transform_path(path)
                if was_transformed:
                    lines[i] = '+++ b/' + transformed
                    if path not in modified_paths:
                        modified_paths.append(path)

            # Transform paths in rename/copy headers
            elif line.startswith('rename from ') or line.startswith('copy from '):
                parts = line.split(' ', 2)
                path = parts[2]
                transformed, was_transformed = self.path_transformer.transform_path(path)
                if was_transformed:
                    lines[i] = ' '.join(parts[:2]) + ' ' + transformed
                    if path not in modified_paths:
                        modified_paths.append(path)

            elif line.startswith('rename to ') or line.startswith('copy to '):
                parts = line.split(' ', 2)
                path = parts[2]
                transformed, was_transformed = self.path_transformer.transform_path(path)
                if was_transformed:
                    lines[i] = ' '.join(parts[:2]) + ' ' + transformed
                    if path not in modified_paths:
                        modified_paths.append(path)

        return '\n'.join(lines), modified_paths

    def should_apply_patch(self, patch_path: Path) -> bool:
        """Return True if the patch contains files matching any source prefix."""
        with open(patch_path, 'r', encoding='utf-8') as f:
            content = f.read()

        files = []
        for line in content.split('\n'):
            if line.startswith('--- a/'):
                path = line[6:]
                if path != '/dev/null':
                    files.append(path)

        return self.path_transformer.has_relevant_files(files)


def create_transformer_from_config(config, logger: Optional[logging.Logger] = None) -> PathTransformer:
    """
    Create a PathTransformer using mappings stored in the config file.

    Args:
        config: ConfigManager instance
        logger: Optional logger instance

    Returns:
        PathTransformer instance

    Raises:
        ValueError: If no path mappings are configured
    """
    mappings = config.get_path_mappings()
    if not mappings:
        raise ValueError(
            "No path mappings configured.\n"
            "Add one with:  porter config --add-mapping <source-prefix> <target-prefix>\n"
            "Example:       porter config --add-mapping src/api/ lib/openapi/"
        )
    return PathTransformer(mappings, logger)
