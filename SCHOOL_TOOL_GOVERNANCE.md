# School Tool Governance Standard

This repository is part of the SecuredMe open-source school-tool suite.

Official classroom use is maintained for students, teachers, schools, and supervised young-adult learning. The supported AI-assisted routes are Codex/OpenAI and Antigravity/Gemini only. Ollama Cloud, generic uncensored local AI, and unknown agent routes are not supported as official classroom providers.

The existing project license remains active. `NOTICE` and `DISCLAIMER` add attribution, school-governance, and misuse-responsibility boundaries without changing that license.

Users may fork the code under the repository license, but the maintainer only supports the reviewed official version. Private modified copies, unreviewed rewrites, and changes made outside pull request review are not a maintenance obligation.

Other AI agents must not rewrite the official school mechanism directly. If a user wants a different mechanism, build a separate local fork, adapter, or plugin without disturbing the maintained repository.

Cybersecurity and algorithm-building features, when present, are training tools for supervised learning. They must not be used for attack, theft, fraud, bypass, abuse, surveillance misuse, or criminal automation.
## Development Stability Gate
This repository is tagged `pre-alpha` and `in-development`. External PRs are not evaluated for merge before the official school tool is stable and fully functional for classroom use. Until that gate is met, outside contributors should open issues or build local forks/plugins; maintainers may still push internal stabilization commits.
## School Authentication And Secret Boundary
This repository is a small SecuredMe school tool. Official classroom use must not require `.env` files, API keys, raw tokens, or local model secrets. Student and teacher workflows must use Codex/OpenAI or Antigravity/Gemini through browser WebAuth, fingerprinted session approval, and encrypted local session records when authentication is needed.

The reason for excluding generic local AI routes from official school mode is student and teacher safety: education accounts, provider-side account controls, browser login, and governed AI refusal behavior are safer than unguided local model endpoints for classroom cybersecurity and algorithm-building tools.

