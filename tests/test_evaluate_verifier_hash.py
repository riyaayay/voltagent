"""Regression test: evaluate_verifier.compute_sha256 is platform-agnostic.

This guards against the CI failure caused by core.autocrlf=true on Windows
producing different raw binary hashes than Linux CI (LF checkout).

The fix: compute_sha256 normalises CRLF→LF before hashing.  Reverting that
normalisation will cause this test to fail on Windows (CRLF checkout).

NOTE: imports from scripts.evaluate_verifier are done inside test functions
(not at module scope) to avoid triggering the voltagent model-loading chain
during pytest collection.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Pure helper — duplicates the logic under test to have an independent oracle
# ---------------------------------------------------------------------------

def _compute_sha256_lf(path: Path) -> str:
    """LF-normalised SHA-256 — independent oracle for the tests below."""
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComputeSha256:
    """compute_sha256 must return the same digest regardless of line endings."""

    def test_lf_file(self, tmp_path: Path) -> None:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.evaluate_verifier import compute_sha256  # noqa: PLC0415

        content = b'{"a": 1,\n"b": 2\n}\n'
        f = tmp_path / "lf.json"
        f.write_bytes(content)
        # LF file — no CRLF to strip, hash must match plain LF content
        assert compute_sha256(f) == hashlib.sha256(content).hexdigest()

    def test_crlf_file_matches_lf_hash(self, tmp_path: Path) -> None:
        """A CRLF file must produce the same hash as the LF version."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.evaluate_verifier import compute_sha256  # noqa: PLC0415

        lf_content = b'{"a": 1,\n"b": 2\n}\n'
        crlf_content = lf_content.replace(b"\n", b"\r\n")

        lf_file = tmp_path / "lf.json"
        crlf_file = tmp_path / "crlf.json"
        lf_file.write_bytes(lf_content)
        crlf_file.write_bytes(crlf_content)

        assert compute_sha256(lf_file) == compute_sha256(crlf_file), (
            "compute_sha256 must normalise CRLF→LF before hashing so that "
            "Windows dev machines (autocrlf=true) and Linux CI produce the "
            "same digest."
        )

    def test_frozen_benchmark_hashes(self) -> None:
        """The frozen benchmark files must match EXPECTED_HASHES exactly.

        If this fails it means either:
          a) Someone modified a frozen benchmark file (forbidden).
          b) The EXPECTED_HASHES dict is stale and needs updating.
        """
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.evaluate_verifier import EXPECTED_HASHES, compute_sha256  # noqa: PLC0415

        for fname, expected in EXPECTED_HASHES.items():
            path = Path("data/eval") / fname
            if not path.exists():
                pytest.skip(f"Benchmark file not present: {path}")
            actual = compute_sha256(path)
            assert actual == expected, (
                f"Integrity check failed for {fname}!\n"
                f"Expected: {expected}\n"
                f"Actual:   {actual}\n"
                "Either the file was modified (forbidden) or EXPECTED_HASHES "
                "is stale.  Update EXPECTED_HASHES using LF-normalised bytes."
            )
