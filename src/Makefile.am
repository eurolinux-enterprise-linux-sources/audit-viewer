# Copyright (C) 2008 Red Hat, Inc.  All rights reserved.
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program; if
# not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth
# Floor, Boston, MA 02110-1301, USA.  Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#
# Red Hat Author: Miloslav Trmac <mitr@redhat.com>

## Process this file with automake to produce Makefile.in

## Settings
ACLOCAL_AMFLAGS = -I m4
applicationsdir = $(datarootdir)/applications
configsdir = $(pkgdatadir)/configs
configs_listdir = $(configsdir)/Selected_Events
configs_overviewdir = $(configsdir)/Overviews
configs_reportdir = $(configsdir)/Summary_Reports
mimedir = $(datarootdir)/mime
pkgmimedir = $(mimedir)/packages

## Targets
SUBDIRS = po

applications_DATA = audit-viewer.desktop
bin_SCRIPTS = src/audit-viewer
libexec_PROGRAMS = src/audit-viewer-server
man_MANS = doc/audit-viewer.8
pkgmime_DATA = audit-viewer.xml
dist_pkgdata_DATA = src/audit-viewer.glade
pkgdata_PYTHON = src/client.py \
	src/dialog_base.py \
	src/event_dialog.py src/event_source.py \
	src/filters.py src/format_versions.py \
	src/list_properties.py src/list_tab.py src/lists.py \
	src/main.py src/main_window.py \
	src/report_properties.py src/report_tab.py \
	src/save_extra.py src/search_entry.py src/source_dialog.py \
	src/statistic.py \
	src/tab.py src/tab_properties.py \
	src/util.py
nodist_pkgdata_PYTHON = src/settings.py src/server.py
dist_configs_list_DATA = \
	configs/Selected_Events/AVC_Messages.audit-viewer \
	configs/Selected_Events/Event_Overview.audit-viewer \
	configs/Selected_Events/Executable_File_Events.audit-viewer \
	configs/Selected_Events/File_Events.audit-viewer \
	configs/Selected_Events/Host_Events.audit-viewer \
	configs/Selected_Events/Login_Attempts.audit-viewer \
	configs/Selected_Events/PID_Events.audit-viewer \
	configs/Selected_Events/System_Call_Events.audit-viewer \
	configs/Selected_Events/Terminal_Events.audit-viewer \
	configs/Selected_Events/User_Events.audit-viewer
dist_configs_overview_DATA = \
	configs/Overviews/Todays_Events.audit-viewer \
	configs/Overviews/Yesterdays_Events.audit-viewer
dist_configs_report_DATA = \
	configs/Summary_Reports/Event_Summary.audit-viewer \
	configs/Summary_Reports/Executable_File_Summary.audit-viewer \
	configs/Summary_Reports/File_Summary.audit-viewer \
	configs/Summary_Reports/Host_Summary.audit-viewer \
	configs/Summary_Reports/PID_Summary.audit-viewer \
	configs/Summary_Reports/System_Call_Summary.audit-viewer \
	configs/Summary_Reports/Terminal_Summary.audit-viewer \
	configs/Summary_Reports/User_Summary.audit-viewer

install-fedora: install admin/audit-viewer-server.console
	mv $(DESTDIR)$(libexecdir)/audit-viewer-server \
		$(DESTDIR)$(libexecdir)/audit-viewer-server-real
	ln -s /usr/bin/consolehelper \
		$(DESTDIR)$(libexecdir)/audit-viewer-server
	$(MKDIR_P) $(DESTDIR)$(sysconfdir)/pam.d \
		$(DESTDIR)$(sysconfdir)/security/console.apps
	$(INSTALL_DATA) $(srcdir)/admin/audit-viewer-server.pam \
		$(DESTDIR)$(sysconfdir)/pam.d/audit-viewer-server
	$(INSTALL_DATA) admin/audit-viewer-server.console \
		$(DESTDIR)$(sysconfdir)/security/console.apps/audit-viewer-server

install-data-hook:
if RUN_UPDATE_MIME_DATABASE
	update-mime-database $(DESTDIR)$(mimedir)
endif

uninstall-hook:
if RUN_UPDATE_MIME_DATABASE
	update-mime-database $(DESTDIR)$(mimedir)
endif

## Rules
CLEANFILES = $(applications_DATA) $(bin_SCRIPTS) $(man_MANS) \
	$(nodist_pkgdata_PYTHON) $(pkgmime_DATA) \
	admin/audit-viewer-server.console
DISTCHECK_CONFIGURE_FLAGS = --disable-update-mimedb
EXTRA_DIST = admin/audit-viewer-server.console.in \
	admin/audit-viewer-server.pam \
	doc/audit-viewer.8.in \
	src/audit-viewer.in src/optparse_strings.py src/settings.py.in \
	audit-viewer.desktop.in audit-viewer.xml.in


src_audit_viewer_server_SOURCES = src/server.c src/server.h
src_audit_viewer_server_CPPFLAGS = $(AM_CPPFLAGS) -DLOCALEDIR='"$(localedir)"' \
	-DLOCALSTATEDIR='"$(localstatedir)"'

admin/audit-viewer-server.console: admin/audit-viewer-server.console.in Makefile
	$(MKDIR_P) admin
	sed 's|@''libexecdir''@|$(libexecdir)|g' \
		< $(srcdir)/admin/audit-viewer-server.console.in > $@

doc/audit-viewer.8: $(srcdir)/doc/audit-viewer.8.in Makefile
	$(MKDIR_P) doc
	sed 's|@''localstatedir''@|$(localstatedir)|g' \
		< $(srcdir)/doc/audit-viewer.8.in > $@

src/server.py: src/server.h Makefile
	$(MKDIR_P) src
	sed -n 's/#define[ \t]\+\([^ \t]\+\)[ \t]\+\([^ \t]\+\)\([ \t]\+.*\)\?$$/\1 = \2/p' \
		< $(srcdir)/src/server.h > $@

src/settings.py: src/settings.py.in Makefile
	$(MKDIR_P) src
	sed -e 's|@''PACKAGE''@|$(PACKAGE)|g' \
		-e 's|@''PACKAGE_VERSION''@|$(PACKAGE_VERSION)|g' \
		-e 's|@''configsdir''@|$(configsdir)|g' \
		-e 's|@''libexecdir''@|$(libexecdir)|g' \
		-e 's|@''localedir''@|$(localedir)|g' \
		-e 's|@''pkgdatadir''@|$(pkgdatadir)|g' \
		< $(srcdir)/src/settings.py.in > $@

src/audit-viewer: src/audit-viewer.in Makefile
	$(MKDIR_P) src
	sed -e 's|@''PYTHON''@|$(PYTHON)|g' \
		-e 's|@''SHELL''@|$(SHELL)|g' \
		-e 's|@''pkgdatadir''@|$(pkgdatadir)|g' \
		< $(srcdir)/src/audit-viewer.in > $@

@INTLTOOL_DESKTOP_RULE@
@INTLTOOL_XML_RULE@
