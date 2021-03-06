docdir = @docdir@
EXTRA_DIST = Doxyfile.in mainpage.doxy manual.docbook manual.README

# dist-hook may be not portable partly, so non-SuSE-users please
# forgive me and don't call "make dist" or send me a patch ;-)

dist-hook: manual-html manual-pdf manual-manpages reference-html
	mkdir $(distdir)/manual
	cp -r $(srcdir)/manual/* $(distdir)/manual/
	mkdir $(distdir)/reference
	cp $(srcdir)/reference/* $(distdir)/reference/
	cp manual.pdf $(distdir)/

manual-prepare:
	sed -e 's,<title>CapiSuite [0-9a-z\.]*</title>,<title>CapiSuite $(VERSION)</title>,g' \
	  manual.docbook > manual.new # (not another *.in file...)
	mv manual.new manual.docbook
	xmllint --noout --valid manual.docbook

manual-html: manual-prepare
	xsltproc --stringparam profile.condition html -o manual-profiled.docbook /usr/share/sgml/docbook/docbook-xsl-stylesheets/profiling/profile.xsl manual.docbook
	xsltproc -o manual/ /usr/share/sgml/docbook/docbook-xsl-stylesheets/xhtml/chunk.xsl manual-profiled.docbook
	rm manual-profiled.docbook
	cp -r /usr/share/sgml/docbook/docbook-xsl-stylesheets/images/ manual/ # missing images...
	if test ! -d manual/images/callouts; then \
		echo "manual pages weren't created succesful." ;\
		exit 1; \
	fi

manual-manpages: manual-prepare
	xsltproc --stringparam profile.condition man -o manual-profiled.docbook /usr/share/sgml/docbook/docbook-xsl-stylesheets/profiling/profile.xsl manual.docbook
	xsltproc -o manpages/ /usr/share/sgml/docbook/docbook-xsl-stylesheets/manpages/docbook.xsl manual-profiled.docbook
	rm manual-profiled.docbook

manual-pdf: manual-prepare
	xsltproc --stringparam profile.condition pdf -o manual.xml /usr/share/sgml/docbook/docbook-xsl-stylesheets/profiling/profile.xsl manual.docbook
	db2pdf manual.xml 
	-rm CATALOG.local manual.aux manual.log manual.out manual.tex suse-*.dsl manual.xml

reference-html: Doxyfile.in
	sed -e 's,@VERSION\@,$(VERSION),g' \
	    -e 's,@capisuite_sources\@,$(top_srcdir)/src,g' \
	    -e 's,@docbuilddir\@,.,g' \
	    -e 's,@srcdir\@,$(srcdir),g' Doxyfile.in > Doxyfile
	$(doxygen) Doxyfile
	if test ! -d reference; then \
		echo "Creation of reference didn't succeed. Please install doxygen and try again" ;\
		exit 1; \
	fi
	rm Doxyfile
	
install-data-local:
	if test -d reference; then \
		$(mkinstalldirs) $(DESTDIR)$(docdir)/reference ; \
		(cd reference; for i in *; do \
			$(INSTALL_DATA) $$i $(DESTDIR)$(docdir)/reference/$$i  ;\
		done;) ;\
	fi
	if test -d manual; then \
		$(mkinstalldirs) $(DESTDIR)$(docdir) ; \
		cp -r manual $(DESTDIR)$(docdir)/ ; \
	fi
	if test -f manual.pdf; then \
		cp manual.pdf $(DESTDIR)$(docdir)/ ; \
	fi

uninstall-local:
	rm -rf $(DESTDIR)$(docdir) 

maintainer-clean-local:
	rm -rf reference manual manual.pdf
 
