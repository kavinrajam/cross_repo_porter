"""
Core cherry-pick logic for syncing commits between repositories.
Similar to git cherry-pick but with path transformation support.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import logging

from cross_repo_porter.repository import GitRepository, RepositoryPair, CommitInfo
from cross_repo_porter.path_transformer import PathTransformer, PatchTransformer
from cross_repo_porter.state import CherryPickState, StateManager


class CherryPickError(Exception):
    """Base exception for cherry-pick operations."""
    pass


class ConflictError(CherryPickError):
    """Exception raised when conflicts occur during cherry-pick."""
    
    def __init__(self, message: str, conflicted_files: List[str]):
        super().__init__(message)
        self.conflicted_files = conflicted_files


class CherryPicker:
    """Handles cherry-picking commits with path transformation."""
    
    def __init__(
        self,
        repos: RepositoryPair,
        path_transformer: PathTransformer,
        state_manager: StateManager,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize cherry picker.
        
        Args:
            repos: Repository pair (source and target)
            path_transformer: Path transformer instance
            state_manager: State manager instance
            logger: Optional logger instance
        """
        self.repos = repos
        self.path_transformer = path_transformer
        self.patch_transformer = PatchTransformer(path_transformer, logger)
        self.state_manager = state_manager
        self.logger = logger or logging.getLogger(__name__)
        self.temp_dir = None
    
    def cherry_pick_commit(
        self,
        commit_sha: str,
        preserve_author: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Cherry-pick a single commit with path transformation.
        
        Args:
            commit_sha: SHA of commit to cherry-pick
            preserve_author: Preserve original author information
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get commit info
            commit_info = self.repos.source.get_commit_info(commit_sha)
            self.logger.info(f"Cherry-picking {commit_info.short_sha}: {commit_info.message[:50]}")
            
            # Check if commit has relevant files
            relevant_files = self.path_transformer.get_relevant_files(commit_info.files_changed)
            if not relevant_files:
                self.logger.info(f"Skipping {commit_info.short_sha}: no relevant files")
                return True, None
            
            # Create temporary directory for patch
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp(prefix='wsapi-porter-')
            
            # Generate patch file
            patch_path = Path(self.temp_dir) / f"{commit_info.short_sha}.patch"
            self._generate_patch(commit_sha, patch_path)
            
            # Transform paths in patch
            self.patch_transformer.transform_patch_file(patch_path)
            
            # Apply patch
            success, error = self._apply_patch(patch_path)
            
            if not success:
                # Check for conflicts
                conflicted = self.repos.target.get_conflicted_files()
                if conflicted:
                    raise ConflictError(
                        f"Conflicts in {len(conflicted)} file(s)",
                        conflicted
                    )
                return False, error
            
            # Create commit with original metadata
            if preserve_author:
                commit_sha = self.repos.target.commit(
                    message=commit_info.message,
                    author=commit_info.author,
                    date=commit_info.date
                )
            else:
                commit_sha = self.repos.target.commit(message=commit_info.message)
            
            self.logger.info(f"Successfully cherry-picked as {commit_sha[:7]}")
            return True, None
            
        except ConflictError:
            raise
        except Exception as e:
            self.logger.error(f"Error cherry-picking {commit_sha}: {e}")
            return False, str(e)
    
    def _generate_patch(self, commit_sha: str, output_path: Path) -> None:
        """
        Generate patch file for a commit.
        
        Args:
            commit_sha: Commit SHA
            output_path: Path to write patch file
        """
        result = subprocess.run(
            ["git", "format-patch", "-1", commit_sha, "--stdout", "--full-index"],
            cwd=self.repos.source.path,
            capture_output=True,
            text=True,
            check=True
        )
        
        output_path.write_text(result.stdout)
        self.logger.debug(f"Generated patch: {output_path}")
    
    def _apply_patch(self, patch_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Apply patch file to target repository.
        
        Args:
            patch_path: Path to patch file
            
        Returns:
            Tuple of (success, error_message)
        """
        # Try to apply with 3-way merge
        result = subprocess.run(
            ["git", "apply", "--3way", "--index", str(patch_path)],
            cwd=self.repos.target.path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return True, None
        
        # Check if it's a conflict or other error
        if "conflict" in result.stderr.lower() or "conflict" in result.stdout.lower():
            return False, "Conflicts detected"
        
        return False, result.stderr or result.stdout
    
    def cherry_pick_range(
        self,
        commits: List[str],
        state: CherryPickState
    ) -> Tuple[bool, Optional[str]]:
        """
        Cherry-pick a range of commits.
        
        Args:
            commits: List of commit SHAs to cherry-pick
            state: Current state
            
        Returns:
            Tuple of (success, error_message)
        """
        for i, commit_sha in enumerate(commits, 1):
            # Update state
            state.current_commit = commit_sha
            self.state_manager.save(state)
            
            self.logger.info(f"[{i}/{len(commits)}] Processing {commit_sha[:7]}")
            
            try:
                success, error = self.cherry_pick_commit(commit_sha)
                
                if not success:
                    return False, error
                
                # Mark as applied
                state.applied_commits.append(commit_sha)
                self.state_manager.save(state)
                
            except ConflictError as e:
                # Save conflict state
                state.status = "conflict"
                state.conflict_files = e.conflicted_files
                self.state_manager.save(state)
                raise
        
        # All commits applied successfully
        state.status = "completed"
        state.current_commit = None
        self.state_manager.save(state)
        
        return True, None
    
    def continue_cherry_pick(self, state: CherryPickState) -> Tuple[bool, Optional[str]]:
        """
        Continue cherry-pick after resolving conflicts.
        
        Args:
            state: Current state
            
        Returns:
            Tuple of (success, error_message)
        """
        # Check if conflicts are resolved
        if self.repos.target.has_conflicts():
            return False, "Conflicts not resolved. Please resolve conflicts and stage files."
        
        # Check if files are staged
        if not self.repos.target.repo.is_dirty(index=True, working_tree=False):
            return False, "No staged changes. Please stage resolved files with 'git add'."
        
        # Get current commit info
        if not state.current_commit:
            return False, "No current commit in state"
        
        commit_info = self.repos.source.get_commit_info(state.current_commit)
        
        # Create commit
        commit_sha = self.repos.target.commit(
            message=commit_info.message,
            author=commit_info.author,
            date=commit_info.date
        )
        
        self.logger.info(f"Continued cherry-pick: {commit_sha[:7]}")
        
        # Mark current commit as applied
        state.applied_commits.append(state.current_commit)
        state.status = "in_progress"
        state.conflict_files = []
        
        # Get remaining commits
        remaining = state.get_remaining_commits()
        
        if remaining:
            # Continue with remaining commits
            return self.cherry_pick_range(remaining, state)
        else:
            # All done
            state.status = "completed"
            state.current_commit = None
            self.state_manager.save(state)
            return True, None
    
    def abort_cherry_pick(self, state: CherryPickState) -> None:
        """
        Abort cherry-pick operation.
        
        Args:
            state: Current state
        """
        self.logger.info("Aborting cherry-pick")
        
        # Reset to state before cherry-pick
        if state.applied_commits:
            # Reset to before first applied commit
            self.repos.target.reset_hard("HEAD~" + str(len(state.applied_commits)))
        
        # Clean working directory
        self.repos.target.clean()
        
        # Clear state
        state.status = "aborted"
        self.state_manager.save(state)
        
        self.logger.info("Cherry-pick aborted")
    
    def skip_commit(self, state: CherryPickState) -> Tuple[bool, Optional[str]]:
        """
        Skip current commit and continue with next.
        
        Args:
            state: Current state
            
        Returns:
            Tuple of (success, error_message)
        """
        if not state.current_commit:
            return False, "No current commit to skip"
        
        self.logger.info(f"Skipping commit {state.current_commit[:7]}")
        
        # Reset working directory
        self.repos.target.reset_hard("HEAD")
        self.repos.target.clean()
        
        # Mark as applied (skipped)
        state.applied_commits.append(state.current_commit)
        state.status = "in_progress"
        state.conflict_files = []
        
        # Get remaining commits
        remaining = state.get_remaining_commits()
        
        if remaining:
            return self.cherry_pick_range(remaining, state)
        else:
            state.status = "completed"
            state.current_commit = None
            self.state_manager.save(state)
            return True, None
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_dir and Path(self.temp_dir).exists():
            import shutil
            shutil.rmtree(self.temp_dir)
            self.logger.debug(f"Cleaned up temp directory: {self.temp_dir}")

# Made with Bob
