#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TOOL_ROOT = Path(__file__).resolve().parent.parent


class TestVersionConsistency(unittest.TestCase):
    """Ensure version strings match across all locations."""

    def _read_program_version(self):
        program = TOOL_ROOT / ".program"
        content = program.read_text()
        match = re.search(r'^version:\s*(\S+)', content, re.MULTILINE)
        self.assertIsNotNone(match, ".program missing version field")
        return match.group(1)

    def _read_init_version(self):
        init = TOOL_ROOT / "app" / "__init__.py"
        content = init.read_text()
        match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
        self.assertIsNotNone(match, "__init__.py missing __version__")
        return match.group(1)

    def _read_doc_version(self):
        program = TOOL_ROOT / ".program"
        content = program.read_text()
        name_match = re.search(r'^name:\s*(\S+)', content, re.MULTILINE)
        name = name_match.group(1) if name_match else "ttm2k"
        doc = TOOL_ROOT / "doc" / f"{name}.yaml"
        content = doc.read_text()
        match = re.search(r'^VERSION:\s*"([^"]+)"', content, re.MULTILINE)
        self.assertIsNotNone(match, f"doc/{name}.yaml missing VERSION field")
        return match.group(1)

    def test_versions_match(self):
        prog_ver = self._read_program_version()
        init_ver = self._read_init_version()
        doc_ver = self._read_doc_version()

        self.assertEqual(
            prog_ver, init_ver,
            f".program ({prog_ver}) != __init__.py ({init_ver})",
        )
        self.assertEqual(
            prog_ver, doc_ver,
            f".program ({prog_ver}) != doc/ttm2k.yaml ({doc_ver})",
        )


if __name__ == "__main__":
    unittest.main()
