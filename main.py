"""
cross-repo-porter - Main entry point
Cherry-pick commits between any two Git repositories with configurable path transformation.
"""

import datetime
import logging
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path

from config import ConfigManager
from constants import CONFIG_DIR


def _create_arg_parser():
    """Create and configure argument parser."""
    parser = ArgumentParser(
        description="""
cross-repo-porter — Cherry-pick commits from one Git repository into another,
with automatic path transformation between different directory layouts.

EXAMPLES:
  # One-time setup: point to your two repos and configure a path mapping
  porter config --source /path/to/repo-a --target /path/to/repo-b
  porter config --add-mapping src/api/   lib/openapi/

  # Cherry-pick a branch
  porter cherry-pick feature-branch --base-source main --base-target main

  # Cherry-pick with defaults saved in config
  porter cherry-pick feature-branch

  # Continue after resolving conflicts
  porter cherry-pick --continue

  # Preview without making changes
  porter cherry-pick --dry-run feature-branch
        """,
        formatter_class=RawTextHelpFormatter,
        epilog="For more information, see: https://github.com/YOUR_GITHUB_USERNAME/cross-repo-porter"
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ------------------------------------------------------------------ #
    # cherry-pick sub-command                                              #
    # ------------------------------------------------------------------ #
    cp_parser = subparsers.add_parser(
        'cherry-pick',
        help='Cherry-pick commits from source repository to target repository'
    )
    cp_parser.add_argument(
        'branch',
        type=str,
        nargs='?',
        help="Branch name or commit SHAs to cherry-pick"
    )
    cp_parser.add_argument(
        '--continue',
        dest='continue_pick',
        action='store_true',
        help="Continue cherry-pick after resolving conflicts"
    )
    cp_parser.add_argument(
        '--skip',
        action='store_true',
        help="Skip the current conflicting commit and continue"
    )
    cp_parser.add_argument(
        '--abort',
        action='store_true',
        help="Abort cherry-pick and revert all changes"
    )
    cp_parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be cherry-picked without making any changes"
    )
    cp_parser.add_argument(
        '--base-source',
        type=str,
        metavar='BRANCH',
        default=None,
        help="Base branch in source repository (overrides saved default)"
    )
    cp_parser.add_argument(
        '--base-target',
        type=str,
        metavar='BRANCH',
        default=None,
        help="Base branch in target repository (overrides saved default)"
    )

    # ------------------------------------------------------------------ #
    # config sub-command                                                   #
    # ------------------------------------------------------------------ #
    cfg_parser = subparsers.add_parser(
        'config',
        help='Configure repository paths, default branches, and path mappings'
    )
    cfg_parser.add_argument(
        '--source',
        type=str,
        metavar='PATH',
        help="Path to source repository"
    )
    cfg_parser.add_argument(
        '--target',
        type=str,
        metavar='PATH',
        help="Path to target repository"
    )
    cfg_parser.add_argument(
        '--base-source',
        type=str,
        metavar='BRANCH',
        help="Save default base branch for source repository"
    )
    cfg_parser.add_argument(
        '--base-target',
        type=str,
        metavar='BRANCH',
        help="Save default base branch for target repository"
    )
    cfg_parser.add_argument(
        '--add-mapping',
        nargs=2,
        metavar=('SOURCE_PREFIX', 'TARGET_PREFIX'),
        help="Add a path mapping  e.g. --add-mapping src/api/ lib/openapi/"
    )
    cfg_parser.add_argument(
        '--remove-mapping',
        metavar='SOURCE_PREFIX',
        help="Remove a path mapping by its source prefix"
    )
    cfg_parser.add_argument(
        '--list',
        action='store_true',
        help="Show current configuration"
    )

    # ------------------------------------------------------------------ #
    # status sub-command                                                   #
    # ------------------------------------------------------------------ #
    subparsers.add_parser('status', help='Show current cherry-pick status')

    return parser


