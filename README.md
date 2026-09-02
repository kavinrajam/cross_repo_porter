# cross-repo-porter

A Python CLI tool for cherry-picking commits from one Git repository into another with **configurable path transformation** — useful when two repositories share the same content but store it under different directory layouts.

## 🎯 Overview

`porter` works like `git cherry-pick` but across repositories. You define which path prefixes in the source map to which prefixes in the target, then cherry-pick any branch or set of commits.

1. Cherry-picks commits individually (preserves commit history)
2. Transforms file paths in patches using your configured mappings
3. Handles merge commits correctly
4. Supports conflict resolution with resume capability
5. Maintains original commit metadata (author, date, message)

## ✨ Key Features

- **Cross-repo Cherry-Pick**: Apply commits from one repo into a different repo
- **Configurable Path Mapping**: Any number of `source-prefix → target-prefix` rules
- **Configurable Base Branches**: Save your default branches once, override any time
- **Merge Commit Support**: Handles both linear and merged histories
- **Resume Capability**: Continue from where you left off after resolving conflicts
- **State Management**: Persistent state tracking for reliable operations
- **Interactive CLI**: Clear prompts and progress indicators

## 📋 Prerequisites

- Python 3.7+
- Git installed and configured
- Access to both repositories (local clones)

## 🚀 Installation

### Using pipx (Recommended)

```bash
pipx install git+https://github.com/YOUR_GITHUB_USERNAME/cross-repo-porter.git
```

### Using pip

```bash
pip install git+https://github.com/YOUR_GITHUB_USERNAME/cross-repo-porter.git
```

### From source

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/cross-repo-porter.git
cd cross-repo-porter/cross_repo_porter
pip install -e .
```

## ⚙️ Configuration

All configuration is stored in `~/.cross-repo-porter/.paths.json`.

### 1. Set repository paths

```bash
porter config --source /path/to/source-repo
porter config --target /path/to/target-repo
```

### 2. Set default base branches

```bash
porter config --base-source main
porter config --base-target main
```

These are the branches used to determine which commits are "new" and where the target branch is created from. You can always override them per-run with `--base-source` / `--base-target`.

### 3. Add path mappings

Tell `porter` how file paths in the source repository correspond to paths in the target repository:

```bash
porter config --add-mapping <source-prefix> <target-prefix>

# Example: files under src/api/ in the source live under lib/openapi/ in the target
porter config --add-mapping src/api/  lib/openapi/

# Multiple mappings are supported
porter config --add-mapping docs/spec/  docs/generated/
```

### View current configuration

```bash
porter config --list
```

Output:
```
Current Configuration:
  Source Repository : /path/to/source-repo
  Target Repository : /path/to/target-repo
  Default src branch: main
  Default tgt branch: main
  Path Mappings:
    'src/api/'  →  'lib/openapi/'
  Config File       : ~/.cross-repo-porter/.paths.json
```

### Remove a path mapping

```bash
porter config --remove-mapping src/api/
```

## 📖 Usage

### Basic cherry-pick

```bash
porter cherry-pick feature-branch
```

This will:
1. Find commits in `feature-branch` not in the configured source base branch
2. Show the list and ask for confirmation
3. Create `pull/feature-branch` in the target repository (branched from the target base)
4. Apply each commit with path transformation

### Cherry-pick with explicit branches

```bash
# Override base branches for this run only
porter cherry-pick feature-branch --base-source develop --base-target staging
```

### Dry run

Preview what would be cherry-picked without making any changes:

```bash
porter cherry-pick --dry-run feature-branch
```

### Conflict resolution

When a conflict is detected, `porter` pauses and saves its state:

```bash
# After editing and staging the conflicted files:
git -C /path/to/target-repo add <resolved-files>

porter cherry-pick --continue   # resume
porter cherry-pick --skip       # skip the conflicting commit
porter cherry-pick --abort      # revert everything
```

### Check status

```bash
porter status
```

## 🔄 Example Workflow

```
$ porter cherry-pick feature-branch

