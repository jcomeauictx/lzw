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
%.view: %.rgb %.gs
	WIDTH=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$5}' $*.gs); \
	HEIGHT=$$(awk '$$1 ~ /%%BoundingBox:/ {print $$4}' $*.gs); \
	echo $$WIDTH $$HEIGHT
clean:
	rm -rf *.a85 *.ps *.lzw *.rgb *.gs