# --------------------------------------------------------------------------- #
# Command handlers                                                             #
# --------------------------------------------------------------------------- #

def handle_config_command(args):
    """Handle config command."""
    config = ConfigManager(initial=True)

    if args.source:
        config.set_source(args.source)
        print(f"✓ Source repository set to: {args.source}")

    if args.target:
        config.set_target(args.target)
        print(f"✓ Target repository set to: {args.target}")

    if args.base_source:
        config.set_default_source_branch(args.base_source)
        print(f"✓ Default source branch set to: {args.base_source}")

    if args.base_target:
        config.set_default_target_branch(args.base_target)
        print(f"✓ Default target branch set to: {args.base_target}")

    if args.add_mapping:
        src_prefix, tgt_prefix = args.add_mapping
        config.add_path_mapping(src_prefix, tgt_prefix)
        print(f"✓ Path mapping added: {src_prefix!r}  →  {tgt_prefix!r}")

    if args.remove_mapping:
        removed = config.remove_path_mapping(args.remove_mapping)
        if removed:
            print(f"✓ Path mapping removed: {args.remove_mapping!r}")
        else:
            print(f"⚠️  No mapping found for: {args.remove_mapping!r}")

    if args.list:
        print("Current Configuration:")
        print(f"  Source Repository : {config.get_source() or '(not set)'}")
        print(f"  Target Repository : {config.get_target() or '(not set)'}")
        print(f"  Default src branch: {config.get_default_source_branch() or '(not set)'}")
        print(f"  Default tgt branch: {config.get_default_target_branch() or '(not set)'}")
        mappings = config.get_path_mappings()
        if mappings:
            print("  Path Mappings:")
            for src, tgt in mappings.items():
                print(f"    {src!r}  →  {tgt!r}")
        else:
            print("  Path Mappings     : (none)")
        print(f"  Config File       : {CONFIG_DIR / '.paths.json'}")
        return

    if not any([args.source, args.target, args.base_source, args.base_target,
                args.add_mapping, args.remove_mapping, args.list]):
        print("Use --source, --target, --base-source, --base-target, "
              "--add-mapping, --remove-mapping, or --list")
        sys.exit(1)


def handle_status_command():
    """Handle status command."""
    from state import StateManager

    state_manager = StateManager()
    state = state_manager.load()

    if not state:
        print("No active cherry-pick operation")
        return

    print("Cherry-pick Status:")
    print(f"  Source : {state.source_branch}")
    print(f"  Target : {state.target_branch}")
    print(f"  Status : {state.status}")
    print(f"  Progress: {len(state.applied_commits)}/{len(state.commits_to_apply)} commits")

    if state.current_commit:
        print(f"  Current: {state.current_commit[:7]}")

    if state.conflict_files:
        print(f"  Conflicts: {len(state.conflict_files)} file(s)")
        for file in state.conflict_files:
            print(f"    - {file}")

    remaining = state.get_remaining_commits()
    if remaining:
        print(f"  Remaining: {len(remaining)} commit(s)")


