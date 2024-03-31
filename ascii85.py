#!/usr/bin/python3
'''
command-line replacement for Ruby ascii85 program
'''
import sys
import base64
import logging

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARN)

OUTPUT = sys.stdout.buffer

def a85encode(infile):
    '''
    use base64 library to encode ascii85
    '''
    return base64.a85encode(infile.read(), adobe=True)

def a85decode(infile):
    '''
    use base64 library to decode ascii85
    '''
    return base64.a85decode(adobe(infile.read()), adobe=True)

def adobe(bytestring):
    r'''
    make bytestring Adobe-compatible, starting with <~ and ending with ~>

    note that a PS or EPS file may have several runs, none starting with <~
    but all ending with ~>. we can't deal with these, you'll need to split
    them before feeding them into this routine.

    >>> adobe(b'JcC<$')
    b'<~JcC<$~>'
    >>> adobe(b'JcC<$~>\r\n')
    b'<~JcC<$~>'
    >>> adobe(b'<~JcC<$~>')
    b'<~JcC<$~>'
    '''
    bytestring = b'<~' + (bytestring.strip()
                          .lstrip(b'<~')
                          .rstrip(b'~>')
                         ) + b'~>'
    return bytestring

SELECTOR = {
 '-d': a85decode,
 '-e': a85encode,
}

def route(args):
    '''
    route command-line call to appropriate routine
    '''
    args += [None, None]  # avoid checking by making sure it has two elements
    command = SELECTOR.get(args[0])
    if command is None:
        raise RuntimeError('Must specify action and filename,'
                           'e.g. ascii85 -d myfile.a85')    
    filename = args[1]
    if filename is None:
        infile = sys.stdin.buffer
    else:
        infile = open(filename, 'rb')  # pylint: disable=consider-using-with
    return command(infile)

if __name__ == '__main__':
    OUTPUT.write(route(sys.argv[1:]))
