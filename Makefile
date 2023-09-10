PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrdtask
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrdtask.1 > nrrdtask.1.gz
	install -m755 nrrdtask/nrrdtask.py $(BINDIR)/nrrdtask
	install -m644 nrrdtask.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrdtask-completion.bash $(BSHDIR)
	rm -f nrrdtask.1.gz

uninstall:
	rm -f $(BINDIR)/nrrdtask
	rm -f $(MANDIR)/nrrdtask.1.gz
	rm -f $(BSHDIR)/nrrdtask-completion.bash
	rm -rf $(DOCDIR)

