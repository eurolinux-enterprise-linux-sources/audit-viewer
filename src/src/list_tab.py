# An "event list" tab
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
import csv
from gettext import gettext as _
import time
import xml.etree.cElementTree as cElementTree

import gobject
import gtk

from event_dialog import EventDialog
from list_properties import ListProperties
from search_entry import SearchEntry
from tab import Tab
import util

__all__ = ('ListTab')

def N_(s): return s

class ListPosition(object):

    '''A "event pointer" into the event list in a tab.

    The pointer can be invalidated any time, after notification by
    self.change_cb.'''

    def __init__(self, list_tab, model, it):
        self.__list_tab = list_tab
        self.__model = model
        self.__it = it
        self.change_cb = None
        self.__update_event_key()

    def has_prev(self):
        '''Return True if a previous event exists.'''
        return (self.__it is not None and
                self.__model.get_path(self.__it) !=
                self.__model.get_path(self.__model.get_iter_first()))

    def has_next(self):
        '''Return True if a next event exists.'''
        return (self.__it is not None and
                self.__model.iter_next(self.__it) is not None)

    def to_prev(self):
        '''Move to previous event (which must exist) and return it.'''
        # Ugly - but pygtk doesn't seem to support gtk_tree_path_prev()
        path = self.__model.get_path(self.__it)
        self.__it = self.__model.get_iter((path[0] - 1,))
        self.__update_event_key()
        if self.change_cb is not None:
            self.change_cb()

    def to_next(self):
        '''Move to next event (which must exist) and return it.'''
        self.__it = self.__model.iter_next(self.__it)
        self.__update_event_key()
        if self.change_cb is not None:
            self.change_cb()

    @property
    def current_event(self):
        '''The current event, or None.'''
        if self.__it is None:
            return None
        return self.__model.get_value(self.__it, 0)

    @property
    def event_key(self):
        '''(serial, sec, ms) for the current event.

        The key is preserved even if self.__it is None, and updated after
        moving to a different event.

        '''
        return self.__event_key

    def replace(self, model, it):
        '''Handle a list refresh.

        The model was replaced by model.  it corresponds to the previous
        self.current_event(), or it is None.

        '''
        self.__model = model
        self.__it = it
        if self.change_cb is not None:
            self.change_cb()

    def disconnect(self):
        '''Delete links to other objects to allow garbage collection.'''
        self.change_cb = None
        self.__model = None
        self.__it = None
        self.__list_tab.positions.remove(self)
        del self.__list_tab

    def __update_event_key(self):
        '''Update self.__event_key.'''
        event = self.__model.get_value(self.__it, 0)
        assert event is not None
        self.__event_key = (event.id.serial, event.id.sec, event.id.milli)

