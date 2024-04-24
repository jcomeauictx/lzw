#!/usr/bin/python3 -OO
'''
Lempel-Ziv-Welch compression and decompression

A different approach, hopefully cleaner and faster than lzw.py
'''
import sys, os, struct, io, logging  # pylint: disable=multiple-imports

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARNING)

# pylint: disable=consider-using-f-string  # "we don't do that here"
BUFFER_SIZE = 8192  # see "8K" on p. 56 of TIFF6.pdf
# min and max bit lengths recommended on p. 60 of TIFF6.pdf
MINBITS = 9
MAXBITS = 12
# encoding and decoding tables, make shallow copies of these for use
STRINGTABLE = {n: bytes([n]) for n in range(256)}  # codes to strings
CODETABLE = dict(map(reversed, STRINGTABLE.items()))  # strings to codes
CODEMAP = {n: n for n in range(256)}  # codes to codes
CLEAR_CODE = 256  # see TIFF6.pdf pp. 58-63 for use of special codes
END_OF_INFO_CODE = 257
SPECIAL = {CLEAR_CODE: None, END_OF_INFO_CODE: None}

def doctest_debug(*args):  # pylint: disable=unused-argument
    '''
    redefined below if running doctest module
    '''
    return

class CodeReader(io.BufferedReader):
    r'''
    Create an iterator for the variable-bitlength codes in a LZW file

    This won't have any information about the code table, so `bitlength`
    will need to be manipulated by the caller; otherwise it will treat
    the entire input stream by default as 9-bit codes.

    >>> CodeReader(io.BytesIO(b'UUUUUUUUU')).read()
    [170, 341, 170, 341, 170, 341, 170, 341]
    >>> CodeReader(io.BytesIO(b'UUUUUUUU')).read()
    [170, 341, 170, 341, 170, 341, 170, 256]
    '''
    def __init__(self, stream, buffer_size=BUFFER_SIZE,
                 minbits=MINBITS, maxbits=MAXBITS):
        super().__init__(stream, buffer_size)
        self.bitlength = self.minbits = minbits
        self.maxbits = maxbits
        self.bitstream = bytearray()

    def __iter__(self):
        '''
        Along with `__next__`, allows this to function as an iterator
        '''
        return self

    def __next__(self):
        '''
        Return the next code from the stream
        '''
        while len(self.bitstream) < self.bitlength:
            nextbyte = super().read(1)
            doctest_debug('nextbyte: %s', nextbyte)
            if not nextbyte:  # empty string or None: EndOfFile
                if not self.bitstream:
                    raise StopIteration
                self.bitstream.extend(  # pad remaining bits with zeroes
                    b'0' * (self.bitlength - len(self.bitstream)))
            else:
                self.bitstream.extend(format(ord(nextbyte), '08b').encode())
        result = int(bytes(self.bitstream[:self.bitlength]), 2)
        self.bitstream[:self.bitlength] = []
        return result

    def read(self, count=None):
        '''
        Read and return a list of codes

        Shouldn't be used except for doctests
        '''
        count = BUFFER_SIZE if count in (None, -1) else count
        result = []
        for _ in range(count):
            try:
                result.append(next(self))
            except StopIteration:
                break
        return result

