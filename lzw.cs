#!/usr/src/jcomeauictx/casperscript/bin/bccs
/infile sys.argc 1 gt {sys.argv 1 get} {(/dev/stdin)} ifelse def
/outfile sys.argc 2 gt {sys.argv 2 get} {(/dev/stdout)} ifelse def
infile (r) file
dup bytesavailable [0] astore
128 string (bytes of LZW data: %d\n) 3 -1 roll sprintf
{(%stderr) (w) file exch writestring} {pop} ifelse
/LZWDecode filter
/stringbuffer 1024 string def
/output outfile (w) file def
{dup stringbuffer readstring 1 index length 0 gt or
  {output exch writestring} {pop output flushfile exit} ifelse} loop
[ outfile status ] 1 get dup 0 gt
  {[0] astore 128 string (bytes written: %d\n) 3 -1 roll sprintf
    {(%stderr) (w) file exch writestring} {pop} ifelse}
  {pop}
  ifelse
