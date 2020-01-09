# "Event list" tab properties dialog.
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
from gettext import gettext as _

import gobject
import gtk

import lists
from tab_properties import TabProperties
import util

__all__ = ('ListProperties')

class ListProperties(TabProperties):

    '''List properties dialog.'''

    _glade_widget_names = (('list_column_add', 'list_column_delete',
                            'list_column_down', 'list_column_name',
                            'list_column_up', 'list_columns',
                            'list_properties_notebook', 'list_sort_ascending',
                            'list_sort_by_field', 'list_sort_by_time',
                            'list_sort_descending', 'list_sort_field') +
                           tuple(TabProperties.
                                 _tab_glade_widget_names('list')))

    __date_column_text = _('Event date')
    __other_column_text = _('Other fields')
    def __init__(self, parent):
        TabProperties.__init__(self, parent, 'list')

        util.connect_and_run(self.list_sort_by_field, 'toggled',
                             self.__list_sort_by_field_toggled)
        self._init_field_combo(self.list_sort_field)

        self.column_store = gtk.ListStore(gobject.TYPE_STRING)
        self.list_columns.set_model(self.column_store)
        c = gtk.TreeViewColumn(_('Column'), gtk.CellRendererText(), text = 0)
        self.list_columns.append_column(c)
        self.list_columns.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.list_columns.connect('key-press-event',
                                  self.__list_columns_key_press)
        self.columns_selection = self.list_columns.get_selection()
        util.connect_and_run(self.columns_selection, 'changed',
                             self.__columns_selection_changed)
        self.list_column_up.connect('clicked', self.__list_column_up_clicked)
        self.list_column_down.connect('clicked',
                                      self.__list_column_down_clicked)
        self.list_column_delete.connect('clicked',
                                        self.__list_column_delete_clicked)
        self.list_column_add.connect('clicked', self.__list_column_add_clicked)
        store = gtk.ListStore(gobject.TYPE_STRING)
        store.append((self.__date_column_text,))
        store.append(('',))
        for field in lists.field_names:
            store.append((field,))
        store.append(('',))
        store.append((self.__other_column_text,))
        self.list_column_name.set_model(store)
        self.list_column_name.set_text_column(0)
        self.list_column_name.set_row_separator_func(util.is_row_separator)

    __list_sort_map = (('list_sort_ascending', False),
                       ('list_sort_descending', True))
    def load(self, tab):
        errors = super(ListProperties, self).load(tab)

        self.list_sort_by_time.set_active(tab.sort_by is None)
        self.list_sort_by_field.set_active(tab.sort_by is not None)
        if tab.sort_by is None:
            self.list_sort_field.set_active(-1)
            self.list_sort_field.child.set_text('')
        else:
            util.set_combo_entry_text(self.list_sort_field, tab.sort_by)
        self._radio_set(tab.sort_reverse, self.__list_sort_map)

        self.column_store.clear()
        for column in tab.columns:
            if column is None:
                column = self.__other_column_text
            elif column is tab.date_column_label:
                column = self.__date_column_text
            self.column_store.append((column,))
        return errors

    def save(self, tab):
        super(ListProperties, self).save(tab)

        if self.list_sort_by_time.get_active():
            tab.sort_by = None
        else:
            tab.sort_by = self.list_sort_field.child.get_text()
            assert tab.sort_by != '', 'Should have been validated'
        tab.sort_reverse = self._radio_get(self.__list_sort_map)

        del tab.columns[:]
        it = self.column_store.get_iter_first()
        while it is not None:
            column = self.column_store.get_value(it, 0)
            if column == self.__date_column_text:
                column = tab.date_column_label
            elif column == self.__other_column_text:
                column = None
            tab.columns.append(column)
            it = self.column_store.iter_next(it)

    def show_filter_tab(self):
        '''Show the filter list tab.'''
        self.list_properties_notebook.set_current_page(1)

    def _validate_get_failure(self):
        r = TabProperties._validate_get_failure(self)
        if r is not None:
            return r

        if (self.list_sort_by_field.get_active() and
            self.list_sort_field.child.get_text() == ''):
            return (_('Field name must not be empty'), 0,
                    self.list_sort_field)
        return None

    def __list_columns_key_press(self, unused_widget, event):
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete):
            (model, it) = self.columns_selection.get_selected()
            if it is not None:
                self.__list_column_delete_clicked()
            return True
        return False

    def __columns_selection_changed(self, *_):
        (model, it) = self.columns_selection.get_selected()
        self.list_column_delete.set_sensitive(it is not None)
        t = (it is not None and
             model.get_path(it) != model.get_path(model.get_iter_first()))
        self.list_column_up.set_sensitive(t)
        self.list_column_down.set_sensitive(it is not None and
                                            model.iter_next(it) is not None)

    def __list_column_up_clicked(self, *_):
        util.tree_model_move_up(self.columns_selection)
        self.__columns_selection_changed()

    def __list_column_down_clicked(self, *_):
        util.tree_model_move_down(self.columns_selection)
        self.__columns_selection_changed()

    def __list_column_delete_clicked(self, *_):
        util.tree_model_delete(self.columns_selection)

    def __list_column_add_clicked(self, *_):
        column = self.list_column_name.child.get_text()
        # FIXME: do something if column is empty
        (model, it) = self.columns_selection.get_selected()
        it = model.insert_after(it)
        model.set_value(it, 0, column)
        self.columns_selection.select_iter(it)

    def __list_sort_by_field_toggled(self, *_):
        self.list_sort_field.set_sensitive(self.list_sort_by_field.get_active())
