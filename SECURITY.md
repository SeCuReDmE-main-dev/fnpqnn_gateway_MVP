# Security Policy

## Supported Versions

FNP-QNN Gateway MVP is pre-alpha. There are no production-supported versions yet. Security fixes target the current main branch unless a maintainer explicitly publishes another supported line.

## Scope

Security-sensitive areas include suite routing, fingerprints, provider handoff metadata, CodeProject.AI diagnostics, and token-governor redaction. Reports should focus on real behavior in this repository or on its documented gateway boundary.

## Responsible Disclosure

Report security issues privately to the maintainer before public disclosure. If GitHub Security Advisories are enabled, use that channel first. If not, use a private maintainer channel and include enough detail to reproduce without exposing secrets or personal data.

Useful report content:

- affected file, route, module, command, or workflow;
- reproduction steps;
- expected and observed behavior;
- impact and affected users;
- whether credentials, personal information, student data, private evidence, or operational details were exposed;
- proposed fix, if known.

## Secret Boundary

Never commit or disclose API keys, OAuth tokens, cookies, browser sessions, .env values, passwords, cPanel details, payment credentials, private corpora, raw student records, production logs, or unpublished research material.

The shared SecuredMe gateway may route configured audit, observability, and assistant handoff metadata. This repository must not expose gateway secrets, provider tokens, or private operator state in README files, tests, logs, exceptions, screenshots, or issue reports.

## AI And Human Review Boundary

Official school AI routes are Codex/OpenAI and Antigravity/Gemini only. Model output must remain advisory and reviewable. Do not convert this tool into autonomous authority, enforcement, diagnosis, grading, legal decision-making, or unsupervised production safety infrastructure.

## Public Issues

Do not open public issues containing exploit payloads, live credentials, personal data, private student information, customer records, camera/audio samples, payment secrets, or enough operational detail to compromise a deployment.
