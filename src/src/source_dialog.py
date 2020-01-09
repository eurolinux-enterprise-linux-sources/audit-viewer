# An "Audit Event Source" dialog
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
from gettext import gettext as _

import gtk
import gobject

from dialog_base import DialogBase
import event_source
import util

__all__ = ('SourceDialog')

class SourceDialog(DialogBase):

    '''An event source dialog.'''

    __gsignals__ = { 'destroy': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                 ()),
                     'apply': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()) }

    _glade_widget_names = ('source_apply',
                           'source_log', 'source_log_label',
                           'source_path', 'source_path_browse',
                           'source_path_label',
                           'source_type_file', 'source_type_log',
                           'source_with_rotated')

    def __init__(self, parent, client):
        DialogBase.__init__(self, 'source_dialog', parent)
        self.client = client
        self.__running_modally = False

        self.__log_store = gtk.ListStore(gobject.TYPE_STRING)
        self.source_log.set_model(self.__log_store)
        cell = gtk.CellRendererText()
        self.source_log.pack_start(cell, True)
        self.source_log.set_attributes(cell, text = 0)

        util.connect_and_run(self.source_with_rotated, 'toggled',
                             self.__source_with_rotated_toggled)
        util.connect_and_run(self.source_type_log, 'toggled',
                             self.__source_type_log_toggled)
        util.connect_and_run(self.source_type_file, 'toggled',
                             self.__source_type_file_toggled)
        self._setup_browse_button(self.source_path_browse, self.source_path,
                                  _('Audit Log File'),
                                  gtk.FILE_CHOOSER_ACTION_OPEN)
        self.window.connect('destroy', self.__window_destroy)
        self.window.connect('response', self.__window_response)

    def run(self):
        '''Run the dialog modally until it is "correctly" closed.

        Assumes the caller is handling the 'apply' signal.

        '''
        self.__running_modally = True
        self.source_apply.hide() # What does "apply" mean in a modal dialog?
        res = self.window.run()
        # If there is an error, self.__window_response() has already reported
        # it, so call self._validate_get_failure() instead of
        # self._validate_values() here.
        while (res == gtk.RESPONSE_OK and
               self._validate_get_failure() is not None):
            res = self.window.run()
        # If the response is gtk.RESPONSE_OK and the values validate,
        # self.__window_response() has already emitted 'apply'.
        self.source_apply.show()
        self.__running_modally = False
        return res

    def load(self, main_window):
        '''Modify dialog controls to reflect main_window.'''
        self.source_type_log.set_sensitive(self.client is not None)

        source = main_window.event_source
        if isinstance(source, event_source.ClientEventSource):
            self.source_with_rotated.set_active(False)
            self.source_type_log.set_active(True)
            util.set_combo_option(self.source_log, source.filename)
        elif isinstance(source, event_source.ClientWithRotatedEventSource):
            self.source_with_rotated.set_active(True)
            self.source_type_log.set_active(True)
            util.set_combo_option(self.source_log, source.base)
        elif isinstance(source, event_source.FileEventSource):
            self.source_with_rotated.set_active(False)
            self.source_type_file.set_active(True)
            self.source_path.set_text(source.path)
        else:
            assert isinstance(source,
                              event_source.FileWithRotatedEventSource), \
                'Unexpected event source'
            self.source_with_rotated.set_active(True)
            self.source_type_file.set_active(True)
            self.source_path.set_text(source.base)

    def save(self, main_window):
        '''Modify main_window to reflect dialog state.'''
        if self.source_type_log.get_active():
            assert self.client is not None
            it = self.source_log.get_active_iter()
            assert it is not None
            name = self.__log_store.get_value(it, 0)
            if self.source_with_rotated.get_active():
                source = event_source.ClientWithRotatedEventSource(self.client,
                                                                   name)
            else:
                source = event_source.ClientEventSource(self.client, name)
        else:
            path = self.source_path.get_text()
            if self.source_with_rotated.get_active():
                source = event_source.FileWithRotatedEventSource(path)
            else:
                source = event_source.FileEventSource(path)
        main_window.event_source = source

    def _validate_get_failure(self):
        if self.source_type_log.get_active():
            it = self.source_log.get_active_iter()
            if it is None:
                return (_('No system log file available'), None,
                        self.source_type_log)
        # Allow nonenxistent paths as base name in FileWithRotatedEventSource
        elif not self.source_with_rotated.get_active():
            path = self.source_path.get_text()
            try:
                f = open(path)
                f.close()
            except IOError, e:
                return (_('Error opening %s: %s') % (path, e.strerror), None,
                        self.source_path)
        return None

    def __source_type_log_toggled(self, *_):
        util.set_sensitive_all(self.source_type_log.get_active(),
                               self.source_log_label, self.source_log)

    def __source_with_rotated_toggled(self, *_):
        it = self.source_log.get_active_iter()
        if it is not None:
            old_value = self.__log_store.get_value(it, 0)
        else:
            old_value = None
        self.__log_store.clear()
        if self.client is not None:
            files = self.client.list_files()
            if self.source_with_rotated.get_active():
                files = sorted(name for name in files
                               if not event_source.is_rotated_file_name(name))
            else:
                files = event_source.sorted_log_files(files)
            for filename in files:
                self.__log_store.append((filename,))

            if old_value is not None:
                util.set_combo_option(self.source_log, old_value)
            if self.source_log.get_active_iter() is None:
                it = self.__log_store.get_iter_first()
                if it is not None:
                    self.source_log.set_active_iter(it)

    def __source_type_file_toggled(self, *_):
        util.set_sensitive_all(self.source_type_file.get_active(),
                               self.source_path_label, self.source_path,
                               self.source_path_browse)

    def __window_destroy(self, *_):
        self.emit('destroy')
        return False

    def __window_response(self, unused_widget, response):
        if response in (gtk.RESPONSE_APPLY, gtk.RESPONSE_OK):
            if not self._validate_values():
                return # Don't destroy the dialog
            self.emit('apply')
        if not self.__running_modally and response != gtk.RESPONSE_APPLY:
            self.destroy()

gobject.type_register(SourceDialog)
