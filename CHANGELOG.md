# Changelog

All notable changes to cross-repo-porter will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-04

### 🎉 Major Redesign

Complete rewrite of the tool with a new architecture inspired by `git cherry-pick`.
Restructured as a proper Python package (`cross_repo_porter`).

### Added

- **Cherry-pick behavior**: Commits are now applied individually, preserving commit history
- **State management**: Persistent state tracking with resume capability
- **Merge commit support**: Correctly handles repositories with merge commits
- **Interactive conflict resolution**: Continue, skip, or abort operations
- **Dry-run mode**: Preview changes before applying
- **Status command**: Check current operation status
- **Better error messages**: Clear, actionable error messages
- **Progress indicators**: Visual feedback during operations
- **Proper Python package**: Installable via `pip install -e .` from the `cross_repo_porter/` directory

### Changed

- **Package layout**: All source files now live under `cross_repo_porter/` alongside project metadata
- **Architecture**: Modular design with separate concerns
  - `state.py`: State management with atomic writes
  - `repository.py`: Git operations abstraction
  - `path_transformer.py`: Configurable path transformations
  - `cherry_picker.py`: Core cherry-pick logic
- **Commit handling**: Individual commits instead of aggregated patches
- **Conflict resolution**: Uses native `git apply --3way` instead of `gpatch`
- **Path transformation**: More precise, only transforms diff headers
- **State tracking**: JSON state file instead of commit message metadata

### Removed

- **Old modules**: Removed obsolete implementation files
  - `Conflicts.py`
  - `patch_manager.py`
  - `source.py`
  - `target.py`
  - `path_set.py`
- **Aggregated commits**: No longer combines all commits into one

### Fixed

- **Merge commit handling**: Tool now works correctly with merged histories
- **State corruption**: Atomic writes with backup mechanism
- **Conflict detection**: Immediate detection without polling
- **Path transformation**: Only transforms paths, not content

## [0.1.2] - 2024-03-06

### Added
- Initial release
- Basic commit synchronization
- Path transformation for specs/ directory
- Conflict resolution with gpatch
- Commit tracking via last_commit_id

### Known Issues
- Breaks with merge commits in source repository
- Aggregates all commits into single commit
- Loses individual commit history
- Requires gpatch utility
