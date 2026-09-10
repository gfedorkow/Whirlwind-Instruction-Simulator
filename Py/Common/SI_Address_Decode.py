#!/usr/bin/env python3
"""
wwio_lookup.py

Look up a Whirlwind I ('WWI') si-instruction I/O address and report which
in-out device / mode of operation it refers to.

Source: 2M-0277 Whirlwind Programming Manual, Oct 1958, Table 5
        "DESIGNATIONS OF IN-OUT EQUIPMENT, WWI (si addresses for all units)"
        (page 110 / p.144 of the scanned PDF)

Every si address in Table 5 is printed as a stacked pair: an OCTAL value on
top and its DECIMAL equivalent underneath (e.g. "100(o)" over "64(o)").  On
the scan, the parenthesized letter distinguishing octal from decimal is
easy to misread (O vs 0 vs D all look similar at that resolution), so this
table stores ONLY the octal address -- the "ground truth" column -- and
computes/prints the decimal value live via int(octal_string, 8). Every
octal->decimal pair below was cross-checked against the two printed
numbers in the scan; they all agree.

Usage:
    python3 wwio_lookup.py 504
    python3 wwio_lookup.py 0o110
    python3 wwio_lookup.py --decimal 324      # look up by decimal instead
    python3 wwio_lookup.py --list             # dump the whole table
"""

import argparse
import sys

# ---------------------------------------------------------------------------
# Table 5 data.
#
# Each entry is a dict:
#   unit      -- the UNIT column text
#   mode      -- the MODE OF OPERATION column text
#   octal     -- either a single int si address, or an (start, end) tuple
#                for a range of addresses (e.g. a bank of registers)
#   item      -- (ranges only) what one "step" through the range represents,
#                used to report an offset, e.g. "Register", "Point"
#   note      -- optional footnote text from the bottom of Table 5
#
# Octal literals are written with Python's 0o prefix so the source is
# self-checking (a typo like 0o189 is a SyntaxError, not a silent bug).
# ---------------------------------------------------------------------------

DRUM_NOTE = ("Add 1000(o) [512 decimal] to this drum si address to enable "
             "the SAR end-carry to add one to the GSR.")
PRINTOUT_NOTE = "Print-out is only useful with MT1, MT2, and MT3."
LXL_NOTE = ("In L x L operation the unit stops after each read. In BLOCK "
            "operation the unit continues to supply information to the "
            "computer until stopped by another si command.")
ASSY_NOTE = ("NORMAL mode reads one line per I/O operation. AUTOMATIC "
             "ASSEMBLY mode reads three lines and assembles them into one "
             "computer word.")
CAMERA_NOTE = ("Special mode -- no 500-millisecond computer delay is "
               "allowed after this command.")

