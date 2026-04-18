# Prompt packs

Reference for every prompt pack shipped with the coach. Populated starting Phase 2.

## Conventions

- Files live at `prompts/<pack>/<version>.md`.
- Each file starts with YAML frontmatter declaring `name`, `version`, `description`, and `variables` (list of required Jinja2 variables).
- Body is a Jinja2 template. Variables that aren't declared in the frontmatter must not be referenced in the body (linted at render time).
- Git is the semantic history. `template_hash` in the decision log catches stealth edits that forget to bump the version.

## Packs

### `coach` (Phase 2)

Primary advice prompt used by both live coach and spot analysis. Design notes will land here when v1 is written.

### Future packs

Candidates under consideration: `explainer` (plain-language post-hand teaching), `debater` (adversarial second-opinion), `range-narrator` (villain range estimation).
