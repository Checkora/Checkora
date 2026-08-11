# Security Policy

## Supported Versions

Currently, this project does not have versioned releases. Only the main branch is supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

We take the security of this project seriously. Please **do not** report security vulnerabilities through public GitHub Issues, as this may expose the vulnerability to malicious actors before a patch can be applied.

To privately report a security vulnerability, please send an email to **ravi5258p@gmail.com**.

### Expected Timeline

- **Acknowledgment:** You will receive a response acknowledging receipt of your report within 48 hours.
- **Remediation & Disclosure:** We aim to provide an expected timeline for remediation and potential coordinated public disclosure within 5 business days of acknowledgment.

## Resolving CI Security Findings

Our CI pipeline runs three automated checks on every PR: **pip-audit** (dependency vulnerabilities), **Bandit** (static code analysis), and **npm audit** (JavaScript dependency vulnerabilities). GitHub's **CodeQL** default setup also scans the repository automatically. If any of these fail on your PR:

1. **Read the failure output.** Both `pip-audit` and Bandit publish a step summary on the Actions run page, and their full reports are uploaded as downloadable artifacts — you don't need to dig through raw logs.
2. **Dependency vulnerabilities (pip-audit / npm audit):** Update the flagged package to the patched version named in the report, then re-run the relevant local check below before pushing again.
3. **Static analysis findings (Bandit):** Fix the flagged code pattern directly. If you believe a finding is a false positive, explain why in your PR description rather than silencing it — a maintainer will confirm before merge.
4. **Dependabot PRs:** Dependabot opens its own PRs to bump vulnerable dependencies automatically. Review and merge these promptly to keep `main` patched; don't close them without a reason.
5. Still stuck? Ask in the [Discord server](https://discord.gg/WfrpMuNZn) or comment on your PR — a maintainer can help triage.

See [CONTRIBUTING.md](CONTRIBUTING.md#-local-pre-pr-checks) for the exact commands to reproduce these checks locally before pushing.