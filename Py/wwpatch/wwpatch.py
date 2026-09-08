#!/usr/bin/env python3
"""Patch a list of .tcore files together into one merged .tcore.

First file is the base. Each following file overlays/replaces words at the
same @C addresses. Words present in an earlier file but absent from later
ones are left untouched.

Usage: wwpatch.py file1.tcore file2.tcore ... -o merged.tcore

See README.md in this folder for merge policy on each directive.
"""

import argparse
import io
import re
import sys

# 11-bit WWI address space (0o4000 words). Out-of-range addresses are
# dropped with a warning rather than written.
_CORE_SIZE = 2048

_LINE_RE = re.compile(r'^@[CT](\d+):\s*(.*?)\s*(?:;.*)?$')
_FILE_RE = re.compile(r'^%File:\s*(.*)$')
_TAPEID_RE = re.compile(r'^%TapeID:\s*(.*)$')
_JUMPTO_RE = re.compile(r'^%JumpTo 0(\d+)$')
_HEADER_RE = re.compile(r'^; \*\*\* .* \*\*\*$')
_COMMENT_RE = re.compile(r'^; (.*)$')
_SYMBOL_RE = re.compile(r'^@S(\d+):\s*(.*)$')

# Recognized but deliberately ignored, without a warning: informational
# metadata with no word data (@N, %String), or fields that only made sense
# when write_core() (wwinfra) computed them -- %Stats/%Hash were never
# verified by any reader anyway (confirmed: read_core_file() stores %Hash
# into metadata and never reads it back). @S (symbol table) is handled
# separately, below -- it's carried through, not dropped.
_NO_WARN_RES = [re.compile(p) for p in (
    r'^@N\d+:',
    r'^%String:',
    r'^%Hash:',
    r'^%Blocknum\b',
    r'^%Stats:',
)]


class _ParsedTcore:
    def __init__(self, path):
        self.path = path
        self.file_line = None
        self.tapeid_line = None
        self.jump_to = None
        self.block_msg = None
        self.comments = []  # every other "; ..." line, in file order
        self.words = {}  # {addr: word}
        self.symbols = {}  # {addr: name}

    def parse(self):
        with open(self.path, errors='replace') as f:
            for lineno, line in enumerate(f, start=1):
                line = line.rstrip('\n')
                if line.strip() == '':
                    continue
                if any(p.match(line) for p in _NO_WARN_RES):
                    continue
                m = _SYMBOL_RE.match(line)
                if m:
                    self.symbols[int(m.group(1), 8)] = m.group(2)
                    continue
                m = _LINE_RE.match(line)
                if m:
                    base = int(m.group(1), 8)
                    for i, tok in enumerate(m.group(2).split()):
                        if tok == "None":
                            continue
                        wm = re.match(r'(\d+)', tok)
                        if wm:
                            self.words[base + i] = int(wm.group(1), 8) & 0xFFFF
                    continue
                m = _FILE_RE.match(line)
                if m and self.file_line is None:
                    self.file_line = m.group(1)
                    continue
                m = _TAPEID_RE.match(line)
                if m and self.tapeid_line is None:
                    self.tapeid_line = m.group(1)
                    continue
                m = _JUMPTO_RE.match(line)
                if m:
                    self.jump_to = int(m.group(1), 8)
                    continue
                if _HEADER_RE.match(line):
                    continue
                m = _COMMENT_RE.match(line)
                if m:
                    if self.block_msg is None and self.file_line is None:
                        # first "; ..." comment line, seen before %File, that isn't the
                        # "*** Core Image ***" header -- this is the block_msg line
                        self.block_msg = m.group(1)
                    else:
                        self.comments.append(m.group(1))
                    continue
                print("wwpatch: WARNING: %s:%d: unsupported directive, ignoring: %s" %
                      (self.path, lineno, line), file=sys.stderr)
        return self


def _merge(paths):
    parsed = [_ParsedTcore(p).parse() for p in paths]

    merged_words = {}
    for pf in parsed:
        merged_words.update(pf.words)

    merged_symbols = {}
    for pf in parsed:
        merged_symbols.update(pf.symbols)

    jump_to = None
    for pf in parsed:
        if pf.jump_to is not None:
            jump_to = pf.jump_to

    block_msg = parsed[0].block_msg

    return parsed, merged_words, merged_symbols, jump_to, block_msg


def _write_tcore(parsed, merged_words, merged_symbols, jump_to, block_msg):
    """Render merged data as .tcore text. No %Hash/%Stats and no per-word
    mnemonic/Flexo comments -- both are write_core()-only extras that no
    reader (including read_core_file() itself) ever checks or requires;
    dropping them is what lets this be a plain string-builder instead of a
    wwinfra.write_core() call.
    """
    out = ["; wwpatch output\n"]

    base = parsed[0]
    if block_msg is not None:
        out.append("; %s\n" % block_msg)
    for pf in parsed[1:]:
        if pf.block_msg is not None:
            out.append("; %s (patched in)\n" % pf.block_msg)

    for c in base.comments:
        out.append("; %s\n" % c)
    for pf in parsed[1:]:
        for c in pf.comments:
            out.append("; %s (patched in)\n" % c)

    if base.file_line is not None:
        out.append("%%File: %s\n" % base.file_line)
    for pf in parsed[1:]:
        if pf.file_line is not None:
            out.append("; %%File: %s (patched in)\n" % pf.file_line)

    if base.tapeid_line is not None:
        out.append("%%TapeID: %s\n" % base.tapeid_line)
    for pf in parsed[1:]:
        if pf.tapeid_line is not None:
            out.append("; %%TapeID: %s (patched in)\n" % pf.tapeid_line)

    if jump_to is not None:
        out.append("%%JumpTo 0%o\n" % jump_to)

    for addr, name in sorted(merged_symbols.items()):
        out.append("@S%05o: %s\n" % (addr, name))

    in_range = {}
    for addr, word in merged_words.items():
        if 0 <= addr < _CORE_SIZE:
            in_range[addr] = word
        else:
            print("wwpatch: WARNING: address 0o%o out of range, dropped" % addr,
                  file=sys.stderr)

    row_bases = sorted({addr - addr % 8 for addr in in_range})
    for row_base in row_bases:
        tokens = [("0%o" % in_range[row_base + i]) if (row_base + i) in in_range else "None"
                  for i in range(8)]
        out.append("@C%05o: %s\n" % (row_base, " ".join(tokens)))

    return "".join(out)


def wwpatch(inputs):
    """Merge inputs (paths, in patch order, first = base) and return the
    patched .tcore contents as a StringIO.
    """
    parsed, merged_words, merged_symbols, jump_to, block_msg = _merge(inputs)
    text = _write_tcore(parsed, merged_words, merged_symbols, jump_to, block_msg)
    return io.StringIO(text)


if __name__ == "__main__":

    def main():
        ap = argparse.ArgumentParser(description=__doc__,
                                    formatter_class=argparse.RawDescriptionHelpFormatter)
        ap.add_argument("inputs", nargs="+", help="input .tcore files, in patch order (first = base)")
        ap.add_argument("-o", "--output", required=True, help="output .tcore path")
        args = ap.parse_args()

        if len(args.inputs) < 2:
            print("wwpatch: need at least 2 input files", file=sys.stderr)
            sys.exit(1)

        patched = wwpatch(args.inputs)
        with open(args.output, "w") as f:
            f.write(patched.read())

        print("wwpatch: wrote %s (%d input file(s))" % (args.output, len(args.inputs)))

    main()
