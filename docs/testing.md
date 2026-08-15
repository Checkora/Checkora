# Testing & QA Guide

## Overview

Checkora uses Django's testing framework along with Selenium-based integration tests.

Current test locations:

* `game/tests.py`
* `game/test_analysis.py`
* `game/selenium_tests/test_boards.py`
* `game/selenium_tests/test_navigation.py`

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

Runs all tests inside the game application.

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

## Selenium Testing

### Available Selenium Tests

* `game/selenium_tests/test_boards.py`
* `game/selenium_tests/test_navigation.py`

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
