SHELL := /bin/bash  # we're using Bashisms
all: card.view
%.gs: %.pdf /usr/bin/pdf2ps
	pdf2ps $< $@
%.ps: %.pdf /usr/bin/pdftops
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
	./lzw.py $< $@
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
clean:
	rm -rf *.a85 *.ps *.lzw *.rgb *.gs *.jpg
