# lzw decompression
I started this project after receiving my Red Cross first aid certification
card as a badly formatted PDF, and wanted to fix it. It used to be, in the
distant past, easy to convert a PDF into an eminently readable and editable
postscript file. Sadly, this is no longer the case.

I converted the PDF using both ghostscript's `pdf2ps` and poppler-utils's
`pdftops`, but neither had anything resembling text at first glance. What I did
find was an image the same size as the PDF, so surmised that Red Cross had
simply made an image with the whole contents of the card and turned it into
a PDF. That turned out to be correct.

First, I had to decode the Ascii85, and found the ruby-ascii85 package for that,
but later I realized that Python3 has ascii85 support hidden in the base64
module, and wrote a script that half-assed mimics the Ruby program.
Then I had LZW-encoded data. Surely there's a Unix utility to decompress Lempel-
Ziv-Welch files, right? Well, if there is, my google-fu failed to turn anything
up. I did find two projects, <https://michaeldipperstein.github.io/lzw.html>
and <https://github.com/joeatwork/python-lzw> that helped, but neither worked
for me out of the box. So, after some cursing, I coded up my own. It seemed to
work&mdash;it produced output of the expected length&mdash;but the result was
all white, with a few lines of various shades of gray near the bottom. I finally
(two days later) found I had swapped width and height, and when displayed
correctly, those gray lines coalesced into the certification card, but flipped
vertically. I then confirmed my LZW decoder worked properly by using the
PostScript (ghostscript, casperscript) LZWDecode filter (see lzw.cs) and
confirming it produced identical results.

I ended up fixing the PDF by:
1. `make card.gs`
2. editing the postscript, changing all 3 instances of `showpage` to a unique
misspelling, to find out which was being used.
3. inserting code before that showpage to erase the badly-formatted URL and
rewrite it, using a font name I found in the PDF text and a size I got through
repeated experimentation.

The result of that you can see in the patch file (card.patch) and in the
result of `make fixedcard.pdf`.
