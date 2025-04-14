#! /usr/bin/env python3
# Written by Martin v. Löwis <loewis@informatik.hu-berlin.de>

"""Generate binary message catalog from textual translation description.

This program converts a textual Uniforum-style message catalog (.po file) into
a binary GNU catalog (.mo file).  This is essentially the same function as the
GNU msgfmt program, however, it is a simpler implementation.  Currently it
does not handle plural forms but it does handle message contexts.

Usage: msgfmt.py [OPTIONS] filename.po

Options:
    -o file
    --output-file=file
        Specify the output file to write to.  If omitted, output will go to a
        file named filename.mo (based off the input file name).

    -h
    --help
        Print this message and exit.

    -V
    --version
        Display version information and exit.
"""

import os
import sys
import getopt
import struct
import array
from email.parser import HeaderParser
from enum import StrEnum
from dataclasses import dataclass, field
import codecs
import re


__version__ = "1.2"


def usage(code, msg=''):
    print(__doc__, file=sys.stderr)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)


def _key_for(msgid, msgctxt=None):
    if msgctxt is None:
        return msgid
    return (msgctxt, msgid)


def _format_key(msgid, msgctxt=None):
    if msgctxt is None:
        return msgid
    else:
        return b"%b\x04%b" % (msgctxt, msgid)


class POSection(StrEnum):
    COMMENT = 'comment'
    CTXT = 'msgctxt'
    ID = 'msgid'
    PLURAL = 'msgid_plural'
    STR = 'msgstr'


def parse_po(po, filename):
    """Parse a PO file."""
    if po.startswith(codecs.BOM_UTF8):
        raise ValueError(
            f"The file {filename} starts with a UTF-8 BOM which is not "
            "allowed in .po files.\nPlease save the file without a BOM "
            "and try again.")

    @dataclass
    class ParserState:
        filename: str
        lineno: int = 0
        # Start off assuming Latin-1, so everything decodes without failure,
        # until we know the exact encoding
        encoding: str = 'latin-1'
        # Current section
        section: POSection | None = None
        # Current message data
        msgid: str | None = None
        msgid_plural: str | None = None
        msgctxt: str | None = None
        msgstr: str | list[str] | None = None
        fuzzy: bool = False
        # All parsed messages
        messages: dict = field(default_factory=dict)

        @property
        def is_plural(self):
            return self.msgid_plural is not None


    state = ParserState(filename)
    # Parse the PO file
    for line in po.splitlines():
        state.lineno += 1

        # Skip empty lines
        if not line.strip():
            continue

        if line.startswith(b'#'):
            parse_comment(state, line)
        elif line.startswith(b'msgctxt'):
            parse_msgctxt(state, line)
        elif line.startswith(b'msgid_plural'):
            parse_msgid_plural(state, line)
        elif line.startswith(b'msgid'):
            parse_msgid(state, line)
        elif line.startswith(b'msgstr'):
            parse_msgstr(state, line)
        else:
            # Line containing only a string without a keyword
            # This will be appended to the previous section
            parse_line(state, line)

    if state.section == POSection.CTXT:
        raise ValueError(f'{filename}:{state.lineno}: '
                         'Missing msgid after msgctxt')
    if state.section == POSection.ID:
        raise ValueError(f'{filename}:{state.lineno}: '
                         'Missing msgstr after msgid')
    elif state.section == POSection.STR:
        # Add last entry
        _add_message(state)
    return list(state.messages.values())


def parse_comment(state, line):
    if state.section not in (None, POSection.COMMENT, POSection.STR):
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'Comment line not allowed after {state.section}')

    if state.section == POSection.STR:
        # Previous msgstr section is finished so we need to add the message
        _add_message(state)
    if line.startswith(b'#,') and b'fuzzy' in line:
        # This is a fuzzy mark
        state.fuzzy = True
    state.section = POSection.COMMENT


