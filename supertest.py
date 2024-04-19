#!/usr/bin/python3
'''
For figuring out how `super` works

see https://stackoverflow.com/a/78351285/493161
'''
import logging

logging.basicConfig(level=logging.DEBUG if __debug__ else logging.WARNING)

class A:
    msg = 'hohoho'
    def __init__(self, message=msg):
        self.message = message
class B(A):
    msg = 'hahaha'
class C(B):
    msg = 'hehehe'

if __name__ == '__main__':
    c = C()
    logging.debug('c: %s: %s', c, vars(c))
    b = super(C, c)
    logging.debug('b: %s: %s', b, vars(b))
    a = super(B, c)
    logging.debug('a: %s: %s', a, vars(a))
    logging.debug('C class msg: %s, message: %s', c.msg, c.message)
    logging.debug('C parent class msg: %s, message: %s', b.msg, b.message)
    logging.debug('C grandparent class msg: %s, message: %s', a.msg, a.message)
    print(c.message)
    print(super(C, c).message)
    print(super(B, c).msg)