🔍 Validating repositories...
✓ Repositories validated
📋 Finding commits in 'feature-branch' not in 'main'...
Found 3 commit(s) to cherry-pick:
  1. abc1234 - Add endpoint for user profiles
  2. def5678 - Update schema validation
  3. ghi9012 - Fix error response format

Target branch : pull/feature-branch
Path mappings :
  'src/api/'  →  'lib/openapi/'

Continue? [y/N]: y

🌿 Creating branch 'pull/feature-branch' from 'main'...
🍒 Starting cherry-pick...

✅ Cherry-pick completed successfully!
Branch 'pull/feature-branch' is ready in target repository

Next steps:
  1. Review: cd /path/to/target-repo && git log pull/feature-branch
  2. Push  : git push origin pull/feature-branch
  3. Open a pull request
```

## 📊 Command Reference

| Command | Description |
|---------|-------------|
| `porter cherry-pick <branch>` | Cherry-pick commits from branch |
| `porter cherry-pick <branch> --base-source <b> --base-target <b>` | Override base branches |
| `porter cherry-pick --dry-run <branch>` | Preview without changes |
| `porter cherry-pick --continue` | Continue after resolving conflicts |
| `porter cherry-pick --skip` | Skip current commit |
| `porter cherry-pick --abort` | Abort and revert changes |
| `porter status` | Show current operation status |
| `porter config --source <path>` | Set source repository path |
| `porter config --target <path>` | Set target repository path |
| `porter config --base-source <branch>` | Save default source base branch |
| `porter config --base-target <branch>` | Save default target base branch |
| `porter config --add-mapping <src> <tgt>` | Add a path mapping |
| `porter config --remove-mapping <src>` | Remove a path mapping |
| `porter config --list` | Show current configuration |

## 🏗️ Architecture

```
cross_repo_porter/
├── __init__.py         # Package init & version
├── pyproject.toml      # Project metadata & build config
├── requirements.txt    # Pinned dependencies
├── README.md           # This file
├── CHANGELOG.md        # Version history
├── main.py             # CLI entry point
├── cherry_picker.py    # Core cherry-pick logic
├── repository.py       # Git repository abstraction
├── path_transformer.py # Path transformation engine
├── state.py            # Persistent state management
├── config.py           # Configuration management
└── constants.py        # Global constants
```

### How it works

1. **Commit selection**: Finds commits in the source branch not reachable from the source base branch (handles merge commits correctly)
2. **For each commit**:
   - Generate a `git format-patch` patch file
   - Transform all path prefixes in the patch headers using configured mappings
   - Apply the transformed patch via `git apply --3way`
   - Commit with the original author, date, and message
3. **State tracking**: Progress is saved after every commit for resume capability
4. **Conflict handling**: Pauses when conflicts occur, allows continue/skip/abort

## 📂 State files

```
~/.cross-repo-porter/
├── .paths.json                       # Repository and mapping configuration
├── .cherry-pick-state.json           # Current operation state
├── .cherry-pick-state.backup.json    # State backup
└── .logging/                         # Log files
```

## 🐛 Troubleshooting

### "Repository has uncommitted changes"

```bash
git -C /path/to/repo stash
```

### "Repository paths not configured"

```bash
porter config --source /path/to/source-repo --target /path/to/target-repo
```

### "No path mappings configured"

```bash
porter config --add-mapping <source-prefix> <target-prefix>
```

### "Source/target base branch not specified"

```bash
porter config --base-source main --base-target main
# or pass them directly:
porter cherry-pick feature-branch --base-source main --base-target main
```

### State file corruption

```bash
# Check status
porter status

# Manually restore backup if needed
cp ~/.cross-repo-porter/.cherry-pick-state.backup.json \
   ~/.cross-repo-porter/.cherry-pick-state.json
```

## 👥 Authors

- [Kavin Raj A M](https://github.com/kavinrajam)
- [Saiprasanna Boyina](https://github.com/saiprasanna-16)
- [Vikranth Nagaraj](https://github.com/vikranthnagaraj)

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
