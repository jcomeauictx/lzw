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
    # (this information isn't available so we just read the whole thing)
    # "Read the next source byte into n."
    # pylint: disable=invalid-name  # using pseudocode naming, not snake_case
    while (nextbyte := instream.read(1)) != b'':
        n = ord(nextbyte)
        logging.debug('nextbyte is %s (%d)', nextbyte, n)
        # If n between 0 and 127 inclusive, copy the next n+1 bytes literally
        if n < 128:
            logging.debug('copying verbatim next %d bytes', n + 1)
            outstream.write(instream.read(n + 1))
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

    In practice, the above "twopeat" strategy seems a little daunting with
    the forward lookups. For now, my plan is to just append the two bytes
    to the previous literal string if there is one.

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
    chunks = [[1, b'']]  # 1 here doesn't mean count, it means 'literal'
    def ship(chunk, level=1):
        '''
        it's packed, now ship it over outstream.
        '''
        logging.debug('shipping chunk %s', chunk)
        if chunk[0] == 1:
            if len(chunk[1]):  # don't ship empty literals
                outstream.write(bytes([len(chunk[1]) - 1]))
                outstream.write(chunk[1])
        elif chunk[0] != 0:
            while chunk[0] > 128:
                ship([128, chunk[1]], level + 1)
                chunk[0] -= 128
            try:
                outstream.write(bytes([257 - chunk[0]]))
                outstream.write(chunk[1])
            except ValueError:
                logging.debug('chunk %s count value out of bounds', chunk)
                if chunk[0] == 1:
                    ship([1, chunk[1]], level + 1)
                else:
                    logging.warning('skipping empty chunk %s', chunk)
        else:  # chunk[0] == 0 to mark EOD
            outstream.write(chunk[1])
    def purge(chunks, final=False):
        '''
        iterate over chunks and ship according to the rules above.
        '''
        logging.debug('purging chunks %s', chunks)
        if final:
            # append noop as EOD marker (PLRM3 page 142)
            chunks.append([0, b'\x80'])
            # append empty chunk so following loop sends all real chunks
            chunks.append([1, b''])
        for chunk in chunks[:-1]:
            ship(chunk)
        chunks[0:-1] = []  # purge the shipped chunks from list
    while bytestring or (nextblock := instream.read(buffersize)) != b'':
        bytestring += nextblock
        while bytestring:
            if len(bytestring) < 128:
                bytestring += instream.read(buffersize)
                purge(chunks)
            byte = bytestring[0:1]
            substring = bytestring.lstrip(byte)
            count = len(bytestring) - len(substring)
            if count < 3:
                if chunks[-1][0] == 1 and \
                        len(chunks[-1][1]) < (129 - count):
                    chunks[-1][1] += (byte * count)
                else:
                    chunks.append([count, byte])
            elif chunks[-1][0] != 1 and chunks[-1][1] == byte:
                chunks[-1][0] += count
            else:
                chunks.append([count, byte])
            bytestring = substring
    purge(chunks, True)

if __name__ == '__main__':
    # pylint: disable=consider-using-with
    sys.argv += [None]  # in case action not specified
    sys.argv += [None, None]  # use stdin and stdout by default
    if sys.argv[1] not in ('pack', 'unpack'):
        logging.warning('usage: %s unpack test.rle -', sys.argv[0])
        raise ValueError('Must specify either "pack" or "unpack"')
    if sys.argv[2] and sys.argv[2] != '-':
        sys.argv[2] = open(sys.argv[2], 'rb')
    else:
        sys.argv[2] = None
    if sys.argv[3] and sys.argv[3] != '-':
        sys.argv[3] = open(sys.argv[3], 'wb')
    else:
        sys.argv[3] = None
    eval(sys.argv[1])(*sys.argv[2:4])  # pylint: disable=eval-used
