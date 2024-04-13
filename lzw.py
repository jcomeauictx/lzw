#!/usr/bin/python3 -OO
'''
Simple LZW encoder and decoder for PDF reverse engineering

LZW documentation in TIFF6.pdf says strips of 8k characters should be
ended with EndOfInformation code. But that isn't the case for any PDF
images I've found, which only have the code at the end of *all* the data.
if EOI_IS_EOD is set to a nonempty string, the decoder will terminate on
seeing it, and the encoder will not append it until the end of all the
data.

If EOI_IS_EOD is left False, the decoder will treat EndOfInformation as
a ClearCode, and the encoder will send it at the end of each strip. This
results in much larger LZW-compressed images, over 10 times larger in
the card.lzw test case.

On page 61: "Every LZW-compressed strip must begin on a byte boundary."
So, the bitstream should be cleared after sending, and after receiving,
EndOfInformation.
'''
import sys, os, struct, logging  # pylint: disable=multiple-imports

CLEAR_CODE = 256
END_OF_INFO_CODE = 257
MINBITS, MAXBITS = 9, 12
EOI_IS_EOD = os.getenv('EOI_IS_EOD')
CODE_SIZE = 256  # original dict size, used for deciding when to increase bits

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARNING)
# pylint: disable=consider-using-f-string  # leave this for later

def doctest_debug(*args):  # pylint: disable=unused-argument
    '''
    redefined below if running doctest module
    '''
    return

def newdict(specialcodes=True):
    '''
    build clean starting dict for LZW compression or decompression

    `specialcodes` means that the CLEAR_CODE (256) and END_OF_INFO_CODE (257)
    from https://github.com/joeatwork/python-lzw are in use, which is the
    case in the data extracted from my Red Cross certification card PDF.
    '''
    codedict = {k: bytes([k]) for k in range(256)}
    if specialcodes:
        codedict[CLEAR_CODE] = None
        codedict[END_OF_INFO_CODE] = None
    #doctest_debug('codedict: %s', codedict)
    return codedict

