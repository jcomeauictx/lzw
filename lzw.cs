#!/usr/src/jcomeauictx/casperscript/bin/bccs
(card.lzw) (r) file dup bytesavailable (bytes available: ) print ==
/LZWDecode filter (pstack:) == pstack
1024 string /stringbuffer def
(%stdout) (w) file /outfile def
{dup stringbuffer readstring over length 0 gt or
  {outfile writestring} {exit} ifelse} loop
