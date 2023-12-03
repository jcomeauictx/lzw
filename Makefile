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
%.rgb: lzw.py %.lzw
	./$+ $@  #2>/tmp/lzw.log
%.view: %.rgb %.gs
	WIDTH=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$4}' $*.gs); \
	HEIGHT=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$5}' $*.gs); \
	SIZE=$$((WIDTH * HEIGHT * 3)); \
	IMAGESIZE=$$(stat --format=%s $<); \
	if [ "$${SIZE}00" = "$$IMAGESIZE" ]; then \
	 display -size $${WIDTH}0x$${HEIGHT}0 -depth 8 -flip \
	  -resize $${WIDTH}x$${HEIGHT} rgb:$<; \
	else \
	 display -size $${WIDTH}x$${HEIGHT} -depth 8 -flip rgb:$<; \
	fi
fixedcard.pdf: card.gs card.patch
	-patch $+  # ignore error about already-patched file
	ps2pdf $< $@
clean:
	rm -rf *.a85 *.ps *.lzw *.rgb *.gs *.jpg *.png *.broken __pycache__
distclean: clean
	rm -f fixedcard.pdf *.rej *.check *.doctest *.pylint *.raw
%.pylint: %.py
	pylint $< > $@
%.doctest: %.py
	python3 -m doctest $< > $@
