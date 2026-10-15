"""
Git repository abstraction layer.
Provides high-level operations for both source and target repositories.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Set
from dataclasses import dataclass
from git import Repo, Commit, GitCommandError
import logging


@dataclass
class CommitInfo:
    """Information about a commit."""
    sha: str
    short_sha: str
    message: str
    author: str
    date: str
    files_changed: List[str]
    
    @classmethod
    def from_commit(cls, commit: Commit) -> 'CommitInfo':
        """Create CommitInfo from GitPython Commit object."""
        message = commit.message if isinstance(commit.message, str) else commit.message.decode('utf-8')
        return cls(
            sha=commit.hexsha,
            short_sha=commit.hexsha[:7],
            message=message.strip(),
            author=f"{commit.author.name} <{commit.author.email}>",
            date=commit.committed_datetime.isoformat(),
            files_changed=[str(f) for f in commit.stats.files.keys()]
        )
    
    def has_relevant_files(self, path_prefix: str) -> bool:
        """Check if commit has files matching the path prefix."""
        return any(f.startswith(path_prefix) for f in self.files_changed)
    
    def get_relevant_files(self, path_prefix: str) -> List[str]:
        """Get list of files matching the path prefix."""
        return [f for f in self.files_changed if f.startswith(path_prefix)]


class GitRepository:
    """Wrapper around GitPython Repo with high-level operations."""
    
    def __init__(self, path: str, logger: Optional[logging.Logger] = None):
        """
        Initialize repository.
        
        Args:
            path: Path to repository
            logger: Optional logger instance
        """
        self.path = Path(path)
        self.repo = Repo(path)
        self.logger = logger or logging.getLogger(__name__)
    
    def is_dirty(self) -> bool:
        """Check if repository has uncommitted changes."""
        return self.repo.is_dirty(untracked_files=True)
    
    def get_current_branch(self) -> str:
        """Get name of current branch."""
        return self.repo.active_branch.name
    
    def branch_exists(self, branch_name: str) -> bool:
        """Check if branch exists."""
        return branch_name in [b.name for b in self.repo.heads]
    
    def checkout_branch(self, branch_name: str, create: bool = False) -> None:
        """
        Checkout a branch.
        
        Args:
            branch_name: Name of branch to checkout
            create: Create branch if it doesn't exist
        """
        if create and not self.branch_exists(branch_name):
            self.repo.create_head(branch_name)
        
        branch = self.repo.heads[branch_name]
        branch.checkout()
        self.logger.info(f"Checked out branch: {branch_name}")
    
    def create_branch(self, branch_name: str, start_point: Optional[str] = None, track: bool = False) -> None:
        """
        Create a new branch.
        
        Args:
            branch_name: Name of new branch
            start_point: Starting point (branch/commit), defaults to HEAD
            track: Set up tracking to the start_point (if it is a remote or tracking branch)
        """
        if self.branch_exists(branch_name):
            raise ValueError(f"Branch {branch_name} already exists")
        
        if track and start_point:
            self.repo.git.branch('--track', branch_name, start_point)
        elif start_point:
            self.repo.create_head(branch_name, start_point)
        else:
            self.repo.create_head(branch_name)
        
        self.logger.info(f"Created branch: {branch_name}")
    
    def delete_branch(self, branch_name: str, force: bool = False) -> None:
        """
        Delete a branch.
        
        Args:
            branch_name: Name of branch to delete
            force: Force deletion even if not merged
        """
        if not self.branch_exists(branch_name):
            raise ValueError(f"Branch {branch_name} does not exist")
        
        self.repo.delete_head(branch_name, force=force)
        self.logger.info(f"Deleted branch: {branch_name}")
    
    def fetch(self, remote: str = "origin") -> None:
        """Fetch from remote."""
        self.repo.remotes[remote].fetch()
        self.logger.info(f"Fetched from {remote}")
    
    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> None:
        """
        Pull from remote.
        
        Args:
            remote: Remote name
            branch: Branch name, defaults to current branch
        """
        if branch:
            self.repo.remotes[remote].pull(branch)
        else:
            self.repo.remotes[remote].pull()
        self.logger.info(f"Pulled from {remote}")
    
    def get_commit(self, sha: str) -> Commit:
        """Get commit by SHA."""
        return self.repo.commit(sha)
    
    def get_commit_info(self, sha: str) -> CommitInfo:
        """Get commit information."""
        commit = self.get_commit(sha)
        return CommitInfo.from_commit(commit)
    
    def get_commits_between(self, base: str, head: str) -> List[CommitInfo]:
        """
        Get commits between base and head.
        
        Args:
            base: Base commit/branch
            head: Head commit/branch
            
        Returns:
            List of CommitInfo objects in chronological order
        """
        commits = list(self.repo.iter_commits(f"{base}..{head}"))
        # Reverse to get chronological order (oldest first)
        commits.reverse()
        return [CommitInfo.from_commit(c) for c in commits]
    
    def get_commits_not_in_base(self, branch: str, base: str) -> List[CommitInfo]:
        """
        Get commits in branch that are not in base.
        Handles merge commits correctly.
        
        Args:
            branch: Branch to get commits from
            base: Base branch to compare against
            
        Returns:
            List of CommitInfo objects in chronological order
        """
        # Get all commits in branch
        branch_commits = list(self.repo.iter_commits(branch))
        
        # Get all commits in base
        base_commit_shas = set(c.hexsha for c in self.repo.iter_commits(base))
        
        # Filter out commits already in base
        new_commits = [c for c in branch_commits if c.hexsha not in base_commit_shas]
        
        # Reverse to get chronological order
        new_commits.reverse()
        
        return [CommitInfo.from_commit(c) for c in new_commits]
    
    def stage_files(self, files: Optional[List[str]] = None) -> None:
        """
        Stage files for commit.
        
        Args:
            files: List of files to stage, or None to stage all
        """
        if files:
            self.repo.index.add(files)
        else:
            self.repo.git.add(A=True)
        self.logger.info(f"Staged files: {files or 'all'}")
    
    def commit(self, message: str, author: Optional[str] = None, 
               date: Optional[str] = None) -> str:
        """
        Create a commit.
        
        Args:
            message: Commit message
            author: Author string (name <email>)
            date: Commit date
            
        Returns:
            SHA of new commit
        """
        # Set author and date if provided
        env = {}
        if author:
            env['GIT_AUTHOR_NAME'] = author.split('<')[0].strip()
            env['GIT_AUTHOR_EMAIL'] = author.split('<')[1].strip('>')
        if date:
            env['GIT_AUTHOR_DATE'] = date
            env['GIT_COMMITTER_DATE'] = date
        
        # Use git CLI directly with environment variables for reliable author & date handling
        if env:
            self.repo.git.commit('-m', message, env=env)
        else:
            self.repo.git.commit('-m', message)
        commit = self.repo.head.commit
        
        self.logger.info(f"Created commit: {commit.hexsha[:7]}")
        return commit.hexsha
    
    def get_conflicted_files(self) -> List[str]:
        """Get list of files with merge conflicts."""
        try:
            # Files with conflicts have 'U' status
            status = self.repo.git.status('--porcelain')
            conflicted = []
            for line in status.split('\n'):
                if line.startswith('UU ') or line.startswith('AA ') or \
                   line.startswith('DD ') or line.startswith('AU ') or \
                   line.startswith('UA ') or line.startswith('DU ') or \
                   line.startswith('UD '):
                    conflicted.append(line[3:].strip())
            return conflicted
        except GitCommandError:
            return []
    
    def has_conflicts(self) -> bool:
        """Check if there are any merge conflicts."""
        return len(self.get_conflicted_files()) > 0
    
    def abort_merge(self) -> None:
        """Abort current merge operation."""
        try:
            self.repo.git.merge('--abort')
            self.logger.info("Aborted merge")
        except GitCommandError as e:
            self.logger.warning(f"Failed to abort merge: {e}")
    
    def reset_hard(self, commit: str = "HEAD") -> None:
        """
        Hard reset to commit.
        
        Args:
            commit: Commit to reset to
        """
        self.repo.git.reset('--hard', commit)
        self.logger.info(f"Reset to {commit}")
    
    def clean(self, force: bool = True, directories: bool = True) -> None:
        """
        Clean untracked files.
        
        Args:
            force: Force clean
            directories: Remove untracked directories
        """
        args = []
        if force:
            args.append('-f')
        if directories:
            args.append('-d')
        self.repo.git.clean(*args)
        self.logger.info("Cleaned untracked files")


class RepositoryPair:
    """Manages a pair of source and target repositories."""
    
    def __init__(self, source_path: str, target_path: str, 
                 logger: Optional[logging.Logger] = None):
        """
        Initialize repository pair.
        
        Args:
            source_path: Path to source repository
            target_path: Path to target repository
            logger: Optional logger instance
        """
        self.source = GitRepository(source_path, logger)
        self.target = GitRepository(target_path, logger)
        self.logger = logger or logging.getLogger(__name__)
    
    def validate_clean(self) -> Tuple[bool, List[str]]:
        """
        Validate both repositories are clean.
        
        Returns:
            Tuple of (is_clean, list of error messages)
        """
        errors = []
        
        if self.source.is_dirty():
            errors.append(f"Source repository has uncommitted changes: {self.source.path}")
        
        if self.target.is_dirty():
            errors.append(f"Target repository has uncommitted changes: {self.target.path}")
        
        return len(errors) == 0, errors
    
    def validate_branches(self, source_branch: str, target_branch: str) -> Tuple[bool, List[str]]:
        """
        Validate branch configuration.
        
        Args:
            source_branch: Source branch name
            target_branch: Target branch name
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        if not self.source.branch_exists(source_branch):
            errors.append(f"Source branch does not exist: {source_branch}")
        
        # Target branch can be created, so we don't check existence
        
        return len(errors) == 0, errors

# Made with Bob
