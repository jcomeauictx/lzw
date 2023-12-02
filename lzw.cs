#!/usr/src/jcomeauictx/casperscript/bin/bccs
(card.lzw) (r) file dup bytesavailable (bytes available: ) print ==
/LZWDecode filter (pstack:) == pstack
/stringbuffer 1024 string def
/outfile (card.rgb.check) (w) file def
{dup stringbuffer readstring 1 index length 0 gt or
  {outfile exch writestring} {pop exit} ifelse} loop
