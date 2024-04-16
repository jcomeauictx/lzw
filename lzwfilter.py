#!/usr/bin/python3
'''
Lempel-Ziv-Welch compression and decompression

A different approach, hopefully cleaner and faster than lzw.py
'''
import sys, os, io, logging  # pylint: disable=import-multiple

class CodeReader(io.BufferedReader):
    '''
    Create an iterator for the variable-bitlength codes in a LZW file
    '''