def parse_msgctxt(state, line):
    if state.section not in (None, POSection.COMMENT, POSection.STR):
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'msgctxt not allowed after {state.section}')

    if state.section == POSection.STR:
        # Previous msgstr section is finished so we need to add the message
        _add_message(state)
    line = line.decode(state.encoding).removeprefix('msgctxt')
    state.msgctxt = parse_quoted_strings(state, line)
    state.section = POSection.CTXT


def parse_msgid_plural(state, line):
    if state.section is None:
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         'msgid_plural must be preceded by msgid')
    if state.section != POSection.ID:
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'msgid_plural not allowed after {state.section}')

    line = line.decode(state.encoding).removeprefix('msgid_plural')
    state.msgid_plural = parse_quoted_strings(state, line)
    state.section = POSection.PLURAL


def parse_msgid(state, line):
    if state.section not in (None, POSection.COMMENT,
                             POSection.STR, POSection.CTXT):
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'msgid not allowed after {state.section}')

    if state.section == POSection.STR:
        # Previous msgstr section is finished so we need to add the message
        _add_message(state)
    line = line.decode(state.encoding).removeprefix('msgid')
    state.msgid = parse_quoted_strings(state, line)
    state.section = POSection.ID


def parse_msgstr(state, line):
    if state.section is None:
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         'msgstr must be preceded by msgid')
    if state.section not in (POSection.STR, POSection.ID, POSection.PLURAL):
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'msgstr not allowed after {state.section}')

    line = line.decode(state.encoding)
    if match := re.match(r'^msgstr\[(\d+)\]', line):
        # This is a plural msgstr, e.g. msgstr[0]
        if not state.is_plural:
            raise ValueError(f'{state.filename}:{state.lineno}: '
                             'Missing msgid_plural section')
        index = int(match.group(1))
        line = line.removeprefix(match.group())
        if state.msgstr is None:
            state.msgstr = []
        next_plural_index = len(state.msgstr)
        if index != next_plural_index:
            raise ValueError(f'{state.filename}:{state.lineno}: '
                             'Plural form has incorrect index, found '
                             f"'{index}' but should be '{next_plural_index}'")
        state.msgstr.append(parse_quoted_strings(state, line))
    else:
        # This is a regular (non-plural) msgstr
        if state.is_plural:
            raise ValueError(f'{state.filename}:{state.lineno}: '
                             'Indexed msgstr required after msgid_plural')
        if state.section == POSection.STR:
            raise ValueError(f'{state.filename}:{state.lineno}: '
                             'msgstr not allowed after msgstr')
        line = line.removeprefix('msgstr')
        state.msgstr = parse_quoted_strings(state, line)
    state.section = POSection.STR


def parse_line(state, line):
    line = parse_quoted_strings(state, line.decode(state.encoding))
    if state.section == POSection.CTXT:
        state.msgctxt += line
    elif state.section == POSection.PLURAL:
        state.msgid_plural += line
    elif state.section == POSection.ID:
        state.msgid += line
    elif state.section == POSection.STR:
        if isinstance(state.msgstr, list):
            # This belongs to the last msgstr[N] entry
            state.msgstr[-1] += line
        else:
            state.msgstr += line
    else:
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'Syntax error before:\n{line}')


def parse_quoted_strings(state, line):
    """
    Parse a line containing one or more quoted PO strings separated
    by whitespace.
    Example: "Hello, " "world!" -> 'Hello, world!'
    """
    line = line.strip()
    if not line:
        return ''

    quoted_string = r'"([^"\\]|\\.)*"'
    # One or more quoted strings, possibly separated by whitespace
    quoted_strings = fr'^({quoted_string}\s*)+$'

    if not re.match(quoted_strings, line):
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f'Syntax error: {line}')

    string = ''
    for match in re.finditer(quoted_string, line):
        part = match.group()
        string += parse_quoted_string(state, part)
    return string


def parse_quoted_string(state, string):
    """Parse a single quoted PO string."""
    # Check if there are any disallowed escape sequences
    # The allowed escape sequences are:
    #   - \n, \r, \t, \\, \", \a, \b, \f, \v
    #   - Octal escapes: \o, \oo, \ooo
    #   - Hex escapes: \xh, \xhh, ...
    if match := re.search(r'\\[^"\\abfnrtvx0-7]|\\x[^0-9a-fA-F]', string):
        escape = match.group()
        raise ValueError(f'{state.filename}:{state.lineno}: '
                         f"Invalid escape sequence: '{escape}'")


