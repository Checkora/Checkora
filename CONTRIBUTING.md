# Contributing to Checkora

Thank you for considering contributing to Checkora! We welcome contributions from the community.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment
4. Create a new branch for your changes

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-username/checkora.git
cd checkora

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

## Branch Naming Convention

Use the following prefixes for your branches:

- `feat/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Adding or updating tests
- `chore/` - Maintenance tasks

Example: `feat/add-user-authentication`

## Commit Message Format

```
<scope>: <short clear action in present tense>.
```

### Rules

- **Scope** should be a module or feature name (e.g., `game`, `api`, `ui`, `templates`, `core`)
- Use concise but descriptive language
- Start action with a capital letter (Fix, Add, Rename, Update, Remove, Highlight, Forbid, Focus, Improve)
- No emojis
- No extra explanation
- One sentence only
- End with a period
- Keep it under 80 characters

### Examples

```
game: Add move validation for checkers pieces.
api: Fix permissions querying for game sessions.
templates: Update board layout for better responsiveness.
core: Remove deprecated settings configuration.
```

## Pull Request Guidelines

1. **One PR = One Purpose**
   - Fix one bug, OR
   - Add one feature, OR
   - Improve documentation

2. Keep PRs focused and small
3. Update documentation if needed
4. Add tests for new features
5. Ensure all tests pass before submitting

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and concise

## Reporting Issues

When reporting issues, please include:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

## Code of Conduct

Please be respectful and considerate in all interactions. We are committed to providing a welcoming and inclusive environment for everyone.

## Questions?

If you have questions, feel free to open an issue for discussion.

Thank you for contributing! 🎮
