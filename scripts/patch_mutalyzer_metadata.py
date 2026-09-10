"""Compatibility patch: replace only legacy metadata lookup in three pinned dependencies.

No coordinate conversion or normalization logic is changed. Refuse unknown source bytes.
Run inside the isolated normalizer environment after installing its lockfile.
"""

import hashlib
from importlib.metadata import distribution
from pathlib import Path

SPECS = {
    "mutalyzer_backtranslate": {
        "version": "1.0.0",
        "sha256": "d876dbe5762a4c59c68312b830c8bdc88ab1762259d6ab691246ac46e8efcbe3",
    },
    "mutalyzer_crossmapper": {
        "version": "2.0.1",
        "sha256": "997e2fa53f99dbb0ff887f547dad343913828e668ce4d124027c3003e3b7450a",
    },
    "mutalyzer_spdi_parser": {
        "version": "0.3.1",
        "sha256": "0d33dbf245c8a8a71f2c554c9f0e24a4b49815bae574660bb31b611c77002fdc",
    },
}


def main():
    for name, spec in SPECS.items():
        dist = distribution(name)
        if dist.version != spec["version"]:
            raise ValueError(f"Unexpected {name} version; review compatibility patch")
        path = Path(dist.locate_file(name + "/__init__.py"))
        text = path.read_text()
        if "# VariantRAG metadata compatibility patch" in text:
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(f"Unexpected {name} source bytes; refusing to patch")
        text = text.replace(
            "from pkg_resources import get_distribution",
            "from importlib.metadata import metadata\n# VariantRAG metadata compatibility patch",
        )
        start = text.index("def _get_metadata(name):")
        end = text.index("_copyright_notice", start)
        text = (
            text[:start]
            + 'def _get_metadata(name):\n    return metadata(__package__).get(name, "")\n\n\n'
            + text[end:]
        )
        path.write_text(text)
        print(f"Patched metadata lookup: {name} {dist.version}")


if __name__ == "__main__":
    main()
