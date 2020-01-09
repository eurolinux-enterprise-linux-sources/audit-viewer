# Search text entry
#
# Copyright (C) 2007, 2008 Red Hat, Inc.  All rights reserved.
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
# Behavior and implementation ideas based on rb-search-entry.c from Rhythmbox
# and e-search-bar.c from Evolution.
from gettext import gettext as _

import gobject
import gtk
import sexy

__all__ = ('SearchEntry')

class SearchEntry(sexy.IconEntry):

    '''A widget for entering search text.'''

    __gsignals__ = { 'update-search': (gobject.SIGNAL_RUN_LAST,
                                       gobject.TYPE_NONE,
                                       (gobject.TYPE_STRING,)) }

    def __init__(self):
        super(SearchEntry, self).__gobject_init__()
        self.set_icon(sexy.ICON_ENTRY_PRIMARY,
                      gtk.image_new_from_stock(gtk.STOCK_FIND,
                                               gtk.ICON_SIZE_MENU))
        self.add_clear_button()
        self.last_search_text = self.get_text()
        self.search_text_is_empty = True # Overrides the displayed text

        self.connect('changed', self.__changed)
        self.connect('focus-in-event', self.__focus_in)
        self.connect('focus-out-event', self.__focus_out)
        self.connect('activate', self.__activate)
        self.connect('icon-released', self.__icon_released)

        self.__update_state()

    @property
    def real_text(self):
        '''The logical value of the search text.'''
        if self.search_text_is_empty:
            return ''
        return self.get_text()

    def __update_state(self):
        '''Immediately update widget state.'''
        t = self.real_text
        if self.last_search_text != t:
            self.last_search_text = t
            self.emit('update-search', t)

        style = gtk.widget_get_default_style()
        if (self.flags() & gtk.HAS_FOCUS) == 0 and self.search_text_is_empty:
            self.modify_base(gtk.STATE_NORMAL, None)
            self.modify_text(gtk.STATE_NORMAL,
                             style.text[gtk.STATE_INSENSITIVE])
            self.set_text(_('Search...'))
        elif t != '':
            self.modify_base(gtk.STATE_NORMAL, style.base[gtk.STATE_SELECTED])
            self.modify_text(gtk.STATE_NORMAL, style.text[gtk.STATE_SELECTED])
        else:
            self.modify_base(gtk.STATE_NORMAL, None)
            self.modify_text(gtk.STATE_NORMAL, None)

    def __changed(self, *_):
        t = self.real_text
        self.set_icon_highlight(sexy.ICON_ENTRY_SECONDARY, t != '')

    def __focus_in(self, *_):
        if self.search_text_is_empty:
            self.set_text('')
            self.search_text_is_empty = False
        self.__update_state()
        return False

    def __focus_out(self, *_):
        if self.get_text() == '':
            self.search_text_is_empty = True
        self.__update_state()
        return False

    def __activate(self, *_):
        self.__update_state()

    def __icon_released(self, unused_widget, pos, button):
        if pos == sexy.ICON_ENTRY_SECONDARY and button == 1:
            # The icon entry was just cleared by the handler in libsexy
            self.__update_state()

gobject.type_register(SearchEntry)