def _add_message(state):
    key = _key_for(state.msgid, state.msgctxt)
    if key in state.messages:
        # PO files don't allow duplicate entries
        raise ValueError(f"{state.filename}:{state.lineno}: "
                         f"Duplicate entry: {key!r}")
    state.messages[key] = {'msgctxt': state.msgctxt,
                           'msgid': state.msgid,
                           'msgid_plural': state.msgid_plural,
                           'msgstr': state.msgstr,
                           'fuzzy': state.fuzzy}
    if state.msgid == "":
        # This is the header, see whether there is an encoding declaration
        state.encoding = _get_encoding(state.msgstr)
    # Reset the message data
    state.msgctxt = None
    state.msgid = None
    state.msgid_plural = None
    state.msgstr = None
    state.fuzzy = False


def _get_encoding(msgstr):
    """Get the encoding from the header msgstr, if provided."""
    p = HeaderParser()
    charset = p.parsestr(msgstr).get_content_charset()
    return charset or 'latin-1'


def generate(messages):
    "Return the generated output."
    # the keys are sorted in the .mo file
    keys = sorted(messages.keys())
    offsets = []
    ids = strs = b''
    for id in keys:
        message = messages[id]
        if isinstance(id, tuple):
            # This is a contexted message
            id = _format_key(id[1], id[0])
        # For each string, we need size and file offset.  Each string is NUL
        # terminated; the NUL does not count into the size.
        offsets.append((len(ids), len(id), len(strs), len(message)))
        ids += id + b'\0'
        strs += messages[id] + b'\0'
    output = ''
    # The header is 7 32-bit unsigned integers.  We don't use hash tables, so
    # the keys start right after the index tables.
    # translated string.
    keystart = 7*4+16*len(keys)
    # and the values start after the keys
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    # The string table first has the list of keys, then the list of values.
    # Each entry has first the size of the string, then the file offset.
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1+keystart]
        voffsets += [l2, o2+valuestart]
    offsets = koffsets + voffsets
    output = struct.pack("Iiiiiii",
                         0x950412de,       # Magic
                         0,                 # Version
                         len(keys),         # # of entries
                         7*4,               # start of key index
                         7*4+len(keys)*8,   # start of value index
                         0, 0)              # size and offset of hash table
    output += array.array("i", offsets).tobytes()
    output += ids
    output += strs
    return output


def make(filename, outfile):
    # Compute .mo name from .po name and arguments
    if filename.endswith('.po'):
        infile = filename
    else:
        infile = filename + '.po'
    if outfile is None:
        outfile = os.path.splitext(infile)[0] + '.mo'

    try:
        with open(infile, 'rb') as f:
            lines = f.readlines()
    except IOError as msg:
        print(msg, file=sys.stderr)
        sys.exit(1)

    if lines[0].startswith(codecs.BOM_UTF8):
        print(
            f"The file {infile} starts with a UTF-8 BOM which is not allowed in .po files.\n"
            "Please save the file without a BOM and try again.",
            file=sys.stderr
        )
        sys.exit(1)

    messages = parse_po(b''.join(lines), infile)
    # Compute output
    output = generate(messages)

    try:
        with open(outfile,"wb") as f:
            f.write(output)
    except IOError as msg:
        print(msg, file=sys.stderr)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hVo:',
                                   ['help', 'version', 'output-file='])
    except getopt.error as msg:
        usage(1, msg)

    outfile = None
    # parse options
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-V', '--version'):
            print("msgfmt.py", __version__)
            sys.exit(0)
        elif opt in ('-o', '--output-file'):
            outfile = arg
    # do it
    if not args:
        print('No input file given', file=sys.stderr)
        print("Try `msgfmt --help' for more information.", file=sys.stderr)
        return

    for filename in args:
        make(filename, outfile)


if __name__ == '__main__':
    main()
