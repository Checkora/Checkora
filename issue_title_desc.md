# GitHub Issue & Pull Request Details

This document contains the copy-paste ready content for both the Issue Report and the Pull Request, following the project's strict contribution guidelines.

---

## 1. GitHub Issue Details

**Title:** `Security: Host Header Poisoning Vulnerability via Wildcard ALLOWED_HOSTS`

**Description:**

A critical security vulnerability exists in the Django configuration where the `ALLOWED_HOSTS` setting includes a wildcard (`*`). This allows arbitrary `Host` headers to be accepted by the application, leading to Host Header Poisoning. This is particularly dangerous during the password reset flow, where malicious links can be generated to exfiltrate tokens.

**Steps to Reproduce:**

1. Send a password reset request with a modified `Host` header (e.g., `Host: evil.com`).
2. Observe that the request is accepted.
3. Check the generated email and observe the poisoned link: `http://evil.com/password-reset-confirm/...`.

---

## 2. Pull Request Details

**PR Title:** `core: Fix Host Header Poisoning by enforcing strict ALLOWED_HOSTS.`

**PR Description:**

This PR addresses a critical security vulnerability where the `ALLOWED_HOSTS` setting included a wildcard (`*`), allowing for Host Header Poisoning. This was specifically exploitable in the password reset flow to exfiltrate tokens.

By enforcing a strict allowlist and gating wildcard patterns behind explicit environment checks, the application now correctly rejects unrecognized Host headers and ensures absolute URLs are only generated using trusted hostnames.

**Key Changes:**

- **Strict Host Validation:** Refactored `ALLOWED_HOSTS` to a strict allowlist. Broad wildcard patterns (like `.vercel.app`) are now gated behind `VERCEL_ENV == 'preview'` to ensure production remains airtight.
- **Enhanced Security Settings:** Added `CSRF_TRUSTED_ORIGINS` for identified production domains.
- **Robust Security Tests:** Implemented a comprehensive test suite in `game/tests_security.py` that asserts correct rejection (400 Bad Request) for unknown hosts and verifies safe link generation for trusted hosts.
- **Optimized Build Process:** Introduced `build_vercel.py` to handle deployment-specific logic (like optional C++ compilation) cleanly, ensuring green builds on Vercel while maintaining the Python fallback.

## Type of Change

- [x] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Related Issue

Fixes #779

## Checklist

- [x] My code follows the project's style guidelines
- [x] I have performed a self-review of my code
- [x] I have commented my code where necessary
- [ ] I have updated the documentation if needed (N/A)
- [x] My changes generate no new warnings
- [x] I have added tests that prove my fix/feature works
- [x] New and existing tests pass locally

## Screenshots (if applicable)

*N/A - This is a backend security fix. Automated tests verify the behavior.*

## Additional Notes

The fix includes a new dedicated test file `game/tests_security.py` that validates Host Header protection. I have verified that all project tests (including existing and new security tests) pass locally. Local development is still supported via `localhost` and `127.0.0.1` in the allowlist.
