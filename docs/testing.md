# Testing & QA Guide

## Overview

Checkora uses Django's testing framework along with Selenium-based integration tests. The JavaScript is tested with Jest.

Current test locations:

* `game/tests.py`
* `game/test_analysis.py`
* `game/test_services.py`
* `game/test_heuristic_analysis.py`
* `game/test_engine_rules.py`, `game/test_engine_bridge.py`, `game/test_persistent_engine.py`, `game/test_engine_differential.py`, `game/test_engine_evaluation.py` and `game/test_search_features.py` (the engine, see below)
* `game/test_levels.py`: the four levels a player can pick, their ratings, and how long each may think on a running clock
* `game/test_accounts.py`: pictures, rating and rank, points and streaks, the leaderboard, the account settings page and the privacy and terms pages
* `game/test_google_login.py`: "Continue with Google", for new players, returning players and deactivated accounts
* `game/test_seo.py`: the sitemap lists every lesson and opening and each listed page opens, every page has a canonical link without its query string, and the home page has one h1
* the other `game/test_*.py` modules
* `game/selenium_tests/test_boards.py`
* `game/selenium_tests/test_navigation.py`
* `game/selenium_tests/test_admin_health.py`
* `board.test.js` and `forum.test.js` in the repository root (Jest)

Every Django test module sits directly in `game/`, apart from the Selenium ones.

Install `requirements-dev.txt` before running them. It adds python-chess to `requirements.txt`; without it the tests in `game/test_engine_differential.py`, and the ones in `game/test_engine_evaluation.py` that play random games, are skipped.

```bash
pip install -r requirements-dev.txt
```

---

## Running Tests

### Run all tests

```bash
python manage.py test
```

Runs the complete test suite.

### Run all game tests

```bash
python manage.py test game
```

Runs all tests inside the game application. That includes the Selenium tests in `game/selenium_tests/`, which need Chrome.

### Run a specific test module

```bash
python manage.py test game.tests
python manage.py test game.test_analysis
```

### Run a specific test class

```bash
python manage.py test game.tests.ClassName
```

### Run a specific test method

```bash
python manage.py test game.tests.ClassName.test_method_name
```

### Verbose Output

```bash
python manage.py test --verbosity=2
```

Provides detailed debugging information.

---

## Engine tests

These modules test the chess engine and the bridge to it.

`game/test_engine_rules.py` talks to the engines themselves over their line protocol, with nothing mocked: move counts (`PERFT`) against published figures, castling and en passant edge cases, promotion, `STATUS`, notation, the evaluation, and search positions such as forced mates and draws by repetition. Every test runs against `game/engine/main.py`. When a compiled engine that runs on the machine is present, the same tests run against it too, and one test checks that both engines evaluate positions alike.

`game/test_engine_bridge.py` tests `game/engine.py`: what reaches the engine as a promotion piece, `last_engine_error`, positions loaded from FEN, check tracking, the `BESTMOVE` command built for each difficulty level, the deliberate mistakes of the easy level, the choice between a compiled binary and the Python engine, and the engine server. `OpeningBookFileTest` in the same file checks that every move in `game/engine/opening_book.json` is legal in its position.

`game/test_persistent_engine.py` tests the per-game engine server and `game/engine_client.py`, which starts it: that it is started once and reused, that it is shut down when a game ends, and what happens when a one-off engine process fails or times out.

`game/test_engine_differential.py` plays seeded random games and checks, at every position, that both engines give the same legal moves, status and notation as python-chess.

`game/test_engine_evaluation.py` checks the king attack and the passed pawn term on positions built for them. On the positions of seeded random games it also checks that both engines give the same score, and that swapping the colours only changes the sign of the score.

`game/test_search_features.py` drives `main.py` through its protocol to test hashing, iterative deepening, timeouts and the figures in the `BESTMOVE` reply.

```bash
python manage.py test game.test_engine_rules game.test_engine_bridge game.test_persistent_engine \
    game.test_engine_differential game.test_engine_evaluation game.test_search_features
```

After changing `main.cpp`, rebuild the binary before running these, or the compiled engine is not tested: a binary that is missing or out of date is skipped.

CI also builds the engine with AddressSanitizer and UBSan and runs every `game/test_engine*.py` module and `game/test_persistent_engine.py` against that build, so an out-of-bounds write or undefined behaviour fails the run. To do the same locally:

```bash
g++ -O1 -g -std=c++17 -fno-omit-frame-pointer \
    -fsanitize=address,undefined -fno-sanitize-recover=undefined \
    game/engine/main.cpp -o game/engine/main
ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
    python manage.py test game.test_engine_rules game.test_engine_bridge game.test_persistent_engine \
    game.test_engine_differential game.test_engine_evaluation
```

This build replaces `game/engine/main`, so compile the normal binary again afterwards (see [development.md](development.md)).

---

## Selenium Testing

### Available Selenium Tests

* `game/selenium_tests/test_boards.py`
* `game/selenium_tests/test_navigation.py`
* `game/selenium_tests/test_admin_health.py`

### Requirements

Before running Selenium tests:

* Install project dependencies
* Install Selenium
* Use a supported browser
* Ensure browser driver versions match the installed browser

### Run Selenium Tests

```bash
python manage.py test game.selenium_tests
```

### Common Troubleshooting

#### Browser Driver Mismatch

Ensure your browser driver version matches your installed browser.

#### Element Not Found Errors

Check whether page elements or selectors have changed.

#### Timing Issues

Prefer explicit waits instead of fixed delays.

---

## JavaScript tests

`board.test.js` and `forum.test.js` load `game/static/game/js/board.js` and `forum.js` in a jsdom environment and test them with Jest. `package.json` holds the dependencies and the `test` script.

```bash
npm ci
npm test
```

CI runs the same two commands in its JavaScript job, with `npm audit --audit-level=high` in between. The job then runs `node --check` on every file in `game/static/game/js/`, so a syntax error fails CI even in a script that Jest never loads.

---

## Tests in CI

`.github/workflows/ci.yml` runs `python manage.py test game --verbosity=2 --parallel` twice, once on SQLite and once on PostgreSQL 16, with `requirements-dev.txt` installed and the compiled engine in place. A separate job runs `game.selenium_tests` with Chrome set up and the static files collected, and another runs the engine tests against the sanitizer build. [CONTRIBUTING.md](../CONTRIBUTING.md) lists every job.

---

## Writing New Tests

### When to Add Tests

Add tests when:

* Introducing a new feature
* Fixing a bug
* Modifying game logic
* Updating analysis functionality
* Changing APIs, views, or models

### Naming Conventions

Use descriptive names:

```python
def test_player_can_start_new_game():
    pass
```

### Best Practices

* Keep tests independent
* Test one behavior at a time
* Use clear assertions
* Use descriptive test names
* Avoid unnecessary delays in Selenium tests

---

## Validation Before Opening a Pull Request

Before opening a PR:

* [ ] Run all relevant tests
* [ ] Verify functionality manually
* [ ] Add tests for new features when appropriate
* [ ] Ensure existing tests continue to pass
* [ ] Update documentation if required
