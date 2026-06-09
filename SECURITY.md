# Security Policy

## Supported versions

Only the **`main` branch** receives security fixes. The project does not
maintain release branches and does not backport fixes to older versions.
If you depend on a specific commit or tag, upgrade to the latest `main`
to receive a security patch.

## Reporting a vulnerability

**Do not file a public issue.** Public issues (including GitHub Issues
and public pull-request comments) give attackers a head start before a
fix is available.

Instead, use GitHub's **private vulnerability reporting** feature:

1. Go to the **Security** tab on this repository.
2. Click **Report a vulnerability**.
3. Fill in the details (see *What to include in a report* below).

GitHub's private reporting keeps the report confidential while the
maintainer assesses it, and optionally creates a temporary private fork
for collaboration on a fix. See GitHub's documentation on
[privately reporting a security vulnerability](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
for more details.

If GitHub private vulnerability reporting is unavailable for this
repository, you may reach out via a private discussion or direct message
on the platform where you obtained the project. No maintainer email
address is published in this repository.

### What to include in a report

A good report lets the maintainer reproduce and fix the issue quickly.
Include:

- **Description** — what the vulnerability is and how it can be
  triggered.
- **Impact** — what an attacker could do if the vulnerability is
  exploited (data exposure, code execution, denial of service, etc.).
- **Reproduction steps** — a minimal, concrete example that demonstrates
  the issue (code snippet, YAML input, environment setup).
- **Suggested fix** (if you have one) — a patch, workaround, or design
  change that would address the problem.

## Response timeline

The maintainer commits to the following:

1. **Acknowledge receipt** within **5 business days** of the report.
   The acknowledgment confirms the report was seen and is being triaged;
   it does not imply agreement on severity or a fix plan.

2. **Initial severity assessment** within **10 business days** of the
   report. The assessment classifies the vulnerability as critical, high,
   medium, or low, along with a brief rationale.

3. **Propose a fix timeline** after the severity assessment. Critical
   vulnerabilities are prioritised for an expedited fix. The timeline
   depends on complexity and maintainer availability; the assessment
   reply will include a target date or next-check-in date so you are
   not left waiting without updates.

These timelines are targets, not guarantees. Complex or
hard-to-reproduce issues may take longer; the maintainer will
communicate if that is the case.

## Scope

This security policy covers the **`robotsix-yaml-config` library**
itself — the code and data that ship in the package.

Vulnerabilities in downstream consumers (applications that happen to
use this library) should be reported to those projects directly, even
if the root cause traces back to `robotsix-yaml-config`. If you are
unsure, report here and the maintainer will redirect as appropriate.
