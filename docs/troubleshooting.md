# Troubleshooting Guide

This document covers common issues contributors may encounter while setting up, developing, and testing the project.

## Installation Issues

### Dependencies fail to install

**Problem**

Dependencies fail during installation.

**Solution**

Ensure you are using the recommended Node.js and npm versions.

```bash
node -v
npm -v
```

Then reinstall dependencies:

```bash
npm install
```

---

## Environment Configuration Issues

### Missing environment variables

**Problem**

Application fails to start due to missing configuration values.

**Solution**

Copy the example environment file and update the required values.

```bash
cp .env.example .env
```

Review all required environment variables before starting the application.

---

## Application Startup Issues

### Development server does not start

**Problem**

The application exits immediately or fails to launch.

**Solution**

Check for:

* Missing dependencies
* Incorrect environment variables
* Port conflicts

Try reinstalling dependencies and restarting the server.

---

## Test Failures

### Tests are failing unexpectedly

**Problem**

Previously passing tests now fail.

**Solution**

Run the test suite again after pulling the latest changes:

```bash
npm test
```

Ensure dependencies are up to date:

```bash
npm install
```

---

## Git Issues

### Unable to push changes

**Problem**

Git rejects the push operation.

**Solution**

Pull the latest changes and resolve any merge conflicts:

```bash
git pull origin main
```

Then push again.

---

## Related Documentation

- [Development Guide](development.md)
- [Testing Guide](testing.md)
- [Project Structure](project_structure.md)
- [Architecture Guide](engine_architecture.md)