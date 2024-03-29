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
    return base64.a85encode(infile.read(), adobe=True)

def a85decode(infile):
    return base64.a85decode(adobe(infile.read()), adobe=True)

def adobe(bytestring):
    bytestring = bytestring.strip()
    if not bytestring.startswith(b'<~'):
        bytestring = '<~' + bytestring
    if not bytestring.endswith(b'~>'):
        bytestring += 'b~>'
    return bytestring

SELECTOR = {
 '-d': a85decode,
 '-e': a85encode,
}

def route(args):
    args += [None, None]  # avoid checking by making sure it has two elements
    command = SELECTOR.get(args[0])
    if command == None:
        raise RuntimeError('Must specify action and filename,'
                           'e.g. ascii85 -d myfile.a85')    
    filename = args[1]
    if filename is None:
        infile = sys.stdin.buffer
    else:
        infile = open(filename, 'rb')
    return command(infile)
    
if __name__ == '__main__':
    OUTPUT.write(route(sys.argv[1:]))
