"""Updates the symbols subrepository and regenerates the symbols used by
the editor (port of scripts/update-symbols.js).

Run from the repository root:

    python scripts/update_symbols.py

Each `symbols/<Game>.sym` file (lines of `ADDR,type,name[,desc]`) becomes
`partyplanner64/lib/symbols/<Game>.json`, a list of
{"addr", "type", "name"[, "desc"]} objects.
"""

import json
import os
import re
import subprocess
import sys

SYMBOLS_DIR = "symbols"
SYMBOLS_OUT_DIR = os.path.join("partyplanner64", "lib", "symbols")


def parse_int16(text):
    """parseInt(text, 16): leading hex digits (an optional 0x), or None (NaN)."""
    m = re.match(r"\s*([+-]?)(?:0[xX])?([0-9a-fA-F]+)", text)
    if not m:
        return None
    value = int(m.group(2), 16)
    return -value if m.group(1) == "-" else value


def convert_symbols(text):
    """Return the symbol list of a .sym file's text."""
    lines = re.split(r"\r?\n", text)
    objs = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        pieces = line.split(",")
        if len(pieces) < 3:
            continue

        # Exclude iffy symbols
        sym_name = pieces[2]
        if sym_name.endswith("?") or sym_name.startswith("?"):
            continue

        obj = {
            "addr": parse_int16(pieces[0]),
            "type": pieces[1],
            "name": sym_name,
        }
        if len(pieces) > 3 and pieces[3]:
            obj["desc"] = pieces[3]
        objs.append(obj)
    return objs


def symbols_to_json(symbols):
    """Serialize a symbol list: one symbol per line."""
    return "[\n" + ",\n".join(json.dumps(s, ensure_ascii=False) for s in symbols) + "\n]\n"


def main():
    result = subprocess.run(["git", "submodule", "update", "--remote"],
                            capture_output=True, text=True)
    if result.returncode != 0 or result.stderr:
        sys.stderr.write("Error updating symbols repository! %s, %s"
                         % (result.returncode, result.stderr))
    else:
        print("Updating symbols repository...")

    try:
        files = sorted(os.listdir(SYMBOLS_DIR))
    except OSError:
        print("Could not read the symbols directory", file=sys.stderr)
        sys.exit(1)

    for file in files:
        if not file.lower().endswith(".sym"):
            continue

        inputfile = os.path.join(SYMBOLS_DIR, file)
        try:
            with open(inputfile, encoding="utf-8") as f:
                contents = f.read()
        except OSError:
            print("Could not read symbol file: " + file, file=sys.stderr)
            sys.exit(1)

        output = symbols_to_json(convert_symbols(contents))
        filename = os.path.basename(file)[:-len(".sym")]
        print("Writing " + filename + "...")

        outputfile = os.path.join(SYMBOLS_OUT_DIR, filename + ".json")
        try:
            with open(outputfile, "w", encoding="utf-8") as f:
                f.write(output)
        except OSError as err:
            print("Could not write symbol file: %s: %s" % (file, err), file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
