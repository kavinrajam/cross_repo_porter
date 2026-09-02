# Contributing to cross-repo-porter

Thank you for your interest in contributing! Here's everything you need to get started.

## 📋 Before You Start

- For **bug fixes** or **small improvements**, feel free to open a PR directly.
- For **new features or major changes**, please open an issue first to discuss the idea before writing code.

## 🛠️ Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_GITHUB_USERNAME/cross-repo-porter.git
cd cross-repo-porter

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev dependencies
pip install -e .
pip install ruff pytest
```

## 🔁 Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```
2. Make your changes.
3. Run linting and tests:
   ```bash
   ruff check .
   pytest
   ```
4. Commit with a clear message (see below).
5. Push and open a Pull Request against `main`.

## ✏️ Commit Message Format

Use short, imperative messages:

```
fix: handle empty patch files gracefully
feat: add --no-confirm flag to cherry-pick
docs: update README installation steps
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

## 📐 Code Style

- Formatter/linter: [`ruff`](https://docs.astral.sh/ruff/)
- Follow existing patterns in the codebase — keep new modules focused on a single responsibility.
- Add docstrings for any new public functions or classes.

## 🧪 Tests

- Tests live in `tests/` (create the directory if adding the first test).
- Use `pytest`. Run with:
  ```bash
  pytest
  ```

## 🐛 Reporting Bugs

Open a GitHub Issue and use the **Bug Report** template. Include:
- Your OS and Python version
- The exact command you ran
- The full error output
- Contents of the relevant log file (`~/.cross-repo-porter/.logging/`)

## 📄 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
