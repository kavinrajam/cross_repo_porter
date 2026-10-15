"""
State management for cherry-pick operations.
Provides persistent state for resume capability.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field

from constants import CONFIG_DIR


STATE_FILE = CONFIG_DIR / ".cherry-pick-state.json"
STATE_BACKUP = CONFIG_DIR / ".cherry-pick-state.backup.json"


@dataclass
class CherryPickState:
    """Represents the state of a cherry-pick operation."""
    
    version: str = "2.0"
    source_repo: str = ""
    target_repo: str = ""
    source_branch: str = ""
    target_branch: str = ""
    base_commit: str = ""
    
    commits_to_apply: List[str] = field(default_factory=list)
    applied_commits: List[str] = field(default_factory=list)
    current_commit: Optional[str] = None
    
    status: str = "in_progress"  # in_progress, conflict, completed, aborted
    conflict_files: List[str] = field(default_factory=list)
    
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert state to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CherryPickState':
        """Create state from dictionary."""
        return cls(**data)
    
    def get_remaining_commits(self) -> List[str]:
        """Get list of commits still to be applied."""
        applied_set = set(self.applied_commits)
        return [c for c in self.commits_to_apply if c not in applied_set]
    
    def get_progress(self) -> tuple[int, int]:
        """Get progress as (completed, total)."""
        return len(self.applied_commits), len(self.commits_to_apply)
    
    def is_complete(self) -> bool:
        """Check if all commits have been applied."""
        return len(self.applied_commits) == len(self.commits_to_apply)
    
    def has_conflicts(self) -> bool:
        """Check if there are unresolved conflicts."""
        return self.status == "conflict" and len(self.conflict_files) > 0


class StateManager:
    """Manages persistent state for cherry-pick operations."""
    
    def __init__(self):
        """Initialize state manager."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def save(self, state: CherryPickState) -> None:
        """
        Save state to file atomically.
        
        Args:
            state: State to save
        """
        # Backup existing state if it exists
        if STATE_FILE.exists():
            shutil.copy2(STATE_FILE, STATE_BACKUP)
        
        # Update timestamp
        state.timestamp = datetime.utcnow().isoformat()
        
        # Write to temporary file first
        temp_file = STATE_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        
        # Atomic rename
        temp_file.replace(STATE_FILE)
    
    def load(self) -> Optional[CherryPickState]:
        """
        Load state from file.
        
        Returns:
            Loaded state or None if no state exists
        """
        if not STATE_FILE.exists():
            return None
        
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
            return CherryPickState.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            # Try backup if main file is corrupted
            if STATE_BACKUP.exists():
                try:
                    with open(STATE_BACKUP, 'r') as f:
                        data = json.load(f)
                    return CherryPickState.from_dict(data)
                except:
                    pass
            return None
    
    def exists(self) -> bool:
        """Check if a state file exists."""
        return STATE_FILE.exists()
    
    def clear(self) -> None:
        """Remove state file."""
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        if STATE_BACKUP.exists():
            STATE_BACKUP.unlink()
    
    def get_state_path(self) -> Path:
        """Get path to state file."""
        return STATE_FILE


class StateValidator:
    """Validates state consistency."""
    
    @staticmethod
    def validate(state: CherryPickState) -> tuple[bool, List[str]]:
        """
        Validate state for consistency.
        
        Args:
            state: State to validate
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Check required fields
        if not state.source_repo:
            errors.append("Source repository path is missing")
        if not state.target_repo:
            errors.append("Target repository path is missing")
        if not state.source_branch:
            errors.append("Source branch is missing")
        if not state.target_branch:
            errors.append("Target branch is missing")
        
        # Check commits
        if not state.commits_to_apply:
            errors.append("No commits to apply")
        
        # Check applied commits are subset of commits to apply
        applied_set = set(state.applied_commits)
        to_apply_set = set(state.commits_to_apply)
        if not applied_set.issubset(to_apply_set):
            errors.append("Applied commits contain commits not in the apply list")
        
        # Check current commit
        if state.current_commit and state.current_commit not in to_apply_set:
            errors.append("Current commit is not in the apply list")
        
        # Check status
        valid_statuses = ["in_progress", "conflict", "completed", "aborted"]
        if state.status not in valid_statuses:
            errors.append(f"Invalid status: {state.status}")
        
        # Check conflict state consistency
        if state.status == "conflict" and not state.conflict_files:
            errors.append("Status is 'conflict' but no conflict files listed")
        
        return len(errors) == 0, errors


def create_initial_state(
    source_repo: str,
    target_repo: str,
    source_branch: str,
    target_branch: str,
    commits: List[str],
    base_commit: str = ""
) -> CherryPickState:
    """
    Create initial state for a new cherry-pick operation.
    
    Args:
        source_repo: Path to source repository
        target_repo: Path to target repository
        source_branch: Source branch name
        target_branch: Target branch name
        commits: List of commit SHAs to apply
        base_commit: Base commit SHA
        
    Returns:
        New CherryPickState instance
    """
    return CherryPickState(
        source_repo=source_repo,
        target_repo=target_repo,
        source_branch=source_branch,
        target_branch=target_branch,
        base_commit=base_commit,
        commits_to_apply=commits,
        applied_commits=[],
        current_commit=commits[0] if commits else None,
        status="in_progress"
    )

# Made with Bob
