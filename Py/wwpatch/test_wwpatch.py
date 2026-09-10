#!/usr/bin/env python3
"""Tests for wwpatch.py. Uses fixture files in testdata/.

Run: python3 wwpatch/test_wwpatch.py
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest

TESTDIR = os.path.dirname(os.path.abspath(__file__))
WWPATCH = os.path.join(TESTDIR, "wwpatch.py")
TESTDATA = os.path.join(TESTDIR, "testdata")

BASE = os.path.join(TESTDATA, "base.tcore")
PATCH1 = os.path.join(TESTDATA, "patch1.tcore")
PATCH2 = os.path.join(TESTDATA, "patch2.tcore")
GOLDEN = os.path.join(TESTDATA, "golden_merged.tcore")


def run_wwpatch(inputs, output):
    result = subprocess.run(
        [sys.executable, WWPATCH, *inputs, "-o", output],
        capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def words(text):
    """{addr: word} from every @C line in an output file, address in octal digits as written."""
    out = {}
    for line in text.splitlines():
        m = re.match(r'^@C(\d+):\s*(.*?)\s*$', line)
        if not m:
            continue
        base = int(m.group(1), 8)
        for i, tok in enumerate(m.group(2).split()):
            if tok == "None":
                continue
            out[base + i] = int(tok, 8)
    return out


class WwpatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def output_path(self, name="merged.tcore"):
        return os.path.join(self.tmp, name)

    def test_two_file_overlay(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1], out)
        self.assertEqual(rc, 0, stderr)
        with open(out) as f:
            text = f.read()
        w = words(text)

        # base-only addresses untouched
        self.assertEqual(w[0o100], 1)
        self.assertEqual(w[0o101], 2)
        self.assertEqual(w[0o110], 0o11)
        self.assertEqual(w[0o111], 0o12)
        # patch1 overlay applied
        self.assertEqual(w[0o102], 0o177777)
        self.assertEqual(w[0o103], 0o177776)
        # patch1-only new addresses added
        self.assertEqual(w[0o200], 0o20)
        self.assertEqual(w[0o201], 0o21)

        # base's JumpTo survives (patch1 has none)
        self.assertIn("%JumpTo 040", text)

        # base's File/TapeID/block_msg stay live; patch1's added as commented
        self.assertIn("%File: base_source.tap\n", text)
        self.assertIn("; %File: patch1_source.tap (patched in)\n", text)
        self.assertIn("%TapeID: BASEID\n", text)
        self.assertIn("; %TapeID: PATCH1ID (patched in)\n", text)
        self.assertIn("xsum=base\n", text)
        self.assertIn("xsum=patch1 (patched in)\n", text)

    def test_three_file_precedence(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1, PATCH2], out)
        self.assertEqual(rc, 0, stderr)
        with open(out) as f:
            text = f.read()
        w = words(text)

        # patch2 (last writer) wins over patch1 at the same address
        self.assertEqual(w[0o102], 0o100000)
        # patch2 overlays a base address patch1 didn't touch
        self.assertEqual(w[0o111], 0o77)
        # patch1's own addresses still present
        self.assertEqual(w[0o200], 0o20)

        # patch2's JumpTo wins (later than base's, patch1 had none)
        self.assertIn("%JumpTo 077", text)

        # both non-base files' File/TapeID appear, in patch order
        idx1 = text.index("patch1_source.tap (patched in)")
        idx2 = text.index("patch2_source.tap (patched in)")
        self.assertLess(idx1, idx2)

    def test_output_matches_golden(self):
        # Regression guard: catches any unintended change to merge output,
        # not just the specific fields the other tests happen to check.
        # golden_merged.tcore was captured from base+patch1+patch2 and
        # independently cross-checked (word-for-word, against real tape
        # data) at the time wwpatch.py stopped depending on wwinfra -- see
        # README.md. If this test fails after a deliberate behavior change,
        # regenerate the golden file, don't just delete the assertion.
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1, PATCH2], out)
        self.assertEqual(rc, 0, stderr)
        with open(out) as f:
            actual = f.read()
        with open(GOLDEN) as f:
            expected = f.read()
        self.assertEqual(actual, expected)

    def test_minimum_two_inputs_required(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE], out)
        self.assertNotEqual(rc, 0)
        self.assertIn("need at least 2 input files", stderr)

    def test_output_deterministic(self):
        out1 = self.output_path("m1.tcore")
        out2 = self.output_path("m2.tcore")
        run_wwpatch([BASE, PATCH1], out1)
        run_wwpatch([BASE, PATCH1], out2)
        with open(out1) as f:
            text1 = f.read()
        with open(out2) as f:
            text2 = f.read()

        self.assertEqual(text1, text2)  # identical inputs -> byte-identical output

    def test_unsupported_directive_warns_with_location(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1], out)
        self.assertEqual(rc, 0, stderr)

        # patch1's %SimParam is genuinely unrecognized and should warn, located
        self.assertIn("%s:10: unsupported directive" % PATCH1, stderr)
        self.assertIn("unrecognized_test_directive", stderr)

    def test_stats_hash_blocknum_dont_warn(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1], out)
        self.assertEqual(rc, 0, stderr)

        # %Stats/%Hash/%Blocknum/%String are recognized-but-ignored on input
        # (dropped from output, not carried through or recomputed) -- no
        # warning expected
        self.assertNotIn("Covariance=0.100000", stderr)  # base's %Stats line
        self.assertNotIn("dummy1-dummy1-10", stderr)      # base's %Hash line
        self.assertNotIn("%Blocknum 0o0", stderr)
        self.assertNotIn("testword", stderr)              # base's %String line

    def test_blank_lines_dont_warn(self):
        out = self.output_path()
        rc, stdout, stderr = run_wwpatch([BASE, PATCH1], out)
        self.assertEqual(rc, 0, stderr)
        for warning_line in (l for l in stderr.splitlines() if "unsupported directive" in l):
            content = warning_line.split("ignoring: ", 1)[1]
            self.assertNotEqual(content.strip(), "")


if __name__ == "__main__":
    unittest.main()
