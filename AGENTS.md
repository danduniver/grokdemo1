# Project Rules for grokdemo1

This is a demo/sandbox project. Keep things simple, well-documented, and easy to run.

## General Guidelines
- Prefer simple, readable code over clever abstractions.
- Include a short README update or comment when adding significant features.
- Use conventional commit style if/when committing (e.g. `feat: add X`, `fix: ...`).
- Keep the project runnable with minimal or zero external dependencies where possible for demos.
- When adding new tech (frameworks, languages), document how to run in README.

## Code Style
- Use 2 spaces for indentation in JS/JSON/HTML.
- Use 4 spaces in Python.
- Meaningful variable names.
- Add brief comments for non-obvious logic.

## Demo Focus
- The project demonstrates Grok working on real tasks.
- New features should be self-contained examples that can be shown quickly.
- Prioritize interactive or visual demos (browser-based preferred for zero-install).

## GitHub / Remote
- Main branch is `main`.
- Use the GitHub MCP tools (via Grok) or local git for changes when possible.
- Keep the remote in sync with local work.

## When Using Subagents or Skills
- For complex multi-step work, consider the bundled `implement`, `review`, `design` skills.
- For exploration of the (small) codebase, the `explore` agent is useful.
