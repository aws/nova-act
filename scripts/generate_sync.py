# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/usr/bin/env python3
"""Generate synchronous Nova Act SDK code from async source files using libcst.

This script reads the async implementation under src/nova_act/asyncio/ and generates
the corresponding sync implementation under src/nova_act/. The async version is the
source of truth.

Usage:
    python scripts/generate_sync.py                # Generate/overwrite sync files
    python scripts/generate_sync.py --check        # Check if sync files are up to date (CI)
    python scripts/generate_sync.py --output dir   # Write to alternate directory
    python scripts/generate_sync.py --file path    # Transform a single file

Background:
    Python's ``asyncio`` module enables concurrent code via ``async``/``await``.
    Async functions return coroutines that must be awaited, and async context
    managers use ``async with`` instead of ``with``.
        - https://docs.python.org/3/library/asyncio.html
        - https://peps.python.org/pep-0492/

    libcst (Library Concrete Syntax Tree) parses and transforms Python source
    while preserving formatting, comments, and whitespace — unlike the stdlib
    ``ast`` module which discards them.
        - https://libcst.readthedocs.io/

    Design inspired by psycopg's async-to-sync code generation approach:
        - https://www.psycopg.org/articles/2024/09/23/async-to-sync/
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import libcst as cst

# Resolve project root from this script's location (scripts/generate_sync.py → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HATCH_BIN = _PROJECT_ROOT / ".hatch" / "bin" / "hatch"
ASYNC_DIR = _PROJECT_ROOT / "src/nova_act/asyncio"
SYNC_DIR = _PROJECT_ROOT / "src/nova_act"


# ---------------------------------------------------------------------------
# libcst helpers
# ---------------------------------------------------------------------------


class _CoroutineUnwrapper(cst.CSTTransformer):
    """Unwrap ``Coroutine[X, Y, T]`` → ``T`` inside parsed expression trees.

    Duplicates the ``leave_Subscript`` logic from ``AsyncToSyncTransformer``
    because string annotations (e.g., ``"Callable[..., Coroutine[...]]"``) are
    parsed into a separate expression tree that the main transformer never visits.
    ``leave_Annotation`` parses the string, applies this visitor, and re-emits
    the result as a bare expression.
    """

    def leave_Subscript(self, original_node: cst.Subscript, updated_node: cst.Subscript) -> cst.BaseExpression:
        if isinstance(updated_node.value, cst.Name) and updated_node.value.value == "Coroutine":
            slices = updated_node.slice
            if isinstance(slices, Sequence) and len(slices) >= 3:
                third = slices[2]
                if isinstance(third.slice, cst.Index):
                    return third.slice.value
        return updated_node


# ---------------------------------------------------------------------------
# Main transformer
# ---------------------------------------------------------------------------


class AsyncToSyncTransformer(cst.CSTTransformer):
    """Transform async Python source code to its synchronous equivalent.

    Handles:
    - ``async def`` → ``def``
    - ``await expr`` → ``expr``
    - ``async with`` → ``with``  /  ``async for`` → ``for``
    - ``__aenter__``/``__aexit__`` → ``__enter__``/``__exit__``
    - ``playwright.async_api`` → ``playwright.sync_api``
    - ``async_playwright`` → ``sync_playwright``
    - ``nova_act.asyncio.X`` → ``nova_act.X``
    - ``asyncio.sleep(...)`` → ``time.sleep(...)``
    - ``Coroutine[X, Y, T]`` → ``T`` (in both AST nodes and string annotations)
    - Removal of ``Coroutine`` from ``from typing import ...``
    """

    def __init__(self, async_source_path: str) -> None:
        super().__init__()
        self._async_source_path = async_source_path
        self._has_import_time = False

    # -- Pre-scan ------------------------------------------------------------

    def visit_Module(self, node: cst.Module) -> bool:
        """Pre-scan module for existing ``import time``."""
        for stmt in node.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for item in stmt.body:
                    if isinstance(item, cst.Import) and not isinstance(item.names, cst.ImportStar):
                        for alias in item.names:
                            if isinstance(alias.name, cst.Name) and alias.name.value == "time":
                                self._has_import_time = True
        return True

    # -- Module level -------------------------------------------------------

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Prepend a generated-file header."""
        header_lines = [
            cst.EmptyLine(
                comment=cst.Comment(value="# WARNING: this file is auto-generated by scripts/generate_sync.py"),
            ),
            cst.EmptyLine(
                comment=cst.Comment(value=f"# Source: {self._async_source_path}"),
            ),
            cst.EmptyLine(
                comment=cst.Comment(
                    value="# DO NOT EDIT — changes will be overwritten. Modify the async source instead."
                ),
            ),
        ]
        return updated_node.with_changes(header=[*header_lines, *updated_node.header])

    # -- Functions ----------------------------------------------------------

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        if updated_node.asynchronous is not None:
            name = updated_node.name.value
            if name == "__aenter__":
                updated_node = updated_node.with_deep_changes(updated_node.name, value="__enter__")
            elif name == "__aexit__":
                updated_node = updated_node.with_deep_changes(updated_node.name, value="__exit__")
            return updated_node.with_changes(asynchronous=None)
        return updated_node

    # -- Await --------------------------------------------------------------

    def leave_Await(self, original_node: cst.Await, updated_node: cst.Await) -> cst.BaseExpression:
        return updated_node.expression

    # -- Async with / for ---------------------------------------------------

    def leave_With(
        self,
        original_node: cst.With,
        updated_node: cst.With,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        if updated_node.asynchronous is not None:
            return updated_node.with_changes(asynchronous=None)
        return updated_node

    def leave_For(
        self,
        original_node: cst.For,
        updated_node: cst.For,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        if updated_node.asynchronous is not None:
            return updated_node.with_changes(asynchronous=None)
        return updated_node

    # -- Pragma: async / sync ------------------------------------------------

    @staticmethod
    def _extract_body(suite: cst.BaseSuite) -> Sequence[cst.BaseStatement]:
        """Extract the statement list from an ``IndentedBlock`` or ``SimpleStatementSuite``."""
        if isinstance(suite, cst.IndentedBlock):
            return suite.body
        if isinstance(suite, cst.SimpleStatementSuite):
            return [cst.SimpleStatementLine(body=suite.body)]
        raise ValueError(f"Unexpected suite type: {type(suite)}")

    @staticmethod
    def _has_pragma_comment(node: cst.If, pragma: str) -> bool:
        """Check if an ``if`` statement's trailing comment matches ``# pragma: <pragma>``.

        The comment sits on the same line as ``if True:`` / ``if False:``,
        stored in the ``IndentedBlock.header`` trailing whitespace.
        """
        if isinstance(node.body, cst.IndentedBlock):
            header = node.body.header
            if isinstance(header, cst.TrailingWhitespace) and header.comment is not None:
                return header.comment.value.strip() == f"# pragma: {pragma}"
        return False

    def leave_If(
        self,
        original_node: cst.If,
        updated_node: cst.If,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        """Handle ``if True: # pragma: async`` and ``if False: # pragma: sync`` blocks.

        - ``if True: # pragma: async`` → drop the if-body; keep the else-body
          (un-indented) if present, otherwise remove the entire block.
        - ``if False: # pragma: sync`` → keep the if-body (un-indented),
          discard the else-body.
        """
        if self._has_pragma_comment(updated_node, "async"):
            if not (isinstance(updated_node.test, cst.Name) and updated_node.test.value == "True"):
                raise ValueError("# pragma: async must be on 'if True:', not 'if False:'")
            # Async-only: keep else branch if it exists, otherwise remove entirely
            if updated_node.orelse is not None:
                if isinstance(updated_node.orelse, cst.Else):
                    return cst.FlattenSentinel(self._extract_body(updated_node.orelse.body))
                raise ValueError("# pragma: async block must not use elif")
            return cst.RemovalSentinel.REMOVE

        if self._has_pragma_comment(updated_node, "sync"):
            if not (isinstance(updated_node.test, cst.Name) and updated_node.test.value == "False"):
                raise ValueError("# pragma: sync must be on 'if False:', not 'if True:'")
            if updated_node.orelse is not None:
                raise ValueError("# pragma: sync block must not have an else/elif branch")
            # Sync-only: keep the if-body
            return cst.FlattenSentinel(self._extract_body(updated_node.body))

        return updated_node

    # -- Imports ------------------------------------------------------------

    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.BaseSmallStatement | cst.FlattenSentinel[cst.BaseSmallStatement] | cst.RemovalSentinel:
        module = updated_node.module

        # playwright.async_api → playwright.sync_api
        if (
            isinstance(module, cst.Attribute)
            and isinstance(module.value, cst.Name)
            and module.value.value == "playwright"
            and isinstance(module.attr, cst.Name)
            and module.attr.value == "async_api"
        ):
            updated_node = updated_node.with_deep_changes(module.attr, value="sync_api")

        # from asyncio import sleep → from time import sleep
        # Any other asyncio imports (gather, create_task, etc.) are async-only
        # and get dropped entirely — they have no sync equivalent.
        if isinstance(module, cst.Name) and module.value == "asyncio":
            if not isinstance(updated_node.names, cst.ImportStar):
                has_sleep = any(
                    isinstance(alias.name, cst.Name) and alias.name.value == "sleep" for alias in updated_node.names
                )
                if has_sleep:
                    return updated_node.with_changes(
                        module=cst.Name("time"),
                        names=[cst.ImportAlias(name=cst.Name("sleep"))],
                    )
                # No sleep — remove the entire import
                return cst.RemovalSentinel.REMOVE

        # from typing import ..., Coroutine, ... → remove Coroutine
        if isinstance(module, cst.Name) and module.value == "typing":
            if not isinstance(updated_node.names, cst.ImportStar):
                original_len = len(updated_node.names)
                names = [
                    alias
                    for alias in updated_node.names
                    if not (isinstance(alias.name, cst.Name) and alias.name.value == "Coroutine")
                ]
                if not names:
                    return cst.RemovalSentinel.REMOVE
                if len(names) != original_len:
                    # Strip trailing comma from the new last import alias
                    last = names[-1]
                    if last.comma != cst.MaybeSentinel.DEFAULT:
                        names[-1] = last.with_changes(comma=cst.MaybeSentinel.DEFAULT)
                    return updated_node.with_changes(names=names)

        return updated_node

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        """Handle ``import asyncio`` → ``import time`` or removal."""
        for stmt in updated_node.body:
            if isinstance(stmt, cst.Import) and not isinstance(stmt.names, cst.ImportStar):
                for alias in stmt.names:
                    if isinstance(alias.name, cst.Name) and alias.name.value == "asyncio":
                        if self._has_import_time:
                            return cst.RemovalSentinel.REMOVE
                        return updated_node.with_deep_changes(alias.name, value="time")
        return updated_node

    # -- Attribute paths ----------------------------------------------------

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        # nova_act.asyncio → nova_act  (strip the .asyncio path segment)
        if (
            isinstance(updated_node.attr, cst.Name)
            and updated_node.attr.value == "asyncio"
            and isinstance(updated_node.value, cst.Name)
            and updated_node.value.value == "nova_act"
        ):
            return updated_node.value
        return updated_node

    # -- Names --------------------------------------------------------------

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.BaseExpression:
        # async_playwright → sync_playwright  (covers both imports and call sites)
        if updated_node.value == "async_playwright":
            return updated_node.with_changes(value="sync_playwright")
        return updated_node

    # -- Call sites ---------------------------------------------------------

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        # asyncio.sleep(...) → time.sleep(...)
        if (
            isinstance(updated_node.func, cst.Attribute)
            and isinstance(updated_node.func.value, cst.Name)
            and updated_node.func.value.value == "asyncio"
            and isinstance(updated_node.func.attr, cst.Name)
            and updated_node.func.attr.value == "sleep"
        ):
            return updated_node.with_deep_changes(updated_node.func.value, value="time")
        return updated_node

    # -- Type annotations ---------------------------------------------------

    def leave_Subscript(self, original_node: cst.Subscript, updated_node: cst.Subscript) -> cst.BaseExpression:
        # Coroutine[X, Y, T] → T
        if isinstance(updated_node.value, cst.Name) and updated_node.value.value == "Coroutine":
            slices = updated_node.slice
            if isinstance(slices, Sequence) and len(slices) >= 3:
                third = slices[2]
                if isinstance(third.slice, cst.Index):
                    return third.slice.value
        return updated_node

    def leave_Annotation(self, original_node: cst.Annotation, updated_node: cst.Annotation) -> cst.Annotation:
        """Transform string annotations containing ``Coroutine``."""
        annotation = updated_node.annotation
        if isinstance(annotation, cst.SimpleString):
            value = annotation.evaluated_value
            if isinstance(value, str) and "Coroutine" in value:
                try:
                    parsed = cst.parse_expression(value)
                    transformed = parsed.visit(_CoroutineUnwrapper())
                    return updated_node.with_changes(annotation=transformed)
                except cst.ParserSyntaxError:
                    pass
        return updated_node


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def discover_file_pairs(async_dir: Path, sync_dir: Path) -> list[tuple[Path, Path]]:
    """Auto-discover async → sync file pairs, skipping ``__init__.py`` files."""
    pairs: list[tuple[Path, Path]] = []
    for async_path in sorted(async_dir.rglob("*.py")):
        # __init__.py files have structurally different content between async and sync
        # (different re-exports, preview messages, etc.) and are maintained manually.
        if async_path.name == "__init__.py":
            continue
        relative = async_path.relative_to(async_dir)
        sync_path = sync_dir / relative
        pairs.append((async_path, sync_path))
    return pairs


# ---------------------------------------------------------------------------
# Conversion pipeline
# ---------------------------------------------------------------------------


def convert_file(async_path: Path, async_rel_path: str) -> str:
    """Read an async source file and return the transformed sync code."""
    source = async_path.read_text()

    # Parse and transform with libcst
    tree = cst.parse_module(source)
    transformer = AsyncToSyncTransformer(async_rel_path)
    sync_tree = tree.visit(transformer)

    return sync_tree.code


def format_code(code: str) -> str:
    """Format code with ``hatch fmt``, respecting project configuration.

    Writes to a temp file in the project root so that ``hatch fmt`` discovers
    ``pyproject.toml`` and applies the correct settings.
    """
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=str(_PROJECT_ROOT), delete=False) as f:
            tmp_path = Path(f.name)
            f.write(code)
        subprocess.check_call([str(_HATCH_BIN), "fmt", str(tmp_path)])
        return tmp_path.read_text()
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synchronous Nova Act SDK code from async source files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if sync files are up to date (exit 1 if stale).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        metavar="DIR",
        help="Write generated files to DIR instead of updating in-place.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        metavar="PATH",
        help="Transform a single async file (path relative to project root).",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        metavar="SUBDIR",
        help="Limit to a subdirectory under src/nova_act/asyncio/ (e.g., tools/browser/default/util).",
    )
    args = parser.parse_args()

    # Resolve async/sync root directories
    async_dir = ASYNC_DIR / args.dir if args.dir else ASYNC_DIR
    sync_dir = SYNC_DIR / args.dir if args.dir else SYNC_DIR

    # Build file pairs
    if args.file:
        async_path = Path(args.file)
        relative = async_path.relative_to(async_dir)
        sync_path = sync_dir / relative
        pairs = [(async_path, sync_path)]
    else:
        pairs = discover_file_pairs(async_dir, sync_dir)

    stale = False
    for async_path, sync_path in pairs:
        async_rel = str(async_path.relative_to(_PROJECT_ROOT))

        code = convert_file(async_path, async_rel)
        code = format_code(code)

        # Determine output path
        if args.output:
            relative = sync_path.relative_to(sync_dir)
            out_path = args.output / relative
        else:
            out_path = sync_path

        if args.check:
            existing = out_path.read_text() if out_path.exists() else ""
            if code != existing:
                diff = difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    code.splitlines(keepends=True),
                    fromfile=str(out_path),
                    tofile=f"generated from {async_path}",
                )
                sys.stderr.writelines(diff)
                stale = True
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(code)
            async_display = async_path.relative_to(_PROJECT_ROOT)
            try:
                out_display = out_path.relative_to(_PROJECT_ROOT)
            except ValueError:
                out_display = out_path
            print(f"  {async_display} -> {out_display}")

    if stale:
        print(
            "\nSync files are out of date. Run `python scripts/generate_sync.py` to update.",
            file=sys.stderr,
        )
        sys.exit(1)
    elif args.check:
        print("All sync files are up to date.")


if __name__ == "__main__":
    main()
