SHELL := /bin/bash  # we're using Bashisms
all: lzw.pylint lzw.doctest card.view
%.gs: %.pdf /usr/bin/pdf2ps
	pdf2ps $< $@
%.ps: %.pdf /usr/bin/pdftops
	pdftops $< $@
/usr/bin/pdf2ps:
	@echo Must install ghostscript package >&2
/usr/bin/pdftops:
	@echo Must install poppler-utils package >&2
%.a85: %.gs
	echo '<~' > $@
	sed '1,/^ID$$/d' $< | sed '/^EI Q$$/,$$d' >> $@
%.lzw: %.a85
	cat $< | ascii85 -d > $@
%.rgb: %.lzw
	python3 ./lzw.py $< $@ 2>/tmp/lzw.log
%.rgb.broken: %.lzw  # trying to use gzip decompress, not working
	WIDTH=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$5}' $*.gs); \
	HEIGHT=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$4}' $*.gs); \
	SIZE=$$((WIDTH * HEIGHT * 300)); \
	MODULUS=$$(printf %08x $$(($$SIZE % 0x100000000))); \
	cat <(echo 1f8b0800000000000000 | xxd -r -p) \
	 $< \
	 <(echo 00000000$$MODULUS | xxd -r -p) \
	 > $@
%.jpg: %.rgb %.gs
	WIDTH=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$5}' $*.gs); \
	HEIGHT=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$4}' $*.gs); \
	SIZE=$$((WIDTH * HEIGHT * 3)); \
	IMAGESIZE=$$(stat --format=%s $<); \
	if [ "$${SIZE}00" = "$$IMAGESIZE" ]; then \
	 convert -size $${WIDTH}0x$${HEIGHT}0 -depth 8 rgb:$< \
	  -resize $${WIDTH}x$${HEIGHT} $@; \
	else \
	 convert -size $${WIDTH}x$${HEIGHT} -depth 8 rgb:$< $@; \
	fi
%.view: %.jpg
	display $<
fixedcard.pdf: card.gs card.patch
	-patch $+  # ignore error about already-patched file
	ps2pdf $< $@
clean:
	rm -rf *.a85 *.ps *.lzw *.rgb *.gs *.jpg *.png *.broken
%.pylint: %.py
	pylint $<
%.doctest: %.py
	python3 -m doctest $<