class LZWReader(io.BufferedReader):
    r'''
    Implementation of LZW decompressor

    adapted from pseudocode on page 61 of TIFF6.pdf

        while ((Code = GetNextCode()) != EoiCode) {
            if (Code == ClearCode) {
                InitializeTable();
                //Code = GetNextCode();  // NOTE: we don't do this here,
                //if (Code == EoiCode)   // let next loop handle it.
                //   break;
                //WriteString(StringFromCode(Code));
                //OldCode = Code;
            } /* end of ClearCode case */
            else {
                if (IsInTable(Code)) {
                    WriteString(StringFromCode(Code));
                    AddStringToTable(StringFromCode(OldCode) +
                        FirstChar(StringFromCode(Code)));
                    OldCode = Code;
                } else {
                    OutString = StringFromCode(OldCode) +
                        FirstChar(StringFromCode(OldCode));
                    WriteString(OutString);
                    AddStringToTable(OutString);
                    OldCode = Code;
                }
            } /* end of not-ClearCode case */
        } /* end of while loop */

    let's simplify the nested if-else above for DRY:

                if (IsInTable(Code)) {
                    OutString = StringFromCode(Code);
                    StoreString = StringFromCode(OldCode) +
                        FirstChar(StringFromCode(Code);
                } else {
                    OutString = StringFromCode(OldCode) +
                        FirstChar(StringFromCode(OldCode);
                    StoreString = OutString;
                }
                WriteString(OutString);
                AddStringToTable(StoreString);
                OldCode = Code;

    much better, except that since we ignore the suggestion in the
    original pseudocode to process separately the first code after ClearCode,
    there will be an exception trying to access OldCode for the first
    in-table Code. We handle it by setting StoreString to null (None) in
    that case. So the complete rewritten pseudocode would be:

        while ((Code = GetNextCode()) != EoiCode) {
            if (Code == ClearCode) {
                InitializeTable();
            } /* end of ClearCode case */
            else {
                if (IsInTable(Code)) {
                    OutString = StringFromCode(Code);
                    try {
                        StoreString = StringFromCode(OldCode) +
                            FirstChar(StringFromCode(Code);
                    } except(NoOldCodeImmediatelyAfterClearCode) {
                        StoreString = null;
                    }
                } else {
                    OutString = StringFromCode(OldCode) +
                        FirstChar(StringFromCode(OldCode);
                    StoreString = OutString;
                }
                WriteString(OutString);
                if (StoreString != null) AddStringToTable(StoreString);
                OldCode = Code;
            }
        }

    Test cases from https://rosettacode.org/wiki/LZW_compression
    >>> decode = lambda codes: LZWReader(iter(codes), special=False).read()
    >>> codes = [84,79,66,69,79,82,78,79,84,256,258,260,265,259,261,263]
    >>> decode(codes)
    b'TOBEORNOTTOBEORTOBEORNOT'
    >>> codes = [84,111,32,98,101,32,111,114,32,110,111,116,32,116,257,259,
    ...     268,104,97,267,105,115,272,260,113,117,101,115,116,105,111,110,33]
    >>> decode(codes)
    b'To be or not to be that is the question!'
    >>> codes = [34,84,104,101,114,101,32,105,115,32,110,111,116,104,
    ...     105,110,103,32,112,259,109,97,110,101,110,116,32,101,120,
    ...     99,101,112,281,99,104,277,103,101,46,34,32,296,45,298,296,
    ...     32,72,259,97,99,108,105,116,117,264,32,91,53,52,48,32,299,
    ...     52,55,53,32,66,67,69,93]
    >>> check = decode(codes)
    >>> divider = check.index(b'.') + 2
    >>> check[:divider]
    b'"There is nothing permanent except change."'
    >>> check[divider:]
    b'   ---   Heraclitus  [540 -- 475 BCE]'

    # Test case from TIFF6.pdf pages 59-60 (see lzw.py for complete example)
    >>> codes = b'\x80\x01\xe0@\x80D\x08\x0c\x06\x80\x80'
    >>> LZWReader(io.BytesIO(codes)).read()
    b'\x07\x07\x07\x08\x08\x07\x07\x06\x06'
    '''
    def __init__(self, stream, # pylint: disable=too-many-arguments
                 buffer_size=BUFFER_SIZE, minbits=MINBITS,
                 maxbits=MAXBITS, special=True):
        try:
            super().__init__(stream, buffer_size)
            doctest_debug('Using CodeReader(%s) iterator', stream)
            self.codesource = CodeReader(stream, buffer_size, minbits, maxbits)
        except AttributeError:
            logging.warning('Using non-CodeReader iterator for test purposes')
            self.codesource = stream
        self.special = special  # False for rosettacode.org examples
        self.codedict = {}
        self.oldcode = None
        self.buffer = bytearray()
        self.initialize_table()

    def __next__(self):
        '''
        returns next string from table, adjusting bitlength as we go
        '''
        code = next(self.codesource)
        outstring = storestring = None
        doctest_debug('next LZW code: %s', code)
        if code == END_OF_INFO_CODE and self.special:
            if self.codesource.bitstream.strip(b'0'):
                logging.error('bitstream remaining: %s',
                              self.codesource.bitstream)
                raise ValueError('Nonzero bits left after EOI code')
            self.codesource.bitstream[:] = []  # clear the buffer
            raise StopIteration
        if code == CLEAR_CODE and self.special:
            self.initialize_table()
        elif code in self.codedict:
            outstring = self.codedict[code]
            try:
                storestring = self.codedict[self.oldcode] + outstring[0:1]
            except (KeyError, TypeError):  # oldcode or outstring is None
                pass
        else:
            outstring = self.codedict[self.oldcode]
            outstring += outstring[0:1]
            storestring = outstring
        if storestring is not None:
            self.add_string_to_table(storestring)
        self.oldcode = code
        return outstring or b''  # don't return None if ClearCode

    def initialize_table(self):
        '''
        (Re-)Initialize code table
        '''
        self.codedict.clear()
        self.codedict.update(STRINGTABLE)
        if self.special:
            self.codedict.update(SPECIAL)
        try:
            self.codesource.bitlength = self.codesource.minbits
        except AttributeError:
            logging.warning('No such attribute self.codesource.bitlength')

    def read(self, count=None):
        '''
        Return `count` bytes, defaulting to all available
        '''
        count = count or sys.maxsize
        while len(self.buffer) < count:
            try:
                chunk = next(self)
                doctest_debug('next chunk: ...%s', chunk[-10:])
                self.buffer.extend(chunk)
            except StopIteration:
                break
        result = bytes(self.buffer[:count])
        self.buffer[:count] = []
        return result

    def add_string_to_table(self, bytestring):
        '''
        Add bytestring to code table
        '''
        if bytestring is not None:
            newkey = len(self.codedict)
            self.codedict[newkey] = bytestring
            doctest_debug('set codedict[%d] = ...%s', newkey, bytestring[-10:])
            # at 510, 1022, and 2046, bump bitlength
            if (newkey + 2).bit_length() == (newkey + 1).bit_length() + 1:
                try:
                    if self.codesource.bitlength < self.codesource.maxbits:
                        doctest_debug(
                            'increasing bitlength to %d at code %d',
                            self.codesource.bitlength + 1, newkey)
                        self.codesource.bitlength += 1
                except AttributeError:
                    logging.warning('Cannot change bitlength at code %d',
                                    newkey)

