#!/usr/bin/python3 -OO
'''
Simple LZW decoder for PDF reverse engineering

LZW documentation in TIFF6.pdf says strips of 8k characters should be
ended with EndOfInformation code. But that isn't the case for any PDF
images I've found, which only have the code at the end of *all* the data.
if EOI_IS_EOD is set to a nonempty string, the decoder will terminate on
seeing it, and the encoder will not append it until the end of all the
data.

If EOI_IS_EOD is left False, the decoder will treat EndOfInformation as
a ClearCode, and the encoder will send it at the end of each strip.

On page 61: "Every LZW-compressed strip must begin on a byte boundary."
So, the bitstream should be cleared after sending, and after receiving,
EndOfInformation.
'''
import sys, os, struct, logging  # pylint: disable=multiple-imports

CLEAR_CODE = 256
END_OF_INFO_CODE = 257
MINBITS, MAXBITS = 9, 12
EOI_IS_EOD = os.getenv('EOI_IS_EOD')

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
                Code = GetNextCode();
                if (Code == EoiCode)
                    break;
                WriteString(StringFromCode(Code));
                OldCode = Code;
            } /* end of ClearCode case */
            else {
                if (IsInTable(Code)) {
                    WriteString(StringFromCode(Code));
                    AddStringToTable(StringFromCode(OldCode
                        )+FirstChar(StringFromCode(Code)));
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
    # pylint: disable=too-many-statements
    def nextcode(instream):
        '''
        get next code from lzw-compressed data

        requires Python 3.8 or better for 'walrus' (:=) operator
        '''
        bitstream = ''
        while byte := instream.read(1):
            rawbyte = ord(byte)
            doctest_debug('input byte %s: 0x%x', byte, rawbyte)
            bitstream += format(rawbyte, '08b')
            if len(bitstream) >= bitlength:
                bincode = bitstream[:bitlength]
                bitstream = bitstream[bitlength:]
                code = int(bincode, 2)
                doctest_debug('nextcode: 0x%x (%d) %s', code, code, bincode)
                if code == END_OF_INFO_CODE:
                    if bitstream.rstrip('0'):
                        logging.info('bitstream: %s', bitstream)
                        raise ValueError('nonzero bits remaining after EOI')
                    bitstream = ''
                yield code
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    codegenerator = codegenerator or nextcode(instream)
    codedict = newdict(specialcodes)
    minbits = bitlength = (minbits or MINBITS)
    maxbits = maxbits or MAXBITS
    lastvalue = codevalue = None
    for code in codegenerator:
        try:
            codevalue = codedict[code]
        except KeyError:  # code wasn't in dict
            # pylint: disable=unsubscriptable-object  # None or bytes
            try:
                codevalue = lastvalue + lastvalue[0:1]
            except (TypeError, IndexError) as failure:
                logging.error('This may be PackBits data, not LZW')
                raise ValueError('Invalid LZW data') from failure
        if codevalue is not None:
            doctest_debug('writing out %d bytes', len(codevalue))
            outstream.write(codevalue)
            # now check if code is all ones except for LSB
            # and raise bitlength if so
            newkey = len(codedict)
            try:
                codedict[newkey] = lastvalue + codevalue[0:1]
                doctest_debug('added 0x%x: ...%s to codedict', newkey,
                              codedict[newkey][-50:])
            except TypeError:  # first output after clearcode? no lastvalue
                doctest_debug('not adding anything to dict after first'
                              ' output byte %s', codevalue)
            if (len(codedict) + 1).bit_length() > (newkey + 1).bit_length():
                if bitlength < maxbits:
                    doctest_debug(
                        'increasing bitlength to %d at dictsize %d',
                        bitlength + 1, len(codedict))
                    bitlength += 1
            lastvalue = codevalue
        else:  # CLEAR_CODE or END_OF_INFO_CODE
            doctest_debug('special code found, resetting dictionary')
            codedict.clear()
            codedict.update(newdict(specialcodes))
            bitlength = minbits
            lastvalue = None
            if code == END_OF_INFO_CODE:
                if EOI_IS_EOD:
                    doctest_debug('end of info code found, exiting')
                    return None
                doctest_debug('ignoring EndOfInformation code')
    return None

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

        def write_code(number):
            '''
            pack number into bits with current bitlength and ship out bytes

            high-order bits go first
            '''
            nonlocal bitstream
            doctest_debug('write_code %s: bitstream="%s", bitlength=%s',
                          number, bitstream, bitlength)
            if number is not None:
                bitstream += '{0:0{1}b}'.format(number, bitlength)
            while len(bitstream) >= 8:
                doctest_debug('writing leftmost 8 bits of %s', bitstream)
                byte = int(bitstream[0:8], 2)
                outstream.write(bytes([byte]))
                bitstream = bitstream[8:]
            if number == END_OF_INFO_CODE:
                # at end of strip, pack up any straggler bits and ship
                bitstream = bitstream.ljust(8, '0')
                doctest_debug('writing final bits of stream %s', bitstream)
                outstream.write(bytes([int(bitstream, 2)]))

        def add_table_entry(entry):
            '''
            add a new bytes-to-integer-code mapping

            just before doubling table size, increment bitlength;
            i.e. after entering the 511th entry, raise it from 9 to 10;
            after entering the 1023d entry, raise it from 10 to 11;
            and after entering the 2047, raise it from 11 to 12.
            just before final entry (index 4094), write out 12-bit
            ClearCode, and reinit the table.

            NOTE that in the above paragraph, "table" size includes the
            two special codes, which are *not* actually present in the
            code_from_string dict.
            '''
            nonlocal bitlength
            doctest_debug('add_table_entry(%r)', entry)
            if not entry:
                return
            # table is built without entries for ClearCode and
            # EndOfInformation, so it starts at 256 elements exactly.
            # the first new entry's code then has to be 258,
            # which is len(table)+2.
            dict_length = len(code_from_string)
            newcode = dict_length + 2
            doctest_debug('code_from_string length %d, newcode: %d',
                          len(code_from_string), newcode)
            code_from_string[entry] = newcode
            if newcode + 1 == 2 ** bitlength and bitlength < maxbits:
                logging.debug('raising bitlength to %d at table size %d',
                              bitlength + 1, dict_length)
                bitlength += 1
            elif newcode == 2 ** maxbits - 2:
                logging.debug('clearing table at size %d', dict_length)
                write_code(CLEAR_CODE)
                code_from_string.clear()
                code_from_string.update(initialize_string_table())
                bitlength = minbits

        doctest_debug('beginning packstrip(%s)', strip)
        # InitializeStringTable();
        code_from_string = initialize_string_table()
        # WriteCode(ClearCode);
        bitstream = ''
        write_code(CLEAR_CODE)
        # Omega (I'm using `prefix`] = the empty string;
        prefix = b''
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
        doctest_debug('finishing strip, prefix=%s', prefix)
        write_code(code_from_string.get(prefix, None))
        write_code(END_OF_INFO_CODE)
        doctest_debug('ending packstrip()')
    logging.debug('beginning lzw.encode()')
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    minbits = bitlength = (minbits or MINBITS)
    maxbits = maxbits or MAXBITS
    while (strip := instream.read(stripsize)) != b'':
        packstrip(strip)
    logging.debug('ending lzw.encode()')

def dispatch(allowed, args, minargs, binary=True):
    '''
    simple dispatcher for scripts whose first arg is an action

    2nd and 3rd args are, respectively, input and output files,
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

# pylint: disable=function-redefined
if __name__ == '__main__':
    if os.getenv('PYTHON_DEBUGGING'):
        def doctest_debug(*args):
            '''
            use logging.debug only during doctest
            '''
            logging.debug(*args)
    dispatch(('encode', 'decode'), sys.argv, 3)
elif os.path.splitext(os.path.basename(sys.argv[0]))[0] == 'doctest':
    def doctest_debug(*args):
        '''
        use logging.debug only during doctest
        '''
        logging.debug(*args)
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
