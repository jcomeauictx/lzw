#!/usr/src/jcomeauictx/casperscript/bin/bccs
/action sys.argc 1 gt {sys.argv 1 get} {(decode)} ifelse def
/infile sys.argc 2 gt {sys.argv 2 get} {(/dev/stdin)} ifelse def
/outfile sys.argc 3 gt {sys.argv 3 get} {(/dev/stdout)} ifelse def
/input infile (r) file def /input /input.orig alias
/output outfile (w) file def /output /output.orig alias
input.orig bytesavailable [0] astore
128 string (bytes of input data: %d\n) 3 -1 roll sprintf
{(%stderr) (w) file exch writestring} {pop} ifelse
action (decode) eq
  {/input input /LZWDecode filter def}
  {/output output /LZWEncode filter def}
  ifelse
/stringbuffer 1024 string def
{input stringbuffer readstring 1 index length 0 gt or
{output exch writestring} {pop output flushfile exit} ifelse} loop
[ outfile status ] 1 get dup 0 gt
  {[0] astore 128 string (bytes written: %d\n) 3 -1 roll sprintf
    {(%stderr) (w) file exch writestring} {pop} ifelse}
  {pop}
ifelse
