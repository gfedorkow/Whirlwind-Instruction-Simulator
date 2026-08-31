# wwpatch -- a tcore linker

Patches a list of `.tcore` files together into one merged `.tcore`.
This acts as a primitive linker. 

An use example is  linking csii executable `.tcore` and symbols to a found
intepreter `.tcore` along with necessary patches:

```
linked tcore = interpreter + patch1 + patch2 + csii executable + symbols
```

`wwpatch` can be used as either a standalone CLI tool generating an executable
or imported into the simulator
to allow the linking and patching without creating intermediate files.

## CLI usage

```bash
python3 wwpatch/wwpatch.py file1.tcore file2.tcore ... -o patched.tcore
```

## Library usage

```python
from wwpatch import wwpatch
patched = wwpatch([f1, f2, f3])
for line in patched:
    process(line)
```

The first file is the base.
Each subsequent file overlays/replaces words at matching `@C` addresses.
`wwpatch` returns a `StringIO` object that acts like an open file object.
In this way `wwsim` and others can accept a list of files that are linked together.

## Directive merge policy

- **`%File:` / `%TapeID:` / `; WW Tape Block Numbers...` (block_msg)** -- the
  base file's (first input's) values stay as the live directive. Each
  subsequent file's value is added right after as a commented-out line, e.g.
  `; %File: ... (patched in)`, so provenance isn't lost but only one is
  "active".
- **`%JumpTo`** -- last file in patch order containing **`%JumpTo`** wins.
- **`@S`** -- merged and carried through to the output (later files win on
  address collisions).
- **`%Blocknum`, `%String:`, `%Stats:`, `%Hash:`, `@N`** -- recognized but
  silently dropped, no warning (`_NO_WARN_RES` in `wwpatch.py`). None of
  these carry word data, and `%Hash:` in particular is never actually
  checked by any reader in the codebase (confirmed: `read_core_file()`
  stores it into metadata and nothing ever reads that back) -- so there's
  nothing worth recomputing here either.
- **Per-word mnemonic/Flexo comments** (the `; mh SL sp ca...` annotations
  `wwinfra.write_core()` appends after each `@C` line) -- also not written.
  Purely cosmetic; every reader (including `wwinfra`'s own) strips anything
  after `;` on a `@C`/`@T` line.
- **Anything else** -- print a warning (file, line number,
  content) and are ignored.

## Regression testing

`test_wwpatch.py` runs `wwpatch.py` against
`testdata/` and spot-checks the result: specific `@C` addresses, specific
expected/commented directive lines, output determinism, and warning text
for unrecognized directives. It also diffs the full merged output against
`testdata/golden_merged.tcore` (base+patch1+patch2), as a catch-all
regression guard the specific-field checks above could miss.

`golden_merged.tcore` was captured when `wwpatch.py` stopped depending on
`wwinfra` (word-for-word cross-checked at that point against the real tape,
via `wwinfra.write_core()`/`wwdiff.py -m` round-tripped from `wwpatch`'s new
output -- not just "loads without error"). If a deliberate change to merge
behavior breaks `test_output_matches_golden`, regenerate the golden file
rather than deleting the assertion:
```bash
python3 wwpatch/wwpatch.py wwpatch/testdata/base.tcore wwpatch/testdata/patch1.tcore wwpatch/testdata/patch2.tcore -o wwpatch/testdata/golden_merged.tcore
```

Run the suite:
```bash
python3 wwpatch/test_wwpatch.py -v
```
