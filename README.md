# lzw decompression
I started this project about 30 hours ago at the time of this writing, as I
had received my Red Cross first aid certification card as a badly formatted
PDF, and I wanted to fix it. It used to be, in the distant past, easy to
convert a PDF into an eminently readable and editable postscript file. Sadly,
this is no longer the case.

I converted the PDF using both ghostscript's `pdf2ps` and poppler-utils's
`pdftops`, but neither had anything resembling text at first glance. What I did
find was an image the same size as the PDF, so surmised that Red Cross had
simply made an image with the whole contents of the card and turned it into
a PDF. That turned out to be wrong, but in the process I learned a lot.

First, I had to decode the Ascii85, and found the ruby-ascii85 package for that.
Then I had LZW-encoded data. Surely there's a Unix utility to decompress Lempel-
Ziv-Welch files, right? Well, if there is, my google-fu failed to turn anything
up. I did find two projects, <<https://michaeldipperstein.github.io/lzw.html>>
and <<https://github.com/joeatwork/python-lzw>> that helped, but neither worked
for me out of the box. So, after some cursing, I coded up my own. It seems to
work--it produces output of the expected length--but the result is all white,
with a few lines of various shades of gray near the bottom.

I did find, by `less`ing through the PDF itself, some `<004C>` and similar
entities, which come close to spelling my name, but as of now, with insufficient
sleep and waning interest, I'm going to call this project done for the
foreseeable future.