def decode(instream=None, outstream=None, # pylint: disable=too-many-arguments
           specialcodes=True, minbits=9, maxbits=12, codegenerator=None):
    '''
    Decode LZW-encoded data

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

    Test case from https://rosettacode.org/wiki/LZW_compression
    >>> from io import BytesIO
    >>> outstream = BytesIO()
    >>> codes = [84,79,66,69,79,82,78,79,84,256,258,260,265,259,261,263]
    >>> decode(None, outstream, False, 9, 9, iter(codes))
    >>> outstream.getvalue()
    b'TOBEORNOTTOBEORTOBEORNOT'
    >>> outstream = BytesIO()
    >>> codes = [84,111,32,98,101,32,111,114,32,110,111,116,32,116,257,259,
    ...     268,104,97,267,105,115,272,260,113,117,101,115,116,105,111,110,33]
    >>> decode(None, outstream, False, 9, 9, iter(codes))
    >>> outstream.getvalue()
    b'To be or not to be that is the question!'
    >>> outstream = BytesIO()
    >>> codes = [34,84,104,101,114,101,32,105,115,32,110,111,116,104,
    ...     105,110,103,32,112,259,109,97,110,101,110,116,32,101,120,
    ...     99,101,112,281,99,104,277,103,101,46,34,32,296,45,298,296,
    ...     32,72,259,97,99,108,105,116,117,264,32,91,53,52,48,32,299,
    ...     52,55,53,32,66,67,69,93]
    >>> decode(None, outstream, False, 9, 9, iter(codes))
    >>> check = outstream.getvalue()
    >>> check.startswith(b'"There is nothing permanent except change."')
    True
    >>> check.index(b'---   Heraclitus  [540 -- 475 BCE]')
    46
    '''
    # pylint: disable=too-many-statements, too-many-locals, too-many-branches
    def nextcode(instream):
        '''
        get next code from lzw-compressed data

        requires Python 3.8 or better for 'walrus' (:=) operator
        '''
        nonlocal bitstream
        logging.debug('nextcode(): bitstream=%r', bitstream)
        while not end_of_data and (byte := instream.read(1)):
            rawbyte = ord(byte)
            doctest_debug("input byte b'\\x%02x'", rawbyte)
            bitstream += format(rawbyte, '08b')
            if len(bitstream) >= bitlength:
                bincode = bitstream[:bitlength]
                bitstream = bitstream[bitlength:]
                code = int(bincode, 2)
                doctest_debug('nextcode: 0x%x (%d) %s', code, code, bincode)
                if code == END_OF_INFO_CODE:
                    if bitstream.strip('0'):
                        logging.info('bitstream: %s', bitstream)
                        raise ValueError('nonzero bits remaining after EOI')
                    bitstream = ''
                yield code
    def insert(bytestring):
        '''
        AddStringToTable() from pseudocode.

        This comment from p.61 of TIFF6.pdf actually should apply to this
        subroutine, since GetNextCode() (`nextcode` here) doesn't modify the
        table and doesn't even need to know about it:

        "The function GetNextCode() retrieves the next code from the
         LZW-coded data. It must keep track of bit boundaries. It knows
         that the first code that it gets will be a 9-bit code. We add
         a table entry each time we get a code. So, GetNextCode() must
         switch over to 10-bit codes as soon as string #510 is stored
         into the table. Similarly, the switch is made to 11-bit codes
         after #1022 and to 12-bit codes after #2046.

        One thing the pseudocode doesn't mention is that an unknown code
        shouldn't be more than 1 plus the highest known code, or it is
        an error in the codestream. We will trap this below.
        '''
        nonlocal bitlength
        newkey = len(codedict)
        codedict[newkey] = bytestring
        doctest_debug('added 0x%x (%d): %d bytes ...%s to dict',
                      newkey, newkey, len(codedict[newkey]),
                      codedict[newkey][-16:])
        if (newkey + 2).bit_length() == (newkey + 1).bit_length() + 1:
            if bitlength < maxbits:
                doctest_debug(
                    'increasing bitlength to %d at code %d',
                    bitlength + 1, newkey)
                bitlength += 1
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    bitstream = ''
    codegenerator = codegenerator or nextcode(instream)
    codedict = newdict(specialcodes)
    minbits = bitlength = (minbits or MINBITS)
    maxbits = maxbits or MAXBITS
    lastvalue = codevalue = None
    end_of_data = False
    # while ((Code = GetNextCode()) != EoiCode) {
    # (we don't actually pay attention to EoiCode unless EOI_IS_EOD is set,
    #  because the TIFF6 spec indicates it should be used at the end of
    #  every 8192-byte strip, which is unnecessary and wasteful, as the
    #  resulting compressed file can be over 10 times larger than it
    #  otherwise has to be. We do, however, have to honor the mandatory
    #  byte boundary after seeing it, clearing `bitstream`.)
    for code in codegenerator:
        #       if (IsInTable(Code)) {
        #           OutString = StringFromCode(Code);
        #           try {
        #               StoreString = StringFromCode(OldCode) +
        #                   FirstChar(StringFromCode(Code);
        #           } except(NoOldCodeImmediatelyAfterClearCode) {
        #               StoreString = null;
        #           }
        #       } else {
        #           OutString = StringFromCode(OldCode) +
        #               FirstChar(StringFromCode(OldCode);
        #           StoreString = OutString;
        #       }
        #       WriteString(OutString);
        #       if (StoreString != null) AddStringToTable(StoreString);
        #       OldCode = Code;
        if code in codedict:  # if (IsInTable(Code))
            codevalue = codedict[code]
            # (remember that CLEAR_CODE and END_OF_INFO_CODE are both
            #  also in dict and will return None; this will catch that too.)
            try:
                storevalue = lastvalue + codevalue[0:1]
            except TypeError:  # attempting to add bytes to None
                storevalue = None
        else:  # code wasn't in dict
            if code - 1 in codedict:
                try:
                    # pylint: disable=unsubscriptable-object  # None or bytes
                    codevalue = lastvalue + lastvalue[0:1]
                except (TypeError, IndexError):
                    codevalue = None
                storevalue = codevalue
            else:
                codevalue = None
            if codevalue is None:
                logging.error('This may be PackBits data, not LZW')
                raise ValueError('Invalid LZW data at code 0x%02x' % code)
        if codevalue is not None:
            doctest_debug('writing out %d bytes', len(codevalue))
            outstream.write(codevalue)  # WriteString(OutString);
            if storevalue is not None:  # if (StoreString != null)
                insert(storevalue)  # AddStringToTable(StoreString);
            lastvalue = codevalue  # OldCode = Code
        elif code == END_OF_INFO_CODE:
            if EOI_IS_EOD:
                doctest_debug('EndOfInformation code found, exiting')
                end_of_data = True
            # else decode() will run until `for` loop is done
            else:
                doctest_debug('EndOfInformation code, only resetting bitlength')
                bitlength = minbits
        else:  # CLEAR_CODE
            doctest_debug('processing ClearCode')
            codedict.clear()
            codedict.update(newdict(specialcodes))
            bitlength = minbits
            lastvalue = None
        try:
            doctest_debug('decode(): bytes read: %d, written: %d',
                          instream.tell(), outstream.tell())
        except OSError:  # ignore Illegal Seek during doctests with BytesIO
            pass

