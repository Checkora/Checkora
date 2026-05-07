# Contributing to Checkora ♟️

[![CI/CD Pipeline](https://github.com/Checkora/Checkora/actions/workflows/ci.yml/badge.svg)](https://github.com/Checkora/Checkora/actions/workflows/ci.yml)

Thank you for considering contributing to **Checkora** — a chess engine powered by minimax with alpha-beta pruning, served via Django. We welcome contributions from the community, especially **GSSoC contributors**!

---

## 🗺️ Table of Contents

- [GSSoC Contributors — Start Here](#-gssoc-contributors--start-here)
- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [CI/CD Pipeline](#%EF%B8%8F-cicd-pipeline)
- [Branch Naming Convention](#-branch-naming-convention)
- [Commit Message Format](#-commit-message-format)
- [Pull Request Guidelines](#-pull-request-guidelines)
- [Code Style](#-code-style)
- [Reporting Issues](#-reporting-issues)
- [Code of Conduct](#-code-of-conduct)

---

## 🏅 GSSoC Contributors — Start Here

Welcome to GSSoC! Here's how the contribution flow works for this project:

1. **Fork** the repository to your own GitHub account (button at top-right of the repo page).
2. **Clone your fork** locally — never clone the upstream repo directly.
3. Work on a **feature branch** (not `main`) in your fork.
4. Open a **Pull Request from your fork's branch → `Checkora/Checkora:main`**.
5. The CI pipeline will run automatically on your PR — all checks must pass before review.
6. A maintainer will review and approve your PR. Do **not** merge it yourself.

> **Important:** The `main` branch is protected. You cannot push directly to it —
> all changes must come through reviewed, approved PRs.

---

## 🚀 Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/Checkora.git
   cd Checkora
   ```
3. **Add upstream remote** so you can stay in sync:
   ```bash
   git remote add upstream https://github.com/Checkora/Checkora.git
   git fetch upstream
   ```
4. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

---

## 🛠️ Development Setup

### Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.10 |
| g++ | ≥ 11 (for C++ engine) |
| pip | latest |

### Installation

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
# Copy the example file to a local .env file
cp .env.example .env              # Linux/macOS
copy .env.example .env            # Windows (PowerShell)

# Compile the C++ chess engine (Linux/macOS)
g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main
chmod +x game/engine/main

# Compile on Windows (PowerShell with g++ installed)
g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main.exe

# Run database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

### Running Tests

```bash
python manage.py test game --verbosity=2
```

### Checking for Missing Migrations

```bash
python manage.py migrate --check
```

### Linting (must pass before submitting a PR)

```bash
pip install flake8 flake8-django
flake8 . --exclude=.venv,migrations,__pycache__ --max-line-length=120
```

---

## ⚙️ CI/CD Pipeline

Every PR and push to `main` runs the following automated checks via GitHub Actions:

| Job | What it does | Required to merge |
|-----|-------------|-------------------|
| 🔍 **Lint** | `flake8` on all Python code | ✅ Yes |
| ⚙️ **Compile Engine** | `g++ -O2` on `game/engine/main.cpp` | ✅ Yes |
| 🧪 **Django Tests** | `python manage.py test game` | ✅ Yes |
| 🗄️ **Migration Check** | `python manage.py migrate --check` | ✅ Yes |
| 🔒 **Security Scan** | `pip-audit` on `requirements.txt` | ✅ Yes |
| 🌐 **Deploy** | Vercel production deploy | 🔁 Push to `main` only |

All checks must pass before a maintainer can merge your PR.

---

## 🌿 Branch Naming Convention

Use the following prefixes:

| Prefix | Use for |
|--------|---------|
| `feat/` | New features |
| `fix/` | Bug fixes |
| `docs/` | Documentation changes |
| `refactor/` | Code refactoring |
| `test/` | Adding or updating tests |
| `chore/` | Maintenance tasks |
| `engine/` | C++ engine changes |

**Example:** `feat/add-move-history-panel`

---

## 📝 Commit Message Format

```
<scope>: <short clear action in present tense>.
```

### Rules

- **Scope**: a module or feature name (`game`, `api`, `ui`, `templates`, `core`, `engine`)
- Use concise but descriptive language
- Start action with a capital letter (`Fix`, `Add`, `Update`, `Remove`, `Improve`)
- No emojis in commit messages
- One sentence only, ending with a period
- Keep under 80 characters

### Examples

```
game: Add move validation for castling.
api: Fix session expiry handling in game endpoint.
templates: Update board layout for mobile responsiveness.
engine: Improve alpha-beta pruning depth limit to 6.
core: Remove deprecated settings configuration.
```

---

## 🔀 Pull Request Guidelines

> ⚠️ **Before starting work, sync your fork with upstream `main`.**
> Opening a PR from a stale fork causes unnecessary merge conflicts.
> Run these steps before creating your feature branch:
>
> ```bash
> # Step 1 — Sync your fork with upstream before starting work
> git fetch upstream
> git checkout main
> git rebase upstream/main
> git push origin main
>
> # Step 2 — Then create your feature branch
> git checkout -b feat/your-feature-name
> ```

1. **One PR = One Purpose**: fix one bug, add one feature, or improve documentation.
2. Keep PRs **small and focused** — large PRs are harder to review.
3. Fill in the **PR template** completely (it loads automatically).
4. **Link the relevant issue** using `Fixes #<issue-number>`.
5. **All CI checks must pass** — maintainers will not review failing PRs.
6. Add or update **tests** for any new functionality.
7. Update **documentation** (README, docstrings, comments) as needed.

### Keeping Your Fork Up to Date

Before opening a PR, sync your fork with the upstream `main`:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
git checkout feat/your-feature-name
git rebase main
```

---

## 🎨 Code Style

- Follow **PEP 8** for Python code (`flake8` enforces this automatically).
- Use **meaningful variable and function names** (no single-letter names except loop counters).
- Add **docstrings** to all public functions and classes.
- Keep **functions focused** — one function, one responsibility.
- For C++ engine code, follow the existing style in `game/engine/main.cpp`.

---

## 🐛 Reporting Issues

When reporting issues, please include:

- A clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Your environment (OS, Python version, browser if UI-related)
- Relevant error messages or stack traces

Use the **bug report template** when opening an issue.

---

## 📋 Code of Conduct

Please be respectful and considerate in all interactions. We are committed to providing a welcoming and inclusive environment for everyone.

Unacceptable behavior includes harassment, discrimination, or any form of personal attack.
Violations can be reported to the project maintainers.

---

## ❓ Questions?

- Open an **issue** for project-related questions.
- For GSSoC-specific questions, join our Discord community: [https://discord.gg/WfrpMuNZn](https://discord.gg/WfrpMuNZn)

Thank you for contributing! ♟️🎮
