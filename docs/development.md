# Local Development Setup Guide

## Overview

This guide explains how to set up Checkora for local development, run the application, and work efficiently on contributions.

## Prerequisites

Before getting started, ensure you have the following installed:

| Tool   | Version                                 |
| ------ | --------------------------------------- |
| Python | 3.12+                                   |
| Git    | Latest                                  |
| pip    | Latest                                  |
| g++    | 11+ (required for the C++ chess engine) |

---

## Clone the Repository

Fork the repository and clone your fork:

```bash
git clone https://github.com/<your-username>/Checkora.git
cd Checkora
```

Add the upstream repository:

```bash
git remote add upstream https://github.com/Checkora/Checkora.git
git fetch upstream
```

---

## Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create a local environment file from the template:

### Windows

```bash
copy .env.example .env
```

### Linux/macOS

```bash
cp .env.example .env
```

Update the values in `.env` as required.

---

## Compile the Chess Engine

### Windows

```bash
g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main.exe
```

### Linux/macOS

```bash
g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main
chmod +x game/engine/main
```

---

## Database Setup

Apply migrations:

```bash
python manage.py migrate
```

Create an administrator account:

```bash
python manage.py createsuperuser
```

---

## Run the Development Server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

---

## Static Files

Collect static files when needed:

```bash
python manage.py collectstatic --noinput
```

---

## Common Development Commands

### Run All Tests

```bash
python manage.py test
```

### Run Application Tests

```bash
python manage.py test game --verbosity=2
```

### Run Selenium Tests

```bash
python manage.py test game.selenium_tests --verbosity=2
```

### Create Migrations

```bash
python manage.py makemigrations
```

### Check for Missing Migrations

```bash
python manage.py makemigrations --check --dry-run
```

### Apply Migrations

```bash
python manage.py migrate
```

---

## Keeping Your Fork Updated

Sync your fork with the latest upstream changes:

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

---

## Contribution Workflow

For branch naming conventions, commit message format, pull request guidelines, and code style requirements, refer to:

* `CONTRIBUTING.md`

---

## Troubleshooting

### Migration Issues

```bash
python manage.py migrate
```

### Missing Dependencies

```bash
pip install -r requirements.txt
```

### Engine Compilation Errors

Verify that a supported version of `g++` is installed and available in your system PATH.

---

## Additional Resources

* `README.md`
* `CONTRIBUTING.md`
* `docs/API.md`
* `docs/API_WALKTHROUGH.md`