TABLE = [
    # ---------------- Magnetic Tape (block operation), MT0-MT3 ------------
    {"unit": "Magnetic Tape MT0", "mode": "Re-record, forward", "octal": 0o100},
    {"unit": "Magnetic Tape MT1", "mode": "Re-record, forward", "octal": 0o110},
    {"unit": "Magnetic Tape MT2", "mode": "Re-record, forward", "octal": 0o120},
    {"unit": "Magnetic Tape MT3", "mode": "Re-record, forward", "octal": 0o130},

    {"unit": "Magnetic Tape MT0", "mode": "Re-record, reverse", "octal": 0o101},
    {"unit": "Magnetic Tape MT1", "mode": "Re-record, reverse", "octal": 0o111},
    {"unit": "Magnetic Tape MT2", "mode": "Re-record, reverse", "octal": 0o121},
    {"unit": "Magnetic Tape MT3", "mode": "Re-record, reverse", "octal": 0o131},

    {"unit": "Magnetic Tape MT0", "mode": "Read, forward", "octal": 0o102},
    {"unit": "Magnetic Tape MT1", "mode": "Read, forward", "octal": 0o112},
    {"unit": "Magnetic Tape MT2", "mode": "Read, forward", "octal": 0o122},
    {"unit": "Magnetic Tape MT3", "mode": "Read, forward", "octal": 0o132},

    {"unit": "Magnetic Tape MT0", "mode": "Read, reverse", "octal": 0o103},
    {"unit": "Magnetic Tape MT1", "mode": "Read, reverse", "octal": 0o113},
    {"unit": "Magnetic Tape MT2", "mode": "Read, reverse", "octal": 0o123},
    {"unit": "Magnetic Tape MT3", "mode": "Read, reverse", "octal": 0o133},

    {"unit": "Magnetic Tape MT0", "mode": "Stop after record, forward", "octal": 0o104},
    {"unit": "Magnetic Tape MT1", "mode": "Stop after record, forward", "octal": 0o114},
    {"unit": "Magnetic Tape MT2", "mode": "Stop after record, forward", "octal": 0o124},
    {"unit": "Magnetic Tape MT3", "mode": "Stop after record, forward", "octal": 0o134},

    {"unit": "Magnetic Tape MT0", "mode": "Stop after record, reverse", "octal": 0o105},
    {"unit": "Magnetic Tape MT1", "mode": "Stop after record, reverse", "octal": 0o115},
    {"unit": "Magnetic Tape MT2", "mode": "Stop after record, reverse", "octal": 0o125},
    {"unit": "Magnetic Tape MT3", "mode": "Stop after record, reverse", "octal": 0o135},

    {"unit": "Magnetic Tape MT0", "mode": "Record, forward", "octal": 0o106},
    {"unit": "Magnetic Tape MT1", "mode": "Record, forward", "octal": 0o116},
    {"unit": "Magnetic Tape MT2", "mode": "Record, forward", "octal": 0o126},
    {"unit": "Magnetic Tape MT3", "mode": "Record, forward", "octal": 0o136},

    {"unit": "Magnetic Tape MT0", "mode": "Record, reverse", "octal": 0o107},
    {"unit": "Magnetic Tape MT1", "mode": "Record, reverse", "octal": 0o117},
    {"unit": "Magnetic Tape MT2", "mode": "Record, reverse", "octal": 0o127},
    {"unit": "Magnetic Tape MT3", "mode": "Record, reverse", "octal": 0o137},

    {"unit": "Magnetic Tape MT0", "mode": "Record, forward, for print-out",
     "octal": 0o146, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT1", "mode": "Record, forward, for print-out",
     "octal": 0o156, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT2", "mode": "Record, forward, for print-out",
     "octal": 0o166, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT3", "mode": "Record, forward, for print-out",
     "octal": 0o176, "note": PRINTOUT_NOTE},

    {"unit": "Magnetic Tape MT0", "mode": "Record, reverse, for print-out",
     "octal": 0o147, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT1", "mode": "Record, reverse, for print-out",
     "octal": 0o157, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT2", "mode": "Record, reverse, for print-out",
     "octal": 0o167, "note": PRINTOUT_NOTE},
    {"unit": "Magnetic Tape MT3", "mode": "Record, reverse, for print-out",
     "octal": 0o177, "note": PRINTOUT_NOTE},

    # ---------------- Paper Tape Readers -----------------------------------
    {"unit": "Paper Tape Reader PTR0 (mechanical)", "mode": "Read, normal, L x L",
     "octal": 0o200, "note": LXL_NOTE + " " + ASSY_NOTE},
    {"unit": "Paper Tape Reader PTR0 (mechanical)", "mode": "Read, auto. assembly, L x L",
     "octal": 0o202, "note": LXL_NOTE + " " + ASSY_NOTE},
    {"unit": "Paper Tape Reader PTR1 (Ferranti)", "mode": "Read, normal, block",
     "octal": 0o211, "note": LXL_NOTE + " " + ASSY_NOTE},
    {"unit": "Paper Tape Reader PTR1 (Ferranti)", "mode": "Read, auto. assembly, block",
     "octal": 0o213, "note": LXL_NOTE + " " + ASSY_NOTE},

    # ---------------- Punch --------------------------------------------------
    {"unit": "Punch", "mode": "Record, normal, 7th hole suppressed", "octal": 0o204},
    {"unit": "Punch", "mode": "Record, normal, 7th hole punched", "octal": 0o205},
    {"unit": "Punch", "mode": "Record, auto. assembly, 7th hole suppressed", "octal": 0o206},
    {"unit": "Punch", "mode": "Record, auto. assembly, 7th hole punched", "octal": 0o207},

    # ---------------- Printers ------------------------------------------------
    {"unit": "Printer 2 (computer room)", "mode": "Record", "octal": 0o225},
    {"unit": "Printer 3 (not in use)", "mode": "Record", "octal": 0o235},
    {"unit": "Printers", "mode": "Select Anelex printer, same printer group control",
     "octal": 0o214},
    {"unit": "Printers", "mode": "Select Anelex printer, clear printer group control",
     "octal": 0o215},

    # ---------------- Intervention Registers ----------------------------------
    {"unit": "Intervention Registers 0 & 1", "mode": "Read (activate)", "octal": 0o300},
    {"unit": "Intervention Registers 0 & 1", "mode": "Read (activate)", "octal": 0o301},
    {"unit": "Intervention Registers 2-31", "mode": "Read (insertion)",
     "octal": (0o302, 0o337), "item": "Register (2-31)"},

    # ---------------- MITE Buffer Storage --------------------------------------
    {"unit": "MITE Buffer Storage", "mode": "Set all timing sync.", "octal": 0o403},
    {"unit": "MITE Buffer Storage", "mode": "Clear all FF's", "octal": 0o401},
    {"unit": "MITE Buffer Storage", "mode": "Complement all counters and registers", "octal": 0o433},
    {"unit": "MITE Buffer Storage", "mode": "Set all ref. memories", "octal": 0o413},
    {"unit": "MITE Buffer Storage", "mode": "Set all data memories", "octal": 0o423},
    {"unit": "MITE Buffer Storage", "mode": "Set 'record while reading' sync.", "octal": 0o411},
    {"unit": "MITE Buffer Storage",
     "mode": "Set record sync. (succeeding slot 7 pulse sets all memories)", "octal": 0o421},
    {"unit": "MITE Buffer Storage",
     "mode": "Set record sync. (succeeding slot 7 pulse sets all data syncs.)", "octal": 0o431},

    # ---------------- Teletype ---------------------------------------------------
    {"unit": "Teletype", "mode": "Record TT buffer reg.", "octal": 0o402},

    # ---------------- Real-Time Clock (Timing Register) ---------------------------
    {"unit": "Real-Time Clock", "mode": "Fine count", "octal": 0o005},
    {"unit": "Real-Time Clock", "mode": "Coarse count", "octal": 0o007},
    {"unit": "Real-Time Clock", "mode": "Clear", "octal": 0o011},
    {"unit": "Real-Time Clock", "mode": "Complement", "octal": 0o012},

    # ---------------- Indicator Light Registers ------------------------------------
    {"unit": "Indicator Light Registers 0-7", "mode": "Record",
     "octal": (0o510, 0o517), "item": "Register (0-7)"},

    # ---------------- Display Scopes -------------------------------------------------
    {"unit": "Display Scopes", "mode": "Display points",
     "octal": (0o0600, 0o0677), "item": "Point"},
    {"unit": "Display Scopes", "mode": "Display vectors",
     "octal": (0o1600, 0o1677), "item": "Vector"},
    {"unit": "Display Scopes", "mode": "Display characters",
     "octal": (0o2600, 0o2677), "item": "Character"},
    {"unit": "Display Scopes", "mode": "Display characters",
     "octal": (0o3600, 0o3677), "item": "Character"},
    # NOTE: "Exp. Char. Display" / "Release Exp. Char. Display" also appear in
    # this section of Table 5, but the scan was not legible enough at that
    # spot to transcribe reliably -- they are omitted rather than guessed.
    # If you can read them off the original, add entries for them here.

    # ---------------- DOC System -------------------------------------------------------
    {"unit": "DOC System", "mode": "DOC send system \"A\"", "octal": 0o412},
    {"unit": "DOC System", "mode": "DOC send system \"B\"", "octal": 0o422},

    # ---------------- Crosstel. Output Coder -----------------------------------------------
    {"unit": "Crosstel. Output Coder", "mode": "Send reference", "octal": 0o420},
    {"unit": "Crosstel. Output Coder", "mode": "Send one", "octal": 0o410},
    {"unit": "Crosstel. Output Coder", "mode": "Send zero", "octal": 0o400},

    # ---------------- Raydist -----------------------------------------------------------------
    {"unit": "Raydist", "mode": "(single command)", "octal": 0o016},

    # ---------------- Auxiliary Drum ------------------------------------------------------------
    {"unit": "Auxiliary Drum", "mode": "Read, no change in address sequence",
     "octal": 0o700, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum", "mode": "Read, select new initial angular position",
     "octal": 0o701, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum", "mode": "Read, select new group",
     "octal": 0o702, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum",
     "mode": "Read, select new initial address (group and angular position)",
     "octal": 0o703, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum", "mode": "Record, no change in address sequence",
     "octal": 0o704, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum", "mode": "Record, select new initial angular position",
     "octal": 0o705, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum", "mode": "Record, select new group",
     "octal": 0o706, "note": DRUM_NOTE},
    {"unit": "Auxiliary Drum",
     "mode": "Record, select new initial address (group and angular position)",
     "octal": 0o707, "note": DRUM_NOTE},

    # ---------------- Buffer Drum ------------------------------------------------------------
    {"unit": "Buffer Drum", "mode": "Read, no change in address sequence",
     "octal": 0o710, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Read, select new initial angular position",
     "octal": 0o711, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Read, select new group",
     "octal": 0o712, "note": DRUM_NOTE},
    {"unit": "Buffer Drum",
     "mode": "Read, select new initial address (group and angular position)",
     "octal": 0o713, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Record, no change in address sequence",
     "octal": 0o714, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Record, select new initial angular position",
     "octal": 0o715, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Record, select new group",
     "octal": 0o716, "note": DRUM_NOTE},
    {"unit": "Buffer Drum",
     "mode": "Record, select new initial address (group and angular position)",
     "octal": 0o717, "note": DRUM_NOTE},
    {"unit": "Buffer Drum", "mode": "Switch fields", "octal": 0o734},

    # ---------------- Camera --------------------------------------------------------------------
    {"unit": "Camera", "mode": "Index CCDC camera", "octal": 0o024, "note": CAMERA_NOTE},
    {"unit": "Camera", "mode": "Index camera", "octal": 0o004},

    # ---------------- Height Request -----------------------------------------------------------
    {"unit": "Height Request", "mode": "Record", "octal": 0o006},

    # ---------------- Program / Marginal Checking -----------------------------------------------
    {"unit": "Program/Marginal Checking", "mode": "Switch to PB", "octal": 0o000},
    {"unit": "Program/Marginal Checking", "mode": "Condition switch to PB", "octal": 0o001},
    {"unit": "Program/Marginal Checking", "mode": "Unconditional FF / register reset",
     "octal": 0o010},
    {"unit": "Program/Marginal Checking", "mode": "Program excursion indication", "octal": 0o002},
    {"unit": "Program/Marginal Checking", "mode": "Marginal line selection", "octal": 0o003},
    {"unit": "Program/Marginal Checking", "mode": "Checking release step mode", "octal": 0o013},

    # ---------------- Core Memory -------------------------------------------------------------
    {"unit": "Core Memory", "mode": "Clear", "octal": 0o017},

    # ---------------- In-Out Check -----------------------------------------------------------
    {"unit": "In-Out Check", "mode": "Activate registers to ones", "octal": 0o504},
    {"unit": "In-Out Check", "mode": "Read indicator light registers", "octal": 0o501},
    {"unit": "In-Out Check", "mode": "Activate all light guns", "octal": 0o505},
    {"unit": "In-Out Check", "mode": "Clear all intervention registers and display switches",
     "octal": 0o500},
    {"unit": "In-Out Check", "mode": "Set all intervention registers and display switches",
     "octal": 0o502},
    {"unit": "In-Out Check", "mode": "Change room 222 +5 volts to +10 volts", "octal": 0o506},
    {"unit": "In-Out Check", "mode": "Change room 222 +5 volts to ground", "octal": 0o507},
    {"unit": "In-Out Check", "mode": "Release all test relays", "octal": 0o503},
]