class CodeWriter(io.BufferedWriter):
    r'''
    Write out variable-bitlength codes as bytes

    Example from p. 60 of TIFF6.pdf:

    >>> stream = io.BytesIO()
    >>> writer = CodeWriter(stream, special=False)
    >>> # the following bytes won't actually write out to underlying stream now,
    >>> # since at 9 bits per, they won't align to a byte boundary.
    >>> writer.write([7, 258, 8, 8, 258, 6])
    0
    >>> writer.flush() # now when we flush it, they should be written.
    >>> stream.getvalue()
    b'\x03\xc0\x81\x00\x88\x10\x18'
    '''
    def __init__(self, stream,  # pylint: disable=too-many-arguments
                 buffer_size=BUFFER_SIZE,
                 minbits=MINBITS, maxbits=MAXBITS,
                 special=True):
        super().__init__(stream, buffer_size)
        self.bitlength = self.minbits = minbits
        self.maxbits = maxbits
        self.special = special
        self.bitstream = 0
        self.bits = 0  # number of bits queued in (int) buffer
        if special:
            self.write([CLEAR_CODE])

    def write(self, array):
        '''
        convert variable-length numbers to bytes and write to underlying stream
        '''
        written = 0
        for number in array:
            self.bitstream <<= self.bitlength
            self.bitstream |= number
            self.bits += self.bitlength
        if self.bits and self.bits % 8 == 0:
            count = self.bits // 8
            bytestring = self.bitstream.to_bytes(count, 'big')
            doctest_debug('CodeWriter writing %d bytes: ...%s', count,
                          bytestring[-10:])
            written += super().write(bytestring)
            self.bitstream = self.bits = 0
        return written

    def flush(self, final=True):
        '''
        flush any unwritten codes
        '''
        doctest_debug('flushing CodeWriter')
        if self.special and final:
            self.write([END_OF_INFO_CODE])
        over = self.bits % 8
        if over:
            shift = 8 - over
            doctest_debug('shifting self.bitstream %d bits', shift)
            self.bitstream <<= shift
            self.bits += shift
            written = self.write([])
            doctest_debug('%d bytes written to underlying stream', written)
        super().flush()
        doctest_debug('ending CodeWriter.flush()')

