#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
from pathlib import Path


def read_app_doc(app_name):
    """Read app documentation from YAML file."""
    doc_paths = [
        Path(__file__).parent.parent.parent.parent / "doc" / f"{app_name}.yaml",
        Path("doc") / f"{app_name}.yaml",
    ]

    if hasattr(sys, '_MEIPASS'):
        doc_paths.insert(0, Path(sys._MEIPASS) / "doc" / f"{app_name}.yaml")

    for path in doc_paths:
        if path.exists():
            try:
                content = path.read_text()

                version = re.search(r'^VERSION:\s*"([^"]+)"', content, re.MULTILINE)
                version = version.group(1) if version else ''

                desc = re.search(
                    '^DESCRIPTION:\\s*>\\s*(.+?)(?=^[A-Z_]+:)',
                    content,
                    re.MULTILINE | re.DOTALL,
                )
                desc = desc.group(1).strip() if desc else ''

                usage_section = re.search(
                    '^USAGE:(.+?)^OPTIONS:',
                    content,
                    re.MULTILINE | re.DOTALL,
                )
                usage = (
                    re.findall(r'-\s*"([^"]+)"', usage_section.group(1))
                    if usage_section
                    else []
                )

                return {'version': version, 'description': desc, 'usage': usage}
            except (OSError, UnicodeDecodeError):
                continue

    return {}
