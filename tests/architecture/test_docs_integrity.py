"""Documentation integrity gate: every relative doc link and ledger path must resolve.

文档会随时间腐化：文件被重命名、目录被重组，而正文里的 `](xxx.md)` 链接不会报错，
只会在读者点开时 404。本门禁把"文档链接有效性"变成与 ruff/mypy 同级的硬约束，
使文档重组不会静默破坏交叉引用。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CAPABILITIES = DOCS / "capabilities.json"

# 跳过目录：虚拟环境、版本库、第三方数据
_SKIP_DIRS = {".venv", ".git", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache",
              "data", "__pycache__"}

# 匹配 markdown 相对链接，保留锚点以便剥离
_LINK_RE = re.compile(r"\]\(([^)#\s]+?\.(?:md|json|png|jpg|svg))(#([^)]*))?\)")


def _iter_markdown() -> list[Path]:
    found: list[Path] = []
    for path in ROOT.rglob("*.md"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
    return sorted(found)


def _is_external(target: str) -> bool:
    return target.startswith(("http://", "https://", "mailto:", "#"))


def test_all_relative_markdown_links_resolve() -> None:
    """Every relative link in every repo markdown file must point at a real file."""
    broken: list[str] = []
    for md in _iter_markdown():
        text = md.read_text(encoding="utf-8", errors="ignore")
        for match in _LINK_RE.finditer(text):
            target = match.group(1)
            if _is_external(target):
                continue
            if not (md.parent / target).resolve().exists():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    assert not broken, "存在失效的文档链接（重命名/移动后未同步）:\n" + "\n".join(broken)


def test_capability_ledger_paths_exist() -> None:
    """Every docs path referenced by capabilities.json must exist."""
    payload = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    missing: set[str] = set()
    for entry in payload.get("entries", []):
        for rel in entry.get("docs", []):
            if not (ROOT / rel).exists():
                missing.add(rel)
    assert not missing, f"capabilities.json 引用了不存在的文档: {sorted(missing)}"


def test_docs_use_the_standard_directory_layout() -> None:
    """docs/ 只能使用约定的一级目录，防止文档再次散落回根目录。"""
    allowed = {
        "architecture", "models", "evaluation", "research", "operations",
        "status", "decisions", "archive", "params",
    }
    stray = {
        p.name
        for p in DOCS.iterdir()
        if p.is_dir() and p.name not in allowed and not p.name.startswith(".")
    }
    assert not stray, f"docs/ 出现未约定的子目录: {sorted(stray)}"

    loose = {
        p.name
        for p in DOCS.glob("*.md")
        if p.name not in {"README.md", "HANDOFF.md"}
    }
    assert not loose, (
        "docs/ 根目录只允许 README.md 与 HANDOFF.md，其余文档必须归档到子目录: "
        f"{sorted(loose)}"
    )


def test_archived_docs_are_marked_as_archived() -> None:
    """归档目录下的文档必须带归档横幅，避免读者误当现行方案。"""
    missing: list[str] = []
    for md in (DOCS / "archive").rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        if "已归档" not in text:
            missing.append(str(md.relative_to(ROOT)))
    assert not missing, f"归档文档缺少「已归档」横幅: {missing}"