class LZWWriter(io.BufferedWriter):
    r'''
    Compress stream using LZW algorithm as documented in TIFF6.pdf

    Pseudocode from p. 58 of TIFF6.pdf follows. Find a copy that has
    the Greek Omega character in it for the prefix variable; it's
    missing in most of the copies out there. I'm showing it as Omega
    below.

        InitializeStringTable();
        WriteCode(ClearCode);
        Omega = the empty string;
        for each character in the strip {
            K = GetNextCharacter();
            if Omega+K is in the string table {
                Omega = Omega+K; /* string concatenation */
            } else {
                WriteCode (CodeFromString(Omega);
                AddTableEntry(Omega+K);
                Omega = K;
            }
        } /* end of for loop */
        WriteCode (CodeFromString(Omega));
        WriteCode (EndOfInformation);

    >>> stream = io.BytesIO()
    >>> strip = b'\x07\x07\x07\x08\x08\x07\x07\x06\x06'
    >>> writer = LZWWriter(stream)
    >>> writer.write(strip)
    >>> writer.flush()
    >>> stream.getvalue()
    b'\x80\x01\xe0@\x80D\x08\x0c\x06\x80\x80'
    '''
    # pylint: disable=too-many-instance-attributes
    def __init__(self, stream,  # pylint: disable=too-many-arguments
                 buffer_size=BUFFER_SIZE, minbits=MINBITS,
                 maxbits=MAXBITS, special=True):
        super().__init__(stream, buffer_size)
        self.bitlength = self.minbits = minbits
        self.maxbits = maxbits
        self.codesink = CodeWriter(stream, buffer_size,
                                   minbits, maxbits, special)
        self.special = special  # False for rosettacode.org examples
        self.codedict = {}
        self.oldcode = None
        self.buffer = bytearray()
        self.prefix = b''
        self.offset = 2 * special  # reserve room for special codes
        self.initialize_table()

    def initialize_table(self):
        '''
        (Re-)Initialize code table
        '''
        self.codedict.clear()
        self.codedict.update(CODETABLE)
        self.codesink.bitlength = self.codesink.minbits

    def write(self, strip):
        '''
        Encode strip of image, and send codes downstream
        '''
        for byte in struct.unpack('{:d}c'.format(len(strip)), strip):
            chunk = self.prefix + byte
            if chunk in self.codedict:
                self.prefix = chunk
            else:
                self.codesink.write([self.codedict[self.prefix]])
                self.add_string(chunk)
                self.prefix = byte

    def flush(self):
        '''
        Write out remaining prefix and flush downstream
        '''
        if self.prefix:
            doctest_debug('flushing LZWWriter, prefix ending in %s',
                          self.prefix[-10:])
            self.codesink.write([self.codedict[self.prefix]])
            self.codesink.flush()
            self.prefix = b''
            doctest_debug('ending LZWWriter.flush()')
        else:
            doctest_debug('ignoring LZWWriter.flush() with no prefix')

    def add_string(self, bytestring):
        '''
        AddStringToTable from pseudocode

        Generate a new code number from bytestring and add it to the table
        '''
        newcode = len(self.codedict) + self.offset
        self.codedict[bytestring] = newcode

if os.path.splitext(os.path.basename(sys.argv[0]))[0] == 'doctest' or \
                    os.getenv('PYTHON_DEBUGGING'):
    # pylint: disable=function-redefined
    def doctest_debug(*args):
        '''
        use logging.debug only during doctest
        '''
        logging.debug(*args)

def dispatch(allowed, args, minargs, binary=True):
    '''
    simple dispatcher for scripts whose first arg is an action

    2nd and 3rd args are for input and output filenames,
    with '-' serving as stdin and stdout, respectively.

    `binary` indicates the files should be opened as byte streams

    we leave it to the dispatched routine to interpret None as
    sys.stdin, sys.stdout, sys.stdin.buffer, etc., as appropriate.
    '''
    # pylint: disable=consider-using-with
    argcount = len(args)
    args += [None] * (minargs - (argcount - 1))
    binary = 'b' if binary else ''
    if args[1] not in allowed + ('print',):  # allow `print` for testing
        logging.warning('usage: %s %s file.dat -', args[0], allowed[0])
        raise ValueError('Action %s must be in %s' % (args[1], list(allowed)))
    if args[2] and args[2] != '-':
        args[2] = open(args[2], 'r' + binary)
    else:
        args[2] = None
    if args[3] and args[3] != '-':
        args[3] = open(args[3], 'w' + binary)
    else:
        args[3] = None
    eval(args[1])(*args[2:argcount])  # pylint: disable=eval-used

def encode(args):
    '''
    Encode raw image data as LZW
    '''
    encoder = LZWWriter(args[1] or sys.stdout.buffer)
    source = args[0] or sys.stdin.buffer
    encoder.write(source.read())

def decode(args):
    '''
    Decode LZW-compressed data into raw image
    '''
    decoder = LZWReader(args[0] or sys.stdin.buffer)
    sink = args[1] or sys.stdout.buffer
    sink.write(decoder.read())

if os.path.splitext(os.path.basename(sys.argv[0]))[0] == 'doctest' or \
                    os.getenv('PYTHON_DEBUGGING'):
    # pylint: disable=function-redefined
    def doctest_debug(*args):
        '''
        use logging.debug only during doctest
        '''
        logging.debug(*args)
if __name__ == '__main__':
    dispatch(('encode', 'decode'), sys.argv, 3)
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
