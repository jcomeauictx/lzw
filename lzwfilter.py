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
                self.bitstream.extend(
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

if __name__ == '__main__':
    import doctest
    doctest.testmod()