def parse_octal(text):
    """Parse a user-supplied octal si address, tolerant of common ways
    someone might type/paste it (leading '0o', trailing '(o)' from the
    chart, extra whitespace, leading zeros)."""
    s = text.strip().lower()
    for prefix in ("0o", "o"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # strip a trailing "(o)" / "(0)" annotation if it was pasted in directly
    if s.endswith(")"):
        paren = s.rfind("(")
        if paren != -1:
            s = s[:paren]
    s = s.strip()
    if not s:
        raise ValueError(f"could not parse an octal number from {text!r}")
    return int(s, 8)


def lookup(octal_addr):
    """Return a list of (entry, offset_or_None) matches for octal_addr."""
    matches = []
    for entry in TABLE:
        oc = entry["octal"]
        if isinstance(oc, tuple):
            start, end = oc
            if start <= octal_addr <= end:
                matches.append((entry, octal_addr - start))
        else:
            if oc == octal_addr:
                matches.append((entry, None))
    return matches


def describe(octal_addr):
    """Build the human-readable description string for an octal si address."""
    matches = lookup(octal_addr)
    if not matches:
        return (f"si {octal_addr:#o} (octal {octal_addr:o} / decimal {octal_addr}) "
                 "is not in 2M-0277 Table 5 -- no matching I/O device/mode found.")

    lines = []
    for entry, offset in matches:
        oc = entry["octal"]
        if isinstance(oc, tuple):
            start, end = oc
            addr_str = f"octal {start:o}-{end:o} (decimal {start}-{end})"
            offset_str = f", {entry.get('item', 'item')} offset {offset}" if offset is not None else ""
        else:
            addr_str = f"octal {oc:o} (decimal {oc})"
            offset_str = ""
        line = f"{entry['unit']}: {entry['mode']}  [{addr_str}{offset_str}]"
        if entry.get("note"):
            line += f"\n    Note: {entry['note']}"
        lines.append(line)
    return "\n".join(lines)


def list_table():
    lines = []
    for entry in sorted(TABLE, key=lambda e: e["octal"][0] if isinstance(e["octal"], tuple) else e["octal"]):
        oc = entry["octal"]
        if isinstance(oc, tuple):
            start, end = oc
            addr_str = f"{start:03o}-{end:03o} (o) / {start}-{end} (d)"
        else:
            addr_str = f"{oc:03o} (o) / {oc} (d)"
        lines.append(f"{addr_str:>20}  {entry['unit']} -- {entry['mode']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Look up a Whirlwind si I/O address (Table 5, 2M-0277) "
                     "and report which device/mode it refers to.")
    parser.add_argument("address", nargs="?",
                         help="si address in octal, e.g. 504, 0o110, 0504(o)")
    parser.add_argument("--decimal", action="store_true",
                         help="treat ADDRESS as decimal instead of octal")
    parser.add_argument("--list", action="store_true",
                         help="print the whole Table 5 lookup, sorted by address")
    args = parser.parse_args(argv)

    if args.list:
        print(list_table())
        return 0

    if not args.address:
        parser.print_help()
        return 1

    try:
        if args.decimal:
            octal_addr = int(args.address.strip())
        else:
            octal_addr = parse_octal(args.address)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(describe(octal_addr))
    return 0


if __name__ == "__main__":
    sys.exit(main())