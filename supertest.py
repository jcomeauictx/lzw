class A:
    msg = 'hohoho'
class B(A):
    msg = 'hahaha'
class C(B):
    msg = 'hehehe'
c = C()
print(c.msg)
print(super(C, c).msg)
print(super(B, c).msg)
