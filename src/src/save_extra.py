# Extra widgets for a FileChooserDialog used for saving files
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

import gobject
import gtk

from dialog_base import DialogBase

__all__ = ('SaveExtra')

class SaveExtra(DialogBase):

    '''Extra widgets for a FileChooserDialog.'''

    _glade_widget_names = ('save_extra_auto_extension',
                           'save_extra_type', 'save_extra_type_hbox')

    def __init__(self, types):
        '''Initialize the extra widgets.

        types is a sequence of (human readable label, extension) tuples.  The
        first type is assumed to be the default.

        '''
        DialogBase.__init__(self, 'save_extra_vbox', None)
        self.widget = self.window

        if len (types) > 1:
            self.__type_store = gtk.ListStore(gobject.TYPE_STRING,
                                              gobject.TYPE_STRING)
            for t in types:
                self.__type_store.append(t)
            self.save_extra_type.set_model(self.__type_store)
            cell = gtk.CellRendererText()
            self.save_extra_type.pack_start(cell, True)
            self.save_extra_type.set_attributes(cell, text = 0)
            it = self.__type_store.get_iter_first()
            self.save_extra_type.set_active_iter(it)
        else:
            self.__type_store = None
            self.widget.remove(self.save_extra_type_hbox)

    def get_auto_extension(self):
        '''Return whether we should automatically select an extension.'''
        return self.save_extra_auto_extension.get_active()

    def get_extension(self):
        '''Return an extension specifying the selected type.

        Only defined if len(types) >= 2 in the constructor.

        '''
        assert self.__type_store is not None
        it = self.save_extra_type.get_active_iter()
        return self.__type_store.get_value(it, 1)
