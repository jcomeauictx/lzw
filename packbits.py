#!/usr/bin/python3 -OO
'''
packbits algorithm from page 42 of TIFF6.pdf spec. It seems to match what
the netpbm tools and imgtops use for compression instead of LZW, and Postscript
somehow handles it within its lzw code.
'''
import sys, logging  # pylint: disable=multiple-imports

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARN)

def unpack(instream=None, outstream=None):
    r'''
    UnPackBits routine from pseudocode

    The pseudocode uses signed 8-bit integer values, which is normal for
    old-school C programmers, but confusing after decades of higher-level
    coding. Bit 7 is the sign bit, so here's a small snippet of a Rosetta
    stone for the mapping:

    Signed decimal      Unsigned decimal    Binary
    1                   1                   00000001
    127                 127                 01111111
    -128                128                 10000000
    -127                129                 10000001
    -1                  255                 11111111

    Thus for "-n+1" in the following comments, we get the following
    -127 negated = 127, plus 1 is 128; 257 - 129 = 128
    -1 negated = 1, plus 1 is 2; 257 - 255 = 2

    So we implement (-signed+1) as (257-unsigned)
    '''
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    # "Loop until you get the number of unpacked bytes you are expecting"
    # we don't know this information, so we just read until EOF
    # "Read the next source byte into n."
    # pylint: disable=invalid-name  # using pseudocode naming, not snake_case
    while (nextbyte := instream.read(1)) != b'':
        n = ord(nextbyte)
        logging.debug('nexbyte is %s (%d)', nextbyte, n)
        # If n between 0 and 127 inclusive, copy the next n+1 bytes literally
        if n < 128:
            logging.debug('copying verbatim next %d bytes', n)
            outstream.write(instream.read(n))
        # Else if n is between -127 [128] and -1 [255] inclusive,
        # copy the next byte -n+1 [257-n] times.
        # Else if n is -128, noop [we ignore this case].
        elif n != 128:
            logging.debug('writing out following byte %d times', 257 - n)
            outstream.write(instream.read(1) * (257 - n))

def pack(instream=None, outstream=None, buffersize=4096):
    r'''
    PackBits routine. The above referenced page states:

    "In the inverse routine, it is best to encode a 2-byte repeat run
     as a replicate run except when preceded and followed by a literal run.
     In that case, it is best to merge the three runs into one literal run.
     Always encode 3-byte repeats as replicate runs."

    Or in other words:
    * threepeats and better always get replicated
    * twopeats sent literally only if surrounded by literal runs

    >>> from io import BytesIO
    >>> sample = BytesIO(b'111aaaaaaaabbbdccc5555555555s')
    >>> check = BytesIO(b'')
    >>> pack(sample, check)
    >>> check.getvalue()
    b'\xfe1\xf9a\xfeb\x00d\xfec\xf75\x00s'
    >>> check.seek(0)
    0
    >>> recheck = BytesIO(b'')
    >>> unpack(check, recheck)
    >>> recheck.getvalue()
    b'111aaaaaaaabbbdccc5555555555s'
    '''
    instream = instream or sys.stdin.buffer
    outstream = outstream or sys.stdout.buffer
    bytestring = b''
    chunks = [['literal', b'']]
    def ship(chunk, ship_literal=False):
        '''
        it's packed, now ship it over outstream.
        send twopeats ship_literal=True where appropriate.
        '''
        logging.debug('shipping chunk %s', chunk)
        if chunk[0] == 'literal':
            if len(chunk[1]):  # don't ship empty literals
                outstream.write(bytes([len(chunk[1]) - 1]))
                outstream.write(chunk[1])
        elif ship_literal:
            outstream.write(chunk[1] * chunk[0])
        else:
            outstream.write(bytes([257 - chunk[0]]))
            outstream.write(chunk[1])
    def purge(chunks, final=False):
        '''
        iterate over chunks and ship according to the rules above.
        '''
        logging.debug('purging chunks %s', chunks)
        if final:
            chunks.append(['literal', b''])
        ship(chunks[0])
        for index in range(1, len(chunks) - 1):
            chunk = chunks[index]
            if chunk[0] == 2:
                if chunks[index - 1][0] == chunks[index + 1][0] == 'literal':
                    ship(chunk, True)
                else:
                    ship(chunk)
            else:
                ship(chunk)
        chunks[0:-1] = []
    while bytestring or (nextblock := instream.read(buffersize)) != b'':
        bytestring += nextblock
        while bytestring:
            if len(bytestring) < 128:
                bytestring += instream.read(buffersize)
                purge(chunks)
            byte = bytestring[0:1]
            substring = bytestring.lstrip(byte)
            count = len(bytestring) - len(substring)
            if count == 1:
                if chunks[-1][0] == 'literal':
                    chunks[-1][1] += byte
                else:
                    chunks.append(['literal', byte])
            else:
                chunks.append([count, byte])
            bytestring = substring
        purge(chunks, True)

if __name__ == '__main__':
    # pylint: disable=consider-using-with
    sys.argv += [None, None]  # use stdin and stdout by default
    if sys.argv[1] and sys.argv[1] != '-':
        sys.argv[1] = open(sys.argv[1], 'rb')
    else:
        sys.argv[1] = None
    if sys.argv[2] and sys.argv[2] != '-':
        sys.argv[2] = open(sys.argv[2], 'wb')
    else:
        sys.argv[2] = None
    unpack(*sys.argv[1:3])
