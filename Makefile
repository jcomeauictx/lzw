SHELL := /bin/bash  # we're using Bashisms
ASCII85 := $(shell PATH=$(PATH):. \
	     which ascii85 ascii85.py 2>/dev/null | head -n 1)
ifneq ($(SHOW_ENV),)
  export
endif
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
%.lzw %.rle: %.a85
	cat $< | $(ASCII85) -d > $@
%.rgb:  %.lzw
	./lzw.py decode $< $@  #2>/tmp/lzw.log
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
env:
	if [ -z $(SHOW_ENV) ]; then \
	 $(MAKE) SHOW_ENV=1 $@; \
	else \
	 $@; \
	fi
%.pnm: %.png
	pngtopam $< > $@
%.a85: %.eps
	echo '<~' > $@
	sed '1,/^image\r\?$$/d' $< | sed '/^grestore\r\?$$/,$$d' >> $@
%.rgb: %.rle
	python3 packbits.py unpack $< $@
%.rle.repacked: %.rgb
	python3 packbits.py pack $< $@
%.rgb.reunpacked: %.rle.repacked
	python3 packbits.py unpack $< $@
packtest: $(HOME)/tmp/sample.rgb.reunpacked
%.lzw.check: %.rgb
	python3 lzw.py encode $< $@
	diff $*.lzw $@
