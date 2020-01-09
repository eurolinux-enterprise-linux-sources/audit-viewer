# The main program.
# coding=utf-8
#
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

import gettext
import locale
import optparse
import sys

import gtk.glade
import gnome.ui

import client
from main_window import MainWindow
import settings
import util

_ = gettext.gettext

if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain(settings.gettext_domain, settings.localedir)
    gettext.bind_textdomain_codeset(settings.gettext_domain, 'utf-8')
    gettext.textdomain(settings.gettext_domain)

    parser = optparse.OptionParser(usage = _('%prog [OPTION]... [FILE]...'),
                                   version = ('audit-viewer %s'
                                              % settings.version),
                                   description = _('Start an audit event '
                                                   'viewer.'))
    parser.add_option('-u', '--unprivileged', action = 'store_true',
                      dest = 'unprivileged',
                      help = _('do not attempt to start the privileged backend '
                               'for reading system audit logs'))
    parser.set_defaults(unprivileged = False)
    (options, args) = parser.parse_args()

    gnome.init(settings.gettext_domain, settings.version)
    gtk.glade.bindtextdomain(settings.gettext_domain, settings.localedir)
    gtk.glade.textdomain(settings.gettext_domain)

    if options.unprivileged:
        cl = None
    else:
        try:
            cl = client.Client()
        except (IOError, OSError), e:
            util.modal_error_dialog(None,
                                    _('Error running audit-viewer-server: %s')
                                    % e.strerror)
            sys.exit(1)
        except client.ClientNotAvailableError:
            cl = None

    w = MainWindow(cl)
    if w.setup_initial_window(args):
        gtk.main()
