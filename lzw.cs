#!/usr/src/jcomeauictx/casperscript/bin/bccs
/infile argc 1 gt {argv 1 get} {(/dev/stdin)} ifelse def
/outfile argc 2 gt {argv 2 get} {(/dev/stdout)} ifelse def
infile (r) file dup bytesavailable (bytes available: ) print ==
/LZWDecode filter (pstack:) == pstack
/stringbuffer 1024 string def
/output outfile (w) file def
{dup stringbuffer readstring 1 index length 0 gt or
  {output exch writestring} {pop exit} ifelse} loop
