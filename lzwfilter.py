#!/usr/bin/python3 -OO
'''
Lempel-Ziv-Welch compression and decompression

A different approach, hopefully cleaner and faster than lzw.py
'''
import io, math, logging  # pylint: disable=multiple-imports

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARNING)

BUFFER_SIZE = 8192  # see "8K" on p. 56 of TIFF6.pdf
# min and max bit lengths recommended on p. 60 of TIFF6.pdf
MINBITS = 9
MAXBITS = 12
# encoding and decoding tables, make shallow copies of these for use
STRINGTABLE = {n: bytes([n]) for n in range(256)}  # codes to strings
CODETABLE = dict(map(reversed, STRINGTABLE.items()))  # strings to codes
CLEAR_CODE = 256  # see TIFF6.pdf pp. 58-63 for use of special codes
END_OF_INFO_CODE = 257
SPECIAL = {CLEAR_CODE: None, END_OF_INFO_CODE: None}

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
        self.minbytes = int(math.ceil(maxbits / 8))

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
            nextbytes = super().read(self.minbytes)
            if not nextbytes:  # empty string or None: EndOfFile
                if not self.bitstream:
                    raise StopIteration
                self.bitstream.extend(  # pad remaining bits with zeroes
                    b'0' * (self.bitlength - len(self.bitstream)))
            else:
                for byte in nextbytes:
                    self.bitstream.extend(format(byte, '08b').encode())
        return int(bytes(self.bitstream.pop(0)
                         for index in range(self.bitlength)), 2)

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

class LZWReader(CodeReader):
    '''
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
    >>> decode = lambda codes: LZWReader(BytesIO(codes)).read()
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
    >>> check.startswith(b'"There is nothing permanent except change."')
    True
    >>> check.index(b'---   Heraclitus  [540 -- 475 BCE]')
    46
    '''
    def __init__(self, stream, buffer_size=BUFFER_SIZE,
                 minbits=MINBITS, maxbits=MAXBITS):
        super().__init__(stream, buffer_size, minbits, maxbits)
        self.codedict = dict(SPECIAL).update(STRINGTABLE)
        self.oldcode = None
        self.buffer = bytearray()

    def __next__(self):
        '''
        returns next string from table, adjusting bitlength as we go
        '''
        # while ((Code = GetNextCode()) != EoiCode) {
        code = next(super())
        if code == END_OF_INFO_CODE:
            raise StopIteration
        #    if (Code == ClearCode) {
        #        InitializeTable();
        if code == CLEAR_CODE:
            self.codedict = dict(SPECIAL).update(STRINGTABLE)
        #    else {
        #        if (IsInTable(Code)) {
        #            OutString = StringFromCode(Code);
        if code in self.codedict:
            outstring = self.codedict[code]
        #            try {
        #                StoreString = StringFromCode(OldCode) +
        #                    FirstChar(StringFromCode(Code);
        #            } except(NoOldCodeImmediatelyAfterClearCode) {
        #                StoreString = null;
        #            }
            try:
                storestring = self.codedict[self.oldcode] + outstring[0:1]
            except KeyError:
                storestring = None
        #        } else {
        #            OutString = StringFromCode(OldCode) +
        #                FirstChar(StringFromCode(OldCode);
        #            StoreString = OutString;
        #        }
        else:
            outstring = self.codedict[oldcode]
            outstring += outstring[0:1]
            storestring = outstring
        #        WriteString(OutString);
        #        if (StoreString != null) AddStringToTable(StoreString);
        #        OldCode = Code;
        #    }
        # }
        self.add_string_to_table(storestring)
        self.oldcode = code
        return outstring

    def read(self, count=None):
        '''
        Return `count` bytes, defaulting to all available
        '''
        count = count or sys.maxsize
        offset = 0
        while len(self.buffer) < count:
            try:
                self.buffer.extend(next(self))
            except StopIteration:
                break
        result = bytes(self.buffer[:count])
        self.buffer[:count] = []
        return result

    def add_string_to_table(string):
        newkey = len(self.codetable)
        self.codetable[key] = string
                
if __name__ == '__main__':
    import doctest
    doctest.testmod()
