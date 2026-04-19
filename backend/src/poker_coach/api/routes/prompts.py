"""Prompt pack browser + editor endpoints.

Reads the on-disk filesystem for packs/versions. Writes stay on disk —
git remains the authoritative history; commits are manual so the user
can stage and review.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from poker_coach.api.deps import get_prompts_root
from poker_coach.prompts.renderer import PromptRenderer

logger = logging.getLogger(__name__)

router = APIRouter()

_VERSION_RE = re.compile(r"^v\d+$")


class PackVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    description: str | None


class Pack(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    versions: list[PackVersion]


class PromptDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    pack: str
    version: str
    description: str | None
    declared_variables: list[str]
    template_raw: str
    template_hash: str


class SavePromptRequest(BaseModel):
    version: str
    content: str  # full file bytes including YAML frontmatter


class SavePromptResponse(BaseModel):
    pack: str
    version: str
    path: str


def _iter_packs(root: Path) -> list[Pack]:
    if not root.exists():
        return []
    packs: list[Pack] = []
    for pack_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        versions: list[PackVersion] = []
        renderer = PromptRenderer(root)
        for md in sorted(pack_dir.glob("v*.md")):
            version = md.stem
            if not _VERSION_RE.match(version):
                continue
            try:
                tmpl = renderer.load(pack_dir.name, version)
                versions.append(PackVersion(version=version, description=tmpl.description))
            except Exception:
                # Malformed frontmatter — still surface the version, no desc.
                logger.exception("failed to load prompt %s/%s", pack_dir.name, version)
                versions.append(PackVersion(version=version, description=None))
        packs.append(Pack(name=pack_dir.name, versions=versions))
    return packs


@router.get("/prompts", response_model=list[Pack])
def list_prompts(prompts_root: Path = Depends(get_prompts_root)) -> list[Pack]:
    return _iter_packs(prompts_root)


@router.get("/prompts/{pack}/{version}", response_model=PromptDetail)
def get_prompt(
    pack: str,
    version: str,
    prompts_root: Path = Depends(get_prompts_root),
) -> PromptDetail:
    renderer = PromptRenderer(prompts_root)
    try:
        tmpl = renderer.load(pack, version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PromptDetail(
        pack=tmpl.pack,
        version=tmpl.version,
        description=tmpl.description,
        declared_variables=list(tmpl.declared_variables),
        template_raw=tmpl.template_raw,
        template_hash=tmpl.template_hash,
    )


@router.post("/prompts/{pack}", response_model=SavePromptResponse)
def save_prompt(
    pack: str,
    body: SavePromptRequest,
    prompts_root: Path = Depends(get_prompts_root),
) -> SavePromptResponse:
    if not _VERSION_RE.match(body.version):
        raise HTTPException(
            status_code=400,
            detail=f"version must match {_VERSION_RE.pattern!r}",
        )
    if ".." in pack or "/" in pack:
        raise HTTPException(status_code=400, detail="invalid pack name")

    pack_dir = prompts_root / pack
    pack_dir.mkdir(parents=True, exist_ok=True)
    target = pack_dir / f"{body.version}.md"
    if target.exists():
        raise HTTPException(
            status_code=409,
            detail=f"{body.version} already exists; bump to a new version",
        )

    # Write to a temp path first so a concurrent reader never sees a partial
    # or invalid file at the target path. Rename is atomic on POSIX.
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(body.content, encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            (td_path / pack).mkdir(parents=True)
            (td_path / pack / f"{body.version}.md").write_text(body.content, encoding="utf-8")
            PromptRenderer(td_path).load(pack, body.version)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"template did not validate: {exc}") from exc
    tmp.rename(target)
    return SavePromptResponse(
        pack=pack, version=body.version, path=str(target.relative_to(prompts_root.parent))
    )