def encode(instream=None, outstream=None, # pylint: disable=too-many-arguments
           minbits=9, maxbits=12, stripsize=8192):
    r'''
    Encode data using Lempel-Ziv-Welch compression

    From page 58 of TIFF6.pdf:

    Each strip is compressed independently. We strongly recommend that
    RowsPerStrip be chosen such that each strip contains about 8K bytes
    before compression. We want to keep the strips small enough so that
    the compressed and uncompressed versions of the strip can be kept
    entirely in memory, even on small machines, but are large enough to
    maintain nearly optimal compression ratios.

        >>> from io import BytesIO
        >>> instream = BytesIO(b'\x07\x07\x07\x08\x08\x07\x07\x06\x06')
        >>> outstream = BytesIO()
        >>> encode(instream, outstream)
        >>> outstream.getvalue()
        b'\x80\x01\xe0@\x80D\x08\x0c\x06\x80\x80'
        >>> instream = BytesIO(outstream.getvalue())
        >>> outstream = BytesIO()
        >>> decode(instream, outstream)
        >>> outstream.getvalue()
        b'\x07\x07\x07\x08\x08\x07\x07\x06\x06'
    '''
    # pylint: disable=too-many-statements
    def packstrip(strip=b''):
        r'''
        Encode data using Lempel-Ziv-Welch compression

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
        '''
        def initialize_string_table():
            '''
            opposite of the one used for decode: strings map to code numbers
            '''
            return dict(map(reversed, newdict(False).items()))

        def clear_string_table():
            '''
            send clear code and reinitialize
            '''
            nonlocal bitlength
            code_from_string.clear()
            code_from_string.update(initialize_string_table())
            bitlength = minbits
            write_code(CLEAR_CODE)

        def write_code(number):
            '''
            pack number into bits with current bitlength and ship out bytes

            high-order bits go first
            '''
            nonlocal bitstream, bitlength, writecount
            doctest_debug('write_code %s: bitstream="%s", bitlength=%s',
                          number, bitstream, bitlength)
            if number is not None:
                bitstream += '{0:0{1}b}'.format(number, bitlength)
            else:
                doctest_debug('write_code(None) with bitstream=%s, prefix=%s',
                              bitstream, prefix)
            while len(bitstream) >= 8:
                byte = bytes([int(bitstream[0:8], 2)])
                doctest_debug('writing leftmost 8 bits of %s (0x%02x)',
                              bitstream, ord(byte))
                outstream.write(byte)
                bitstream = bitstream[8:]
            if number == CLEAR_CODE:
                if writecount > CODE_SIZE:  # original dict size
                    logging.debug('%d codes written since last ClearCode',
                                  writecount)
                writecount = CODE_SIZE
            else:
                writecount += 1
            if number == END_OF_INFO_CODE and bitstream:
                # at end of strip, pack up any straggler bits and ship
                bitstream = bitstream.ljust(8, '0')
                doctest_debug('writing final bits of stream %s', bitstream)
                outstream.write(bytes([int(bitstream, 2)]))
                bitstream = ''
            #doctest_debug('writecount: %d', writecount)
            elif (writecount + 2) == (2 ** bitlength):
                if bitlength < maxbits:
                    logging.debug('increasing bitlength to %d at code %d',
                                  bitlength + 1, writecount)
                    bitlength += 1
                else:
                    logging.debug('clearing table at code %d', writecount)
                    clear_string_table()

        def add_table_entry(entry):
            '''
            add a new bytes-to-integer-code mapping

            just before doubling table size, increment bitlength;
            i.e. after entering table entry 511, raise it from 9 to 10;
            after entering table entry 1023, raise it from 10 to 11;
            and after table entry 2047, raise it from 11 to 12.
            as soon as we use entry 4094, we write out a 12-bit
            ClearCode, and reinit the table.

            NOTE that in the above paragraph, "table" size includes the
            two special codes, which are *not* actually present in the
            code_from_string dict.

            NOTE also that entry 511 could mean the 512th entry with code
            511, or the 511th entry with code 510. Need to find out what
            works.

            Final NOTE: the following text in italics on P. 60 of TIFF6.pdf
            turns out to be the determinant:

            "Whenever you add a code to the output stream, it “counts”
             toward the decision about bumping the code bit length. This
             is important when writing the last code word before an EOI
             code or ClearCode, to avoid code length errors."

            So the above part about the number of table entries was a
            lie, or at minimum an oversimplification. The decoder is going
            to raise bitlength when it sees (2 ** bitlength - 2) codes.
            So, when the encoder sends the 254th code right before EOI,
            it has to send EOI as a 10-bit code even though that last
            `WriteCode(CodeFromString(Omega))`, outside the loop, didn't
            add a table entry.

            Accordingly, we move the bitlength-incrementing code to
            the `write_code` subroutine.
            '''
            doctest_debug('add_table_entry(...%r) (length %d)',
                          entry[-16:], len(entry))
            if not entry:
                return
            # table is built without entries for ClearCode and
            # EndOfInformation, so it starts at 256 elements exactly.
            # the first new entry's code then has to be 258,
            # which is len(table)+2.
            newcode = len(code_from_string) + 2
            code_from_string[entry] = newcode
            doctest_debug('added 0x%x (%d), key %d bytes ...%s to dict',
                          newcode, newcode, len(entry), entry[-16:])

        nonlocal prefix, code_from_string
        doctest_debug('beginning packstrip(...%s), length %d, prefix length %d',
                      strip[-16:], len(strip), len(prefix))
        if strip == b'':
            if EOI_IS_EOD:  # if not, EOI was written at end of previous strip
                write_code(code_from_string.get(prefix, None))
                doctest_debug('writing END_OF_INFO code at end of file')
                write_code(END_OF_INFO_CODE)
            doctest_debug('ending packstrip on empty strip')
            return
        if len(code_from_string) == 0 or not EOI_IS_EOD:
            # (TIFF6 spec says each strip should reinit table and
            # send ClearCode, but many PDF images don't show this
            # in use. So we only do it on first call, and after
            # table fills up.)
            # InitializeStringTable();
            # WriteCode(ClearCode);
            clear_string_table()
            # Omega (I'm using `prefix`] = the empty string;
            # NOTE: the caller (encode) sets this. Prefix must be
            # carried over from one strip to the next.
            # So, leave this commented out.
            #prefix = b''
        # for each character in the strip {
        #     K = GetNextCharacter();
        # https://stackoverflow.com/a/57543519/493161
        for byte in struct.unpack('{:d}c'.format(len(strip)), strip):
            #doctest_debug('processing byte: %s', byte)
        #     if Omega+K is in the string table {
        #         Omega = Omega+K; /* string concatenation */
            if prefix + byte in code_from_string:
                prefix += byte
        #     } else {
        #         WriteCode (CodeFromString(Omega));
        #         AddTableEntry(Omega+K);
        #         Omega = K;
            else:
                write_code(code_from_string.get(prefix, None))
                # must add 2 to all codes to account for Clear and EOI codes
                add_table_entry(prefix + byte)
                prefix = byte
        # WriteCode (CodeFromString(Omega));
        # WriteCode (EndOfInformation);
        doctest_debug('finishing strip, prefix=...%s, length %d',
                      prefix[-16:], len(prefix))
        if not EOI_IS_EOD:
            doctest_debug('writing final prefix before EOI code')
            write_code(code_from_string.get(prefix, None))
            prefix = b''  # reset prefix
            doctest_debug('writing END_OF_INFO code at end of strip')
            write_code(END_OF_INFO_CODE)
            code_from_string.clear()  # to force reset on next packstrip()
        doctest_debug('ending packstrip(...%s), length %d',
                      strip[-16:], len(strip))
        return
    logging.debug('beginning lzw.encode()')
    logging.debug('EOI_IS_EOD: %s', EOI_IS_EOD)
    writecount = CODE_SIZE
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    minbits = bitlength = (minbits or MINBITS)
    maxbits = maxbits or MAXBITS
    bitstream, prefix = '', b''
    code_from_string = {}
    while (strip := instream.read(stripsize)) != b'':
        packstrip(strip)
        try:
            doctest_debug('encode(): bytes read: %d, written: %d',
                          instream.tell(), outstream.tell())
        except OSError:  # ignore Illegal Seek during doctests with BytesIO
            pass
    if EOI_IS_EOD:
        packstrip(b'')
    logging.debug('ending lzw.encode()')

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
