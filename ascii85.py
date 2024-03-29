#!/usr/bin/python3
'''
command-line replacement for Ruby ascii85 program
'''
import sys
from base64 import a85encode, a85decode

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise RuntimeError('Must specify action and filename,'
                           'e.g. ascii85 -d myfile.a85')    
    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'rb') as infile:
            BYTESTRING = infile.read()
    else:
        BYTESTRING = sys.stdin.buffer.read()
    COMMAND = {'-d': a85decode, '-e': a85encode}.get(sys.argv[1])
    if COMMAND is not None:
        sys.stdout.buffer.write(COMMAND(BYTESTRING, adobe=True))
