## PRD: Biome Format On Save And Commit

**Task:** [Biome Format On Save And Commit](../TASKS/biome-format-on-save-and-commit.md)
**Status:** Draft
**Owner:** Codex
**Date:** 2026-04-16

### Problem

The repo currently has no repo-level JS/JSON formatter configuration and no commit hook to enforce formatting. That creates avoidable drift in:

- `scripts/*.jsx`
- `mcp/adobe-premiere-mcp/proxy-server/*.js`
- JSON config files that should remain machine-formatted

You want:

1. Biome to format supported files on save
2. Biome to run automatically before commit
3. Space indentation instead of tabs
4. Default indentation width of `2` for the JS-side files

### Goal

Add the minimum repo-level setup needed to make Biome the default formatter for the repo’s JS/JSON surface and enforce it before commit.

### Non-Goals

- Reformat Python with Biome
- Replace Ruff for Python
- Add a large frontend toolchain
- Introduce formatting rules that fight Adobe ExtendScript compatibility

### Proposed Implementation

#### Repo-Level Tooling

- Add a root `package.json` for formatting-only tooling
- Add `@biomejs/biome`
- Add `husky`
- Add `lint-staged`

#### Formatting Config

- Add `biome.json`
- Keep default indentation at `2` spaces
- Scope formatting to the JS/JSON files we actually want

#### Save Behavior

- Add workspace `.vscode/settings.json`
- Set Biome as default formatter for supported JS/JSON file types
- Enable `editor.formatOnSave`

#### Commit Behavior

- Add Husky `pre-commit`
- Run `lint-staged`
- Format staged supported files with Biome before commit

### File Targets

Primary targets:

- `scripts/**/*.jsx`
- `mcp/adobe-premiere-mcp/proxy-server/**/*.js`
- selected JSON config files

Possible exclusions if needed:

- generated files
- third-party vendored assets

### Risks

- Root `.gitignore` currently ignores `.vscode/` and most `*.json`, so config files will need explicit allow rules
- Biome must not be applied blindly to unsupported file types
- Husky requires local install/bootstrap, so the repo should make setup obvious

### Acceptance Criteria

- Running one repo command formats supported files with Biome
- Saving a supported file in VS Code formats it with Biome
- Committing staged supported files triggers the formatter automatically
- Formatting uses spaces with `2`-space indentation for the JS-side files
- The setup does not interfere with Python tooling

### Recommendation

Implement this with:

- `Biome` for formatting
- `VS Code workspace settings` for save behavior
- `Husky + lint-staged` for pre-commit enforcement

Do not add more tooling than that.
