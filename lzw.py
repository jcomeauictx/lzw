#!/usr/bin/python3 -OO
'''
Simple LZW decoder for PDF reverse engineering
'''
import sys, logging  # pylint: disable=multiple-imports

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

def decode(filename, outfilename=None, # pylint: disable=too-many-arguments
           specialcodes=True, minbits=9, maxbits=12, codegenerator=None):
    '''
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
    >>> codes = [84,79,66,69,79,82,78,79,84,256,258,260,265,259,261,263,
    ...     84,111,32,98,101,32,111,114,32,110,111,116,32,116,257,259,
    ...     268,104,97,267,105,115,272,260,113,117,101,115,116,105,111,
    ...     110,33,34,84,104,101,114,101,32,105,115,32,110,111,116,104,
    ...     105,110,103,32,112,259,109,97,110,101,110,116,32,101,120,
    ...     99,101,112,281,99,104,277,103,101,46,34,32,296,45,298,296,
    ...     32,72,259,97,99,108,105,116,117,264,32,91,53,52,48,32,299,
    ...     52,55,53,32,66,67,69,93]
    >>> decode('/tmp/', None, False, 9, 9, iter(codes))
    >>> check = open('/tmp/.raw', 'rb').read()
    >>> check.startswith(b'TOBEORNOTTOBEORTOBEORNOT')
    True
    >>> check.index(b'To be or not to be that is the question!')
    28
    >>> check.index(b'"There is nothing permanent except change."')
    75
    >>> check.index(b'---   Heraclitus  [540 -- 475 BCE]')
    122

    '''
    codegenerator = codegenerator or nextcode(filename)
    codedict = newdict(specialcodes)
    outfilename = outfilename or filename + '.raw'
    minbits = minbits or 9
    maxbits = maxbits or sys.maxsize
    with open(outfilename, 'wb') as outfile:
        lastvalue = codevalue = None
        for code in codegenerator:
            logging.debug('found code 0x%x (%d)', code, code)
            try:
                codevalue = codedict[code]
            except KeyError:  # code wasn't in dict
                # pylint: disable=unsubscriptable-object  # None or bytes
                codevalue = lastvalue + lastvalue[0:1]
            if codevalue is not None:
                logging.debug('writing out %s', codevalue)
                outfile.write(codevalue)
                #outfile.flush()  # in case of error down the line
                # now check if code is all ones except for LSB
                # and raise bitlength if so
                newkey = len(codedict)
                try:
                    codedict[newkey] = lastvalue + codevalue[0:1]
                    logging.debug('added 0x%x: ...%s to codedict', newkey,
                                  codedict[newkey][-50:])
                except TypeError:  # first output after clearcode? no lastvalue
                    logging.debug('not adding anything to dict after first'
                                  ' output byte %s', codevalue)
                if (len(codedict) + 1).bit_length() > (newkey + 1).bit_length():
                    if GLOBAL['bitlength'] < maxbits:
                        logging.debug(
                            'increasing bitlength to %d at dictsize %d',
                            GLOBAL['bitlength'] + 1, len(codedict))
                        GLOBAL['bitlength'] += 1
                lastvalue = codevalue
            else:  # CLEAR_CODE or END_OF_INFO_CODE
                logging.debug('special code found, resetting dictionary')
                codedict.clear()
                codedict.update(newdict(specialcodes))
                GLOBAL['bitlength'] = minbits
                lastvalue = None
                if code == END_OF_INFO_CODE:
                    logging.debug('end of info code found, exiting')
                    return

if __name__ == '__main__':
    print(decode(*sys.argv[1:]))
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
