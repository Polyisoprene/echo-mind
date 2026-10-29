"""Gate 3: Automated AST Architectural Boundary, SOLID & Flat-Code Anti-Nesting Tests."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Protocol

from echomind.domain import models, ports

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "echomind"
MAX_FILE_LINES = 300
MAX_FUNC_LINES = 40
MAX_CONTROL_NESTING = 2
MAX_PORT_METHODS = 5

FORBIDDEN_IN_DOMAIN_AND_MIND = {
    "aiosqlite",
    "httpx",
    "websockets",
    "fastapi",
    "nonebot",
    "echomind.adapters",
    "echomind.web",
    "echomind.tools",
}

NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)


def _iter_py_files(subdir: str = "") -> list[Path]:
    base = SRC_ROOT / subdir if subdir else SRC_ROOT
    return sorted(p for p in base.rglob("*.py") if p.is_file())


def _extract_imported_modules(tree: ast.AST) -> list[str]:
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def _is_forbidden_import(mod: str) -> bool:
    return any(
        mod == forbidden or mod.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_IN_DOMAIN_AND_MIND
    )


def _calc_max_nesting(node: ast.AST, current_depth: int = 0) -> int:
    max_d = current_depth
    for child in ast.iter_child_nodes(node):
        next_d = current_depth + 1 if isinstance(child, NESTING_NODES) else current_depth
        child_max = _calc_max_nesting(child, next_d)
        max_d = max(max_d, child_max)
    return max_d


def test_srp_file_line_limit() -> None:
    """[SRP-01] Every source file in src/echomind must be <= 300 lines."""
    for path in _iter_py_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= MAX_FILE_LINES, (
            f"{path.relative_to(SRC_ROOT)} has {len(lines)} lines (limit {MAX_FILE_LINES})"
        )


def test_flat_code_nesting_and_func_length() -> None:
    """[FLAT-01..03] Enforce Guard Clauses & Extract Function (nesting <= 2, lines <= 40)."""
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        funcs = [
            n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for fn in funcs:
            fn_lines = (fn.end_lineno or fn.lineno) - fn.lineno + 1
            assert fn_lines <= MAX_FUNC_LINES, (
                f"{path.name}:{fn.name} has {fn_lines} lines (max {MAX_FUNC_LINES})"
            )
            depth = _calc_max_nesting(fn, 0)
            assert depth <= MAX_CONTROL_NESTING, (
                f"{path.name}:{fn.name} has nesting depth {depth} > {MAX_CONTROL_NESTING} "
                "(use guard clauses / invert conditions / extract function!)"
            )


def test_dip_domain_and_mind_zero_infra_imports() -> None:
    """[DIP-01] Verify inward-only imports across domain, mind, tools, and extensions."""
    for pkg in ("domain", "mind"):
        for path in _iter_py_files(pkg):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = [m for m in _extract_imported_modules(tree) if _is_forbidden_import(m)]
            assert not bad, f"DIP violation in {path.name}: forbidden imports {bad}"

    for pkg in ("tools", "extensions", "runtime"):
        for path in _iter_py_files(pkg):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = [
                m
                for m in _extract_imported_modules(tree)
                if m.startswith(("echomind.adapters", "echomind.web"))
            ]
            assert not bad, f"DIP violation in {pkg}/{path.name}: forbidden imports {bad}"


def test_lod_all_domain_models_are_frozen_immutable() -> None:
    """[LoD-02] All domain value objects must enforce frozen=True immutability."""
    classes = [
        obj
        for _, obj in inspect.getmembers(models, inspect.isclass)
        if issubclass(obj, models.FrozenValueObject) and obj is not models.FrozenValueObject
    ]
    assert len(classes) >= 12
    for cls in classes:
        cfg = getattr(cls, "model_config", {})
        assert cfg.get("frozen") is True, f"{cls.__name__} must have frozen=True"
        assert cfg.get("extra") == "forbid", f"{cls.__name__} must have extra='forbid'"


def test_isp_all_ports_are_narrow_protocols() -> None:
    """[ISP-02] Every Port interface in ports.py must be a Protocol with <= 5 methods."""
    protocols = [
        (name, obj)
        for name, obj in inspect.getmembers(ports, inspect.isclass)
        if name.startswith("I") and issubclass(obj, Protocol)
    ]
    assert len(protocols) >= 11
    for name, obj in protocols:
        own_methods = [
            k
            for k, v in obj.__dict__.items()
            if not k.startswith("_") and (callable(v) or isinstance(v, property))
        ]
        assert 1 <= len(own_methods) <= MAX_PORT_METHODS, (
            f"ISP violation: {name} has {len(own_methods)} methods (max {MAX_PORT_METHODS})"
        )


TOOLS_DIR = SRC_ROOT / "tools"
PERSONA_WORDS = (
    "回音",
    "尾尾",
    "小鲸鱼",
    "鲸鱼娘",
    "傲娇",
    "撒娇",
    "蓝发",
    "女仆",
)


def test_tools_stay_persona_agnostic() -> None:
    """工具层必须无状态、无人设：语气与身份只允许由 CognitiveFrame 动态生成。"""
    offenders: dict[str, list[str]] = {}
    for path in sorted(TOOLS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = [word for word in PERSONA_WORDS if word in text]
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"工具层出现硬编码人设词（应改由人格模型生成）：{offenders}"
