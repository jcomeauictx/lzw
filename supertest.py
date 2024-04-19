#!/usr/bin/python3
'''
For figuring out how `super` works

see https://stackoverflow.com/a/78351285/493161
'''
class A:
    msg = 'hohoho'
class B(A):
    msg = 'hahaha'
class C(B):
    msg = 'hehehe'

if __name__ == '__main__':
    c = C()
    print(c.msg)
    print(super(C, c).msg)
    print(super(B, c).msg)
