#!/usr/bin/python3 -OO
'''
packbits algorithm from page 42 of TIFF6.pdf spec. It seems to match what
the netpbm tools and imgtops use for compression instead of LZW, and Postscript
somehow handles it within its lzw code.
'''
import sys, logging  # pylint: disable=multiple-imports

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARN)

def unpack(instream=None, outstream=None):
    '''
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
        # Else if n is between -127 and -1 inclusive,
        # copy the next byte -n+1 times.
        # Else if n is -128, noop [we ignore this case].
        elif n != 128:
            logging.debug('writing out following byte %d times', 257 - n)
            outstream.write(instream.read(1) * (257 - n))

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
