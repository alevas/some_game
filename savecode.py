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

VERSION = 2          # one digit; bump it (keeping the old dictionaries) if the format or dictionary changes
PREFIX = "N"
GROUP = 5            # characters per group
MAX_CODE = 5000      # characters; a finished case is about 250
MAX_JSON = 200_000   # bytes, so a hostile code can't inflate into something huge

# Strings save codes usually contain. Deflating against them makes a code about three
# times shorter. They are only a hint: anything else still encodes, just less tightly.
# But every code already given out depends on them, so never edit one that has been used.
_DICTIONARY_V1 = (
    # Evidence, and who it was shown to
    '["Case File","Sugar Packet","Spanish Dictionary","Cipher Wheel","Arvanitika Notes","Family Tree",'
    '"Vodka Bottle","Lantern","History Book","Photograph","Dental Mirror","Viking Brooch","Sugar Cube",'
    '"Peace Symbol","Portuguese Bread","Language Map","Papyrus Scroll","Quill Pen","Religious Text",'
    '"Magnifying Glass","Namaste Symbol","Parish Ledger","Norman Menu","Waiter\'s Notepad"]'
    '["ClientOffice:Photograph","Library:Case File","Cafe:Sugar Packet","Church:Arvanitika Notes",'
    '"Archive:Religious Text"]'
    '"rookie","noir",'
    # Who can be questioned, as used in trust, asked and lies_broken
    '"Klaus Weber","Herr Schmidt","Karl","Father Thomas","Igor Volkov",'
    # A fresh case last: deflate reaches the nearest text most cheaply
    '{"current_location":"ClientOffice","solved_riddles":[],"fumbled_riddles":[],"inventory":[],'
    '"sanity":3,"max_sanity":3,"difficulty":"detective","score":0,"streak":0,'
    '"visited_locations":["ClientOffice"],"unlocked_locations":["ClientOffice"],"presented":[],'
    '"trust":{},"asked":[],"lies_broken":[],"favors_used":[]}'
).encode()

# Version 2 adds the riddle pick per case (one number per place), the daily case and the
# showdown log, plus the evidence from the bigger riddle pool
_DICTIONARY_V2 = (
    '"Calling Card","Ball of Thread","Wax Tablet","Leather Glove","Pressed Flower",'
    '"clean","slip","dodge","lost",'
).encode() + _DICTIONARY_V1[:-1] + (
    ',"selection":{"ClientOffice":0,"Library":,"Cafe":,"Church":,"Archive":},'
    '"daily":"","replay":false,"showdown_log":[]}'
).encode()

_DICTIONARIES = {1: _DICTIONARY_V1, 2: _DICTIONARY_V2}

_MISTYPES = str.maketrans("018", "OIB")  # digits that look like base32 letters


class SaveCodeError(ValueError):
    """A code that can't be read. The message is written for the player."""


def encode(data: dict, version: int = VERSION) -> str:
    packer = zlib.compressobj(9, zlib.DEFLATED, -15, 9, zlib.Z_DEFAULT_STRATEGY, _DICTIONARIES[version])
    payload = packer.compress(json.dumps(data, separators=(",", ":")).encode()) + packer.flush()
    check = zlib.crc32(bytes([version]) + payload).to_bytes(4, "big")
    body = base64.b32encode(payload + check).decode().rstrip("=")
    return "-".join([f"{PREFIX}{version}"] + [body[i:i + GROUP] for i in range(0, len(body), GROUP)])


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
    version = int(text[1])
    if version not in _DICTIONARIES:
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
    if zlib.crc32(bytes([version]) + payload).to_bytes(4, "big") != check:
        raise SaveCodeError("That code doesn't check out. A character is probably mistyped or missing; "
                            "compare it with the original.")
    try:
        unpacker = zlib.decompressobj(-15, zdict=_DICTIONARIES[version])
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
