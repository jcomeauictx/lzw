#!/usr/bin/python3
'''
Simple LZW decoder for PDF reverse engineering
'''
import sys, logging

CLEAR_CODE = 256
END_OF_INFO_CODE = 257
GLOBAL = {
    'bitlength': 9,
}

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARNING)

def nextcode(filename):
    '''
    get next code from lzw-compressed data

    requires Python 3.8 or better for 'walrus' (:=) operator
    '''
    instream = ''
    with open(filename, 'rb') as infile:
        while byte := infile.read(1):
            rawbyte = ord(byte)
            logging.debug('input byte %s: 0x%x', byte, rawbyte)
            instream += format(rawbyte, '08b')
            if len(instream) >= GLOBAL['bitlength']:
                code = instream[:GLOBAL['bitlength']]
                logging.debug('next code: %s', code)
                instream = instream[GLOBAL['bitlength']:]
                yield int(code, 2)

def newdict(specialcodes=True):
    '''
    build clean starting dict for LZW decompression

    `specialcodes` means that the CLEAR_CODE (256) and END_OF_INFO_CODE (257)
    from https://github.com/joeatwork/python-lzw are in use, which is the
    case in the data extracted from my Red Cross certification card PDF.
    '''
    codedict = {k: bytes([k]) for k in range(256)}
    if specialcodes:
        codedict[CLEAR_CODE] = None
        codedict[END_OF_INFO_CODE] = None
    #logging.debug('codedict: %s', codedict)
    return codedict

def decode(filename, specialcodes=True):
    codegen = nextcode(filename)
    codedict = newdict(specialcodes)
    decompressed = []
    with open(filename + '.dat', 'wb') as outfile:
        lastvalue = codevalue = None
        for code in codegen:
            try:
                codevalue = codedict[code]
            except KeyError:  # code wasn't in dict
                codevalue = lastvalue + lastvalue[0:1]
            if codevalue is not None:
                outfile.write(codevalue)
                #outfile.flush()  # in case of error down the line
                # now check if code is all ones except for LSB
                # and raise bitlength if so
                newkey = len(codedict)
                try:
                    codedict[newkey] = lastvalue + codevalue[0:1]
                    logging.debug('added 0x%x: ...%s to codedict', newkey,
                                  codedict[newkey][-50:])
                except TypeError:  # very first byte output has no lastvalue
                    logging.debug('not adding anything to dict after first'
                                  ' output byte %s', codevalue)
                    pass
                if (len(codedict) + 1).bit_length() > (newkey + 1).bit_length():
                    if GLOBAL['bitlength'] <= 11:  # no more than 12 bits
                        logging.debug(
                            'increasing bitlength to %d at dictsize %d',
                            GLOBAL['bitlength'] + 1, len(codedict))
                        GLOBAL['bitlength'] += 1
                lastvalue = codevalue
            else:  # CLEAR_CODE or END_OF_INFO_CODE
                logging.debug('special code found, resetting dictionary')
                codedict.clear()
                codedict.update(newdict(specialcodes))
                GLOBAL['bitlength'] = 9
                lastvalue = None
                if code == END_OF_INFO_CODE:
                    logging.debug('end of info code found, exiting')
                    return

if __name__ == '__main__':
    print(decode(sys.argv[1]))