def handle_cherry_pick_command(args, log_dir, timestamp):
    """Handle cherry-pick command."""
    from cherry_picker import CherryPicker, ConflictError
    from repository import RepositoryPair
    from path_transformer import create_transformer_from_config
    from state import StateManager, create_initial_state

    logger = logging.getLogger(__name__)
    config = ConfigManager(initial=True)
    state_manager = StateManager()

    # ------------------------------------------------------------------ #
    # Resolve base branches: CLI flag > saved default > error             #
    # ------------------------------------------------------------------ #
    base_source = args.base_source or config.get_default_source_branch()
    base_target = args.base_target or config.get_default_target_branch()

    # Handle continue / skip / abort
    if args.continue_pick or args.skip or args.abort:
        state = state_manager.load()
        if not state:
            print("❌ No active cherry-pick operation")
            sys.exit(1)

        try:
            repo_pair = RepositoryPair(
                source_path=state.source_repo,
                target_path=state.target_repo
            )
            transformer = create_transformer_from_config(config, logger)
            cherry_picker = CherryPicker(repo_pair, transformer, state_manager)

            if args.abort:
                print("🔄 Aborting cherry-pick...")
                cherry_picker.abort_cherry_pick(state)
                state_manager.clear()
                print("✓ Cherry-pick aborted")
                return

            if args.skip:
                print("⏭️  Skipping current commit...")
                success, error = cherry_picker.skip_commit(state)
                if not success:
                    print(f"❌ Error: {error}")
                    sys.exit(1)
                print("✓ Commit skipped")
                if state.status == "completed":
                    print("✅ All commits processed")
                    state_manager.clear()
                    return
                args.continue_pick = True

            if args.continue_pick:
                print("🔄 Continuing cherry-pick...")
                try:
                    success, error = cherry_picker.continue_cherry_pick(state)
                    if success:
                        print("✅ Cherry-pick completed successfully!")
                        state_manager.clear()
                    else:
                        print(f"❌ Error: {error}")
                        sys.exit(1)
                except ConflictError as e:
                    print("⚠️  Cherry-pick paused due to conflicts")
                    print(f"\nConflicts in {len(e.conflicted_files)} file(s):")
                    for f in e.conflicted_files:
                        print(f"  - {f}")
                    print("\nResolve conflicts and run: porter cherry-pick --continue")
                    sys.exit(1)
                return

        except Exception as e:
            logger.error(f"Error during cherry-pick operation: {e}", exc_info=True)
            print(f"❌ Error: {e}")
            sys.exit(1)

    # ------------------------------------------------------------------ #
    # New cherry-pick operation                                            #
    # ------------------------------------------------------------------ #
    if not args.branch:
        print("❌ Error: Branch name required")
        print("Usage: porter cherry-pick <branch-name>")
        sys.exit(1)

    source_path = config.get_source()
    target_path = config.get_target()

    if not source_path or not target_path:
        print("❌ Error: Repository paths not configured")
        print("Run: porter config --source <path> --target <path>")
        sys.exit(1)

    if not base_source:
        print("❌ Error: Source base branch not specified")
        print("Use --base-source <branch>  or save a default with:")
        print("  porter config --base-source <branch>")
        sys.exit(1)

    if not base_target:
        print("❌ Error: Target base branch not specified")
        print("Use --base-target <branch>  or save a default with:")
        print("  porter config --base-target <branch>")
        sys.exit(1)

    try:
        # Load transformer — will fail with a clear message if no mappings set
        transformer = create_transformer_from_config(config, logger)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    try:
        logger.info(f"Initializing repositories: {source_path} -> {target_path}")
        repo_pair = RepositoryPair(source_path, target_path)

        print("🔍 Validating repositories...")
        is_clean, errors = repo_pair.validate_clean()
        if not is_clean:
            for error in errors:
                print(f"❌ {error}")
            sys.exit(1)
        print("✓ Repositories validated")

        print(f"🔄 Pulling latest changes for base branches...")
        try:
            # Pull source base branch
            repo_pair.source.checkout_branch(base_source)
            repo_pair.source.pull(branch=base_source)
            print(f"✓ Pulled latest '{base_source}' in source repository")
        except Exception as e:
            logger.warning(f"Could not pull latest '{base_source}' in source repository: {e}")
            print(f"⚠️  Could not pull latest '{base_source}' in source repository: {e}")

        try:
            # Pull target base branch
            repo_pair.target.checkout_branch(base_target)
            repo_pair.target.pull(branch=base_target)
            print(f"✓ Pulled latest '{base_target}' in target repository")
        except Exception as e:
            logger.warning(f"Could not pull latest '{base_target}' in target repository: {e}")
            print(f"⚠️  Could not pull latest '{base_target}' in target repository: {e}")

        print(f"📋 Finding commits in '{args.branch}' not in '{base_source}'...")
        commits = repo_pair.source.get_commits_not_in_base(args.branch, base_source)

        if not commits:
            print(f"✓ No new commits to cherry-pick from '{args.branch}'")
            return

        print(f"Found {len(commits)} commit(s) to cherry-pick:")
        for i, commit in enumerate(commits, 1):
            print(f"  {i}. {commit.sha[:7]} - {commit.message.split(chr(10))[0][:60]}")

        if args.dry_run:
            print("\n✓ Dry-run complete — no changes made")
            return

        target_branch = f"pull/{args.branch}"
        print(f"\nTarget branch : {target_branch}")
        print(f"Path mappings :")
        for src, tgt in transformer.mappings.items():
            print(f"  {src!r}  →  {tgt!r}")

        response = input("\nContinue? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("Aborted by user")
            return

        if repo_pair.target.branch_exists(target_branch):
            branch_resp = input(f"\n⚠️  Branch '{target_branch}' already exists in target repository. Use existing branch? [y/N]: ").strip().lower()
            if branch_resp not in ['y', 'yes']:
                print("Aborted by user")
                return
            print(f"🌿 Checking out existing branch '{target_branch}'...")
            repo_pair.target.checkout_branch(target_branch)
        else:
            print(f"\n🌿 Creating branch '{target_branch}' tracking 'origin/{base_target}'...")
            repo_pair.target.checkout_branch(base_target)
            # Check if origin/<base_target> exists to track, otherwise fall back to local base_target
            origin_ref = f"origin/{base_target}"
            remote_refs = [r.name for r in repo_pair.target.repo.remotes.origin.refs] if 'origin' in repo_pair.target.repo.remotes else []
            start_point = origin_ref if origin_ref in remote_refs else base_target
            repo_pair.target.create_branch(target_branch, start_point=start_point, track=True)
            repo_pair.target.checkout_branch(target_branch)

        commit_shas = [c.sha for c in commits]
        state = create_initial_state(
            source_repo=str(source_path),
            target_repo=str(target_path),
            source_branch=args.branch,
            target_branch=target_branch,
            commits=commit_shas,
            base_commit=base_target
        )
        state_manager.save(state)

        cherry_picker = CherryPicker(repo_pair, transformer, state_manager)

        print("🍒 Starting cherry-pick...")
        try:
            success, error = cherry_picker.cherry_pick_range(commit_shas, state)

            if success:
                print("\n✅ Cherry-pick completed successfully!")
                print(f"Branch '{target_branch}' is ready in target repository")
                print("\nNext steps:")
                print(f"  1. Review: cd {target_path} && git log {target_branch}")
                print(f"  2. Push  : git push origin {target_branch}")
                print(f"  3. Open a pull request")
                state_manager.clear()
            else:
                print(f"\n❌ Error: {error}")
                sys.exit(1)

        except ConflictError as e:
            print("\n⚠️  Cherry-pick paused due to conflicts")
            print(f"\nConflicts in {len(e.conflicted_files)} file(s):")
            for f in e.conflicted_files:
                print(f"  - {f}")
            print("\nTo resolve:")
            print(f"  1. Fix conflicts in: {target_path}")
            print("  2. Stage resolved files: git add <files>")
            print("  3. Continue: porter cherry-pick --continue")
            print("\nOr:")
            print("  - Skip commit: porter cherry-pick --skip")
            print("  - Abort      : porter cherry-pick --abort")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Cherry-pick failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print(f"\nCheck the log: {log_dir / f'porter_{timestamp}.log'}")
        sys.exit(1)


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #

def main():
    """Main entry point."""
    parser = _create_arg_parser()
    args = parser.parse_args()

    log_dir = CONFIG_DIR / ".logging"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"porter_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("cross-repo-porter v1.0.0 started")

    if args.command == 'config':
        handle_config_command(args)
    elif args.command == 'status':
        handle_status_command()
    elif args.command == 'cherry-pick':
        handle_cherry_pick_command(args, log_dir, timestamp)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
