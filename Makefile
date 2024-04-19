SHELL := /bin/bash  # we're using Bashisms
BYTECOUNT ?= 1000
ASCII85 := $(shell PATH=$(PATH):. \
	     which ascii85 ascii85.py 2>/dev/null | head -n 1)
PYTHON_DEBUGGING ?=
EOI_IS_EOD ?= 1
ifeq ($(EOI_IS_EOD),)
  IGNORE_EOI := .ignoreeoi
endif
ifneq ($(SHOW_ENV),)
  export
else
  export PYTHON_DEBUGGING EOI_IS_EOD
endif
all: lzwfilter.pylint lzwfilter.doctest
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
%.rgb:  %.lzw lzw.py
	python3 lzw.py decode $< $@  2>/tmp/$(@F).log
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
	pylint $< | tee $@
%.doctest: %.py
	python3 -m doctest $< 2>&1 | tee $@
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
%.lzw.check: %.rgb lzw.py
	-python3 lzw.py encode $< $@ 2>/tmp/$(@F)$(IGNORE_EOI).log
	-diff -q $*.lzw $@
%.rgb.check: %.lzw.check lzw.py
	-python3 lzw.py decode $< $@ 2>/tmp/$(@F)$(IGNORE_EOI).log
	-diff -q $*.rgb $@
%.diff: %.check
	diff -y <(head -c $(BYTECOUNT) $* | xxd) \
	 <(head -c $(BYTECOUNT) $< | xxd)
check: card.lzw.check card.rgb.check
encode.profile: lzw.py card.rgb
	python3 -c "import cProfile; \
	 from lzw import encode; \
	 instream = open('card.rgb', 'rb'); \
	 outstream = open('/tmp/card.lzw.tmp', 'wb'); \
	 cProfile.run('encode(instream, outstream)')" > $@