class ListTab(Tab):

    '''An "event list" tab.'''

    _glade_widget_names = ('list_filter_edit', 'list_filter_label',
                           'list_header_hbox', 'list_tree_view')

    _menu_label = N_('_List')
    _properties_class = ListProperties

    date_column_label = '__audit_viewer_date'

    __list_number = 1
    def __init__(self, filters, main_window, will_refresh = False):
        Tab.__init__(self, filters, main_window, 'list_vbox')

        # date_column_label == event date, None == all other columns
        self.columns = [self.date_column_label, None]
        self.sort_by = None # None == date
        self.sort_reverse = True
        self.positions = []
        self.text_filter = None

        self.__used_columns = None
        self.selection = self.list_tree_view.get_selection()
        self.tab_name = _('List %d') % ListTab.__list_number
        ListTab.__list_number += 1

        self.search_entry = SearchEntry()
        self.search_entry.show()
        self.search_entry.connect('update-search',
                                  self.__search_entry_update_search)
        self.list_header_hbox.pack_start(self.search_entry, False)
        self.list_tree_view.connect('row-activated',
                                    self.__list_tree_view_row_activated)
        self.list_filter_edit.connect('clicked',
                                      self.__list_filter_edit_clicked)
        util.connect_and_run(self.selection, 'changed',
                             self.__selection_changed)

        self.__refresh_dont_read_events = will_refresh
        self.refresh()
        self.__refresh_dont_read_events = False

    def event_details(self):
        (model, it) = self.selection.get_selected()
        if it is None:
            return
        lp = ListPosition(self, model, it)
        self.positions.append(lp)
        EventDialog(self.main_window.window, lp)

    def export(self):
        types = ((_('HTML'), '.html'), (_('CSV'), '.csv'),
                 (_('Raw log data'), '.log'))
        (filename, extension) = self.main_window.get_save_path(_('Export...'),
                                                               types,
                                                               self.tab_name)
        if filename is None:
            return
        try:
            if extension == '.csv':
                self.__export_csv(filename)
            elif extension == '.html':
                self.__export_html(filename)
            else:
                assert extension == '.log', ('Unexpected export type %s'
                                             % extension)
                self.__export_log(filename)
        except (IOError, OSError), e:
            self._modal_error_dialog(_('Error writing to %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        e.strerror))

    def refresh(self):
        event_sequence = self.__refresh_get_event_sequence()
        if event_sequence is None:
            return

        if self.filters:
            t = _(', ').join(f.ui_text() for f in self.filters)
        else:
            t = _('None')
        self.list_filter_label.set_text(t)
        self.__refresh_update_tree_view()

        events = self.__refresh_collect_events(event_sequence)
        self.__refresh_update_store(events)

    def report_on_view(self):
        self.main_window.new_report_tab(self.filters)

    def save_config(self, state):
        elem = super(ListTab, self).save_config(state)

        e = cElementTree.Element('sort')
        if self.sort_by is not None:
            e.set('type', 'field')
            e.set('field', self.sort_by.decode('utf-8'))
        else:
            e.set('type', 'date')
        e.set('reverse', { True: 'true', False: 'false' }[self.sort_reverse])
        elem.append(e)

        columns_elem = cElementTree.Element('columns')
        for title in self.columns:
            e = cElementTree.Element('column')
            if title is self.date_column_label:
                e.set('type', 'date')
            elif title is not None:
                e.set('type', 'field')
                e.set('field', title.decode('utf-8'))
            else:
                e.set('type', 'other_fields')
            columns_elem.append(e)
        elem.append(columns_elem)

        return elem

    def tab_select(self):
        Tab.tab_select(self)
        self.main_window.menu_report_on_view.show()
        self.main_window.menu_list_for_submenu.hide()
        self.main_window.menu_event_details.show()

    def _load_config(self, elem):
        for child_elem in elem:
            if child_elem.tag == 'sort':
                type_ = child_elem.get('type')
                if type_ == 'date':
                    self.sort_by = None
                elif type_ == 'field':
                    self.sort_by = util.xml_mandatory_attribute(child_elem,
                                                                'field')
                elif type_ is not None:
                    util.xml_raise_unknown_value(child_elem, 'type')
                v = child_elem.get('reverse')
                if v == 'true':
                    self.sort_reverse = True
                elif v == 'false':
                    self.sort_reverse = False
                elif v is not None:
                    util.xml_raise_unknown_value(child_elem, 'reverse')
            elif child_elem.tag == 'columns':
                self.columns = []
                for e in child_elem:
                    if e.tag != 'column':
                        continue
                    type_ = util.xml_mandatory_attribute(e, 'type')
                    if type_ == 'date':
                        self.columns.append(self.date_column_label)
                    elif type_ == 'field':
                        field = util.xml_mandatory_attribute(e, 'field')
                        self.columns.append(field)
                    elif type_ == 'other_fields':
                        self.columns.append(None)
                    else:
                        util.xml_raise_unknown_value(e, 'type')
        self.refresh()

    def __column_name(self, title):
        '''Return an user-readable name for title from self.columns.'''
        # FIXME: user-friendly column names
        if title is None:
            title = _('Other Fields')
        elif title is self.date_column_label:
            title = _('Date')
        return title

    def __export_csv(self, filename):
        '''Export data to filename in CSV.

        Raise IOError, OSError.

        '''
        def write_to_file(file):
            out = csv.writer(file)
            data = [self.__column_name(title) for title in self.columns]
            out.writerow(data)
            it = self.store.get_iter_first()
            while it is not None:
                store_column = 1
                for (column, title) in enumerate(self.columns):
                    if title is None:
                        data[column] = self.__other_column_text(it)
                    elif title is self.date_column_label:
                        event = self.store.get_value(it, 0)
                        data[column] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                     time.localtime(event.id
                                                                    .sec))
                    else:
                        data[column] = self.store.get_value(it, store_column)
                        store_column += 1
                out.writerow(data)
                it = self.store.iter_next(it)

        util.save_to_file(filename, 'wb', write_to_file)

    def __export_html(self, filename):
        '''Export data to filename in HTML.

        Raise IOError, OSError.

        '''
        def write_to_file(f):
            '''Write data to file in HTML.'''
            H = util.html_escape
            f.write('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                    '"http://www.w3.org/TR/html4/strict.dtd">\n'
                    '<HTML>\n')
            f.write('<HEAD><TITLE>%s</TITLE>\n' % H(self.tab_name))
            f.write('<META http-equiv="Content-Type" '
                    'content="text/html; charset=UTF-8"></HEAD>\n')
            f.write('<BODY><H1>%s</H1>\n' % H(self.tab_name))
            f.write('<TABLE border><THEAD>\n'
                    '<TR>')
            for title in self.columns:
                f.write('<TH scope="col">%s</TH>'
                        % H(self.__column_name(title)))
            f.write('</TR>\n'
                    '</THEAD><TBODY>\n')
            it = self.store.get_iter_first()
            while it is not None:
                f.write('<TR>')
                store_column = 1
                for title in self.columns:
                    if title is None:
                        text = self.__other_column_text(it)
                    elif title is self.date_column_label:
                        text = self.__date_column_text(it)
                    else:
                        text = self.store.get_value(it, store_column)
                        store_column += 1
                    f.write('<TD>%s</TD>' % H(text))
                f.write('</TR>\n')
                it = self.store.iter_next(it)
            f.write('</TBODY></TABLE></BODY></HTML>\n')

        util.save_to_file(filename, 'w', write_to_file)

    def __export_log(self, filename):
        '''Export data to filename in the raw audit format.

        Raise IOError, OSError.

        '''
        def write_to_file(f):
            it = self.store.get_iter_first()
            while it is not None:
                event = self.store.get_value(it, 0)
                for record in event.records:
                    f.write(record.raw)
                    f.write('\n')
                it = self.store.iter_next(it)

        util.save_to_file(filename, 'wb', write_to_file)

    def __list_filter_edit_clicked(self, *_):
        self._show_properties_dialog()
        if self._properties_dialog is not None:
            self._properties_dialog.show_filter_tab()

    def __search_entry_update_search(self, *_):
        t = self.search_entry.get_text()
        if t == '':
            t = None
        if self.text_filter != t:
            self.text_filter = t
            self.refresh()

    def __list_tree_view_row_activated(self, *_):
        self.event_details()

    def __list_tree_view_column_clicked(self, _, column):
        if column is self.date_column_label:
            column = None
        if self.sort_by == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_by = column
            self.sort_reverse = False
        self.refresh()

    def __selection_changed(self, *_):
        (model, it) = self.selection.get_selected()
        self.main_window.menu_event_details.set_sensitive(it is not None)

    @staticmethod
    def __date_column_event_text(event):
        '''Return date column contents for event.'''
        # Keep this in sy c with __date_column_data_fn!
        return time.strftime('%x %X', time.localtime(event.id.sec))

    def __date_column_text(self, it):
        '''Return date column contents for it.'''
        event = self.store.get_value(it, 0)
        return self.__date_column_event_text(self, event)

    def __date_column_data_fn(self, unused_column, cell, model, it):
        '''Set CellRendererText's properties for a date column.'''
        # This should be fast, thus the ugly code without temporary variables
        # and manual inlining of self.__date_column_event_text
        cell.set_property('text',
                          time.strftime('%x %X',
                                        time.localtime(model.get_value(it, 0)
                                                       .id.sec)))

    @staticmethod
    def __other_column_event_text(event):
        '''Return "Other fields" column contents for event.'''
        # Keep this in sync with __other_column_data_fn!

        # self.refresh() has removed used field values from event.fields, so
        # what is left for this function is truly the other fields.
        items = ([key + '=' + value
                  for (key, values) in (event.fields .iteritems())
                  for value in values]
                 + [key + '=' + value
                    for record in event.records
                    for (key, value) in record.fields])
        return ', '.join(items)

    def __other_column_text(self, it):
        '''Return "Other fields" column contents for it.'''
        event = self.store.get_value(it, 0)
        return self.__other_column_event_text(event)

    def __other_column_data_fn(self, unused_column, cell, model, it):
        '''Set CellRendererText's properties for an "Other fields" column.'''
        # Keep this in sync with __other_column_event_text!

        # This should be fast, thus the ugly code without temporary variables
        # and manual inlining of self.__other_column_text
        event = model.get_value(it, 0)
        # self.refresh() has removed used field values from event.fields, so
        # what is left for this function is truly the other fields.
        cell.set_property('text',
                          ', '.join([key + '=' + value
                                     for (key, values) in (event.fields
                                                           .iteritems())
                                     for value in values]
                                    + [key + '=' + value
                                       for record in event.records
                                       for (key, value) in record.fields]))

    def __refresh_get_event_sequence(self):
        '''Return an event sequence (as if from self.main_window.read_events()).

        Return None on error.

        '''
        if self.__refresh_dont_read_events:
            return ()
        wanted_fields = set()
        want_other_fields = False
        if self.sort_by is not None:
            wanted_fields.add(self.sort_by)
        for title in self.columns:
            if title is None:
                want_other_fields = True
            elif title is not self.date_column_label:
                wanted_fields.add(title)
        return self.main_window.read_events(self.filters, wanted_fields,
                                            want_other_fields, True)

    def __refresh_update_tree_view(self):
        '''Update self.list_tree_view for current configuration.

        Update self.__field_columns as well.

        '''
        if self.__used_columns is None or self.columns != self.__used_columns:
            self.__field_columns = [c for c in self.columns
                                    if (c is not None
                                        and c is not self.date_column_label)]
            self.store = gtk.ListStore(gobject.TYPE_PYOBJECT,
                                       *((gobject.TYPE_STRING,)
                                         * len(self.__field_columns)))
            self.list_tree_view.set_model(self.store)
            util.tree_view_remove_all_columns(self.list_tree_view)
            column = 1
            for title in self.columns:
                renderer = gtk.CellRendererText()
                c = gtk.TreeViewColumn(self.__column_name(title).replace('_',
                                                                         '__'),
                                       renderer)
                if title is None:
                    c.set_cell_data_func(renderer, self.__other_column_data_fn)
                elif title is self.date_column_label:
                    c.set_cell_data_func(renderer, self.__date_column_data_fn)
                else:
                    c.add_attribute(renderer, 'text', column)
                    column += 1
                c.set_resizable(True)
                c.set_fixed_width(100)  # A wild guess
                c.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                if title is not None:
                    c.set_clickable(True)
                    c.connect('clicked', self.__list_tree_view_column_clicked,
                              title)
                self.list_tree_view.append_column(c)
            self.__used_columns = self.columns[:]
        for (column, title) in enumerate(self.columns):
            if title is None:
                continue
            if title is self.date_column_label:
                title = None
            c = self.list_tree_view.get_column(column)
            if title == self.sort_by:
                c.set_sort_indicator(True)
                if not self.sort_reverse:
                    c.set_sort_order(gtk.SORT_ASCENDING)
                else:
                    c.set_sort_order(gtk.SORT_DESCENDING)
            else:
                c.set_sort_indicator(False)

    def __refresh_collect_events(self, event_sequence):
        '''Collect and order tuples for display in from event_sequence.

        Return an ordered list of (sort key, tuple for self.store) tuples.

        '''
        events = [] # [(sort key, [event, table fields...])]
        store_data = [None] * (1 + len(self.__field_columns))
        sort_key_None_container = (None,)
        for event in event_sequence:
            if self.sort_by is None:
                sort_key = event.id
            else:
                sort_key = event.fields.get(self.sort_by,
                                            sort_key_None_container)[0]
            store_data[0] = event
            column = 1
            event_fields_get = event.fields.get # Precompute
            for (column, title) in enumerate(self.__field_columns):
                l = event_fields_get(title, None)
                # "if l" == "if l is not None and len(l) > 0'
                store_data[column + 1] = l.pop(0) if l else ''
            events.append((sort_key, tuple(store_data)))
        events.sort(key = lambda event: event[0], reverse = self.sort_reverse)
        return events

    def __refresh_update_store(self, events):
        '''Update self.store and related data.

        events is the result of self.__refresh_collect_events().

        '''
        positions_for_event_key = {}
        for pos in self.positions:
            key = pos.event_key
            l = positions_for_event_key.setdefault(key, [])
            l.append(pos)
        self.store.clear()
        if (self.text_filter is None and
            len(positions_for_event_key) == 0): # Fast path
            for event in events:
                self.store.append(event[1])
        else:
            event_to_it = {}
            text_filter = self.text_filter
            if text_filter is not None:
                event_tuple_len = 1 + len(self.__field_columns)
                text_filter_check_date = False
                text_filter_check_other = False
                for title in self.columns:
                    if title is None:
                        text_filter_check_other = True
                    elif title is self.date_column_label:
                        text_filter_check_date = True
            for event in events:
                event_tuple = event[1]
                if text_filter is not None:
                    for i in xrange(1, event_tuple_len):
                        if event_tuple[i].find(self.text_filter) != -1:
                            break
                    else:
                        # This unfortunately makes our attempts to lazy-compute
                        # the values of these columns moot.
                        if ((not text_filter_check_date
                             or (self.__date_column_event_text(event_tuple[0]).
                                 find(self.text_filter) == -1)) and
                            (not text_filter_check_other
                             or (self.__other_column_event_text(event_tuple[0]).
                                 find(self.text_filter) == -1))):
                            continue
                it = self.store.append(event_tuple)
                event_id = event_tuple[0].id
                key = (event_id.serial, event_id.sec, event_id.milli)
                if key in positions_for_event_key:
                    event_to_it[key] = it
            for (key, l) in positions_for_event_key.iteritems():
                it = event_to_it.get(key, None)
                for pos in l:
                    pos.replace(self.store, it)

ListTab._set_xml_tab_name('event_list', ListTab)
