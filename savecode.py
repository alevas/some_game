"""
Noir Language Riddles: The Babel Conspiracy
Save codes: a whole case written out as text, for players whose saves don't last
(the browser version keeps its saves only until the tab is closed).

A code is the saved game as JSON, deflated, with a checksum, written in base32
(A-Z and 2-7, so no 0/O or 1/I mix-ups) in groups of five after a version prefix:

    N1-ABCDE-FGHIJ-KLMNO-...

It encodes whatever dict it is given, so new GameState fields are included
automatically. Nothing in here prints or reads input.
"""

import base64
import binascii
import json
import re
import zlib
from typing import List

VERSION = 1          # one digit; bump it (keeping the old decoder) if the format or dictionary changes
PREFIX = "N"
GROUP = 5            # characters per group
MAX_CODE = 5000      # characters; a finished case is about 250
MAX_JSON = 200_000   # bytes, so a hostile code can't inflate into something huge

# Strings save codes usually contain. Deflating against them makes a code about three
# times shorter. They are only a hint: anything else still encodes, just less tightly.
# But every code already given out depends on them, so never edit this for version 1.
_DICTIONARY = (
    # Evidence, and who it was shown to
    '["Case File","Sugar Packet","Spanish Dictionary","Cipher Wheel","Arvanitika Notes","Family Tree",'
    '"Vodka Bottle","Lantern","History Book","Photograph","Dental Mirror","Viking Brooch","Sugar Cube",'
    '"Peace Symbol","Portuguese Bread","Language Map","Papyrus Scroll","Quill Pen","Religious Text",'
    '"Magnifying Glass","Namaste Symbol","Parish Ledger","Norman Menu","Waiter\'s Notepad"]'
    '["ClientOffice:Photograph","Library:Case File","Cafe:Sugar Packet","Church:Arvanitika Notes",'
    '"Archive:Religious Text"]'
    '"rookie","noir",'
    # A fresh case last: deflate reaches the nearest text most cheaply
    '{"current_location":"ClientOffice","solved_riddles":[],"fumbled_riddles":[],"inventory":[],'
    '"sanity":3,"max_sanity":3,"difficulty":"detective","score":0,"streak":0,'
    '"visited_locations":["ClientOffice"],"unlocked_locations":["ClientOffice"],"presented":[]}'
).encode()

_MISTYPES = str.maketrans("018", "OIB")  # digits that look like base32 letters


class SaveCodeError(ValueError):
    """A code that can't be read. The message is written for the player."""


def encode(data: dict) -> str:
    packer = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, _DICTIONARY)
    payload = packer.compress(json.dumps(data, separators=(",", ":")).encode()) + packer.flush()
    check = zlib.crc32(bytes([VERSION]) + payload).to_bytes(4, "big")
    body = base64.b32encode(payload + check).decode().rstrip("=")
    return "-".join([f"{PREFIX}{VERSION}"] + [body[i:i + GROUP] for i in range(0, len(body), GROUP)])


def decode(code: str) -> dict:
    """The dict inside a code. Forgives case, spaces, dashes, line breaks and 0/1/8 for O/I/B."""
    text = re.sub(r"[^0-9A-Za-z]", "", code).upper()
    text = re.sub(rf"^{PREFIX}[IL]", f"{PREFIX}1", text)  # N1 copied as NI or Nl
    if not text:
        raise SaveCodeError("Type or paste a save code first.")
    if len(text) > MAX_CODE:
        raise SaveCodeError("That is far too long to be a save code.")
    if not re.match(rf"{PREFIX}\d", text):
        raise SaveCodeError(f"That isn't a save code. Save codes start with {PREFIX}{VERSION}.")
    if int(text[1]) != VERSION:
        raise SaveCodeError(f"That code comes from a different version of the game ({text[:2]}), "
                            f"so this one can't read it.")

    body = text[2:].translate(_MISTYPES)
    stray = sorted(set(re.sub(r"[A-Z2-7]", "", body)))
    if stray:
        raise SaveCodeError(f"Save codes never contain {' or '.join(stray)}. Check those characters.")
    try:
        raw = base64.b32decode(body + "=" * (-len(body) % 8))
    except binascii.Error:
        raw = b""
    if len(raw) < 5:
        raise SaveCodeError("That code is incomplete: a character is missing or one too many.")

    payload, check = raw[:-4], raw[-4:]
    if zlib.crc32(bytes([VERSION]) + payload).to_bytes(4, "big") != check:
        raise SaveCodeError("That code doesn't check out. A character is probably mistyped or missing; "
                            "compare it with the original.")
    try:
        unpacker = zlib.decompressobj(-15, zdict=_DICTIONARY)
        data = json.loads(unpacker.decompress(payload, MAX_JSON))
        if unpacker.unconsumed_tail or not unpacker.eof:
            raise ValueError("too big")
    except (zlib.error, ValueError):
        raise SaveCodeError("That code is damaged and can't be read.") from None
    if not isinstance(data, dict):
        raise SaveCodeError("That code doesn't hold a case this game can open.")
    return data


def lines(code: str, groups: int = 8) -> List[str]:
    """A code split into lines of a few groups each, for showing on screen"""
    parts = code.split("-")
    return ["-".join(parts[i:i + groups]) for i in range(0, len(parts), groups)]
