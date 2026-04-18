"""Prompt pack loader and renderer.

Prompt files live at `<prompts_root>/<pack>/<version>.md` and have YAML
frontmatter declaring `name`, `version`, `description`, and `variables`
(list of identifiers). The body is a Jinja2 template.

Both the raw file bytes and the rendered output hit the decision log so
a rendered prompt can be reproduced even if the template file drifts.
`template_hash` is sha256 of the full raw file (frontmatter + body) so
a stealth edit that forgets to bump the version number still shows up.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import frontmatter
from jinja2 import Environment, StrictUndefined, meta
from pydantic import BaseModel, ConfigDict


class PromptMetadataError(ValueError):
    """Frontmatter is missing or inconsistent with the file path."""


class PromptVariableError(ValueError):
    """Variables declared / referenced / supplied are out of sync."""


class PromptTemplate(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack: str
    version: str
    description: str | None
    declared_variables: tuple[str, ...]
    template_raw: str
    template_hash: str
    body: str


class RenderedPrompt(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack: str
    version: str
    template_hash: str
    template_raw: str
    rendered_prompt: str
    variables: dict[str, Any]


class PromptRenderer:
    def __init__(self, prompts_root: Path) -> None:
        self.prompts_root = prompts_root
        self._env = Environment(
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=False,  # prompts are plain text, not HTML
        )

    def load(self, pack: str, version: str) -> PromptTemplate:
        path = self.prompts_root / pack / f"{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"no prompt file at {path}")
        raw_bytes = path.read_bytes()
        template_hash = hashlib.sha256(raw_bytes).hexdigest()
        raw_text = raw_bytes.decode("utf-8")
        parsed = frontmatter.loads(raw_text)

        name = parsed.metadata.get("name")
        declared_version = parsed.metadata.get("version")
        if name != pack:
            raise PromptMetadataError(
                f"frontmatter name {name!r} does not match pack directory {pack!r}"
            )
        if declared_version != version:
            raise PromptMetadataError(
                f"frontmatter version {declared_version!r} does not match file {version!r}"
            )

        declared_vars = parsed.metadata.get("variables") or []
        valid = isinstance(declared_vars, list) and all(isinstance(v, str) for v in declared_vars)
        if not valid:
            raise PromptMetadataError("`variables` must be a list of strings")

        body = parsed.content
        referenced = meta.find_undeclared_variables(self._env.parse(body))
        undeclared = referenced - set(declared_vars)
        if undeclared:
            raise PromptVariableError(
                f"template references undeclared variables: {sorted(undeclared)}"
            )

        return PromptTemplate(
            pack=pack,
            version=version,
            description=parsed.metadata.get("description"),
            declared_variables=tuple(declared_vars),
            template_raw=raw_text,
            template_hash=template_hash,
            body=body,
        )

    def render(self, pack: str, version: str, variables: dict[str, Any]) -> RenderedPrompt:
        template = self.load(pack, version)
        missing = set(template.declared_variables) - set(variables)
        if missing:
            raise PromptVariableError(f"missing variables: {sorted(missing)}")
        extra = set(variables) - set(template.declared_variables)
        if extra:
            raise PromptVariableError(f"unexpected variables: {sorted(extra)}")
        rendered = self._env.from_string(template.body).render(**variables)
        return RenderedPrompt(
            pack=pack,
            version=version,
            template_hash=template.template_hash,
            template_raw=template.template_raw,
            rendered_prompt=rendered,
            variables=dict(variables),
        )
