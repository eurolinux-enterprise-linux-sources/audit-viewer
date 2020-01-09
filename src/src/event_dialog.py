# An "Event Details" dialog
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
import time

import gtk
import gobject

from dialog_base import DialogBase
import event_source
import util

__all__ = ('EventDialog')

class EventDialog(DialogBase):

    '''An event details dialog.'''
    # FIXME: more user-friendly - detailed explanation for each field?
    # FIXME: allow immediate search for (one or more) field values?

    _glade_widget_names = ('event_dialog_close', 'event_dialog_next_event',
                           'event_dialog_prev_event', 'event_dialog_records',
                           'event_dialog_sn', 'event_dialog_time',
                           'event_dialog_values')

    def __init__(self, parent, position):
        DialogBase.__init__(self, 'event_dialog', parent)
        self.position = position

        self.value_store = gtk.ListStore(gobject.TYPE_STRING,
                                         gobject.TYPE_STRING)
        self.event_dialog_values.set_model(self.value_store)
        c = gtk.TreeViewColumn(_('Field'), gtk.CellRendererText(), text = 0)
        c.set_resizable(True)
        self.event_dialog_values.append_column(c)
        c = gtk.TreeViewColumn(_('Value'), gtk.CellRendererText(), text = 1)
        c.set_resizable(True)
        self.event_dialog_values.append_column(c)
        self.value_selection = self.event_dialog_values.get_selection()
        self.record_store = gtk.ListStore(gobject.TYPE_PYOBJECT,
                                          gobject.TYPE_STRING)
        self.event_dialog_records.set_model(self.record_store)
        c = gtk.TreeViewColumn(_('Record Type'), gtk.CellRendererText(),
                               text = 1)
        self.event_dialog_records.append_column(c)
        self.record_selection = self.event_dialog_records.get_selection()

        self.record_selection.connect('changed',
                                      self.__record_selection_changed)
        self.event_dialog_prev_event.connect('clicked',
                                             self.__prev_event_clicked)
        self.event_dialog_next_event.connect('clicked',
                                             self.__next_event_clicked)
        self.event_dialog_close.connect('clicked', self.__close_clicked)
        self.window.connect('delete-event', self.__close_clicked)

        self.position.change_cb = self.__position_changed
        self.__position_changed()

        self.__load_event()

    def __load_event(self):
        '''Modify the dialog to reflect the current event, which must exist.'''
        event = self.position.current_event
        assert event is not None
        # Reparse the event to make sure all fields read an interpreted, and
        # all are stored in event.records.fields
        text = '\n'.join([record.raw for record in event.records]) + '\n'
        src = event_source.StringEventSource(text)
        events = tuple(src.read_events((), set(), True, False))
        assert len(events) == 1
        event = events[0]
        tm = time.localtime(event.id.sec)
        self.event_dialog_time.set_text(time.strftime('%x %X', tm))
        self.event_dialog_sn.set_text('%d' % event.id.serial)

        (_, it) = self.record_selection.get_selected()
        if it is None:
            old_record_type = None
        else:
            old_record_type = self.record_store.get_value(it, 1)
        old_record_it = None
        self.record_store.clear()
        for record in event.records:
            # FIXME: user-friendlier name?
            record_type = util.msgtype_string(record.type)
            it = self.record_store.append((record, record_type))
            if (old_record_type is not None and
                record_type == old_record_type and old_record_it is None):
                old_record_it = it
        if old_record_it is None:
            old_record_it = self.record_store.get_iter_first()
        self.record_selection.select_iter(old_record_it)
        self.__record_selection_changed()

    def __position_changed(self):
        self.event_dialog_prev_event.set_sensitive(self.position.has_prev())
        self.event_dialog_next_event.set_sensitive(self.position.has_next())

    def __record_selection_changed(self, *_):
        (model, it) = self.record_selection.get_selected()
        if it is None:
            return
        record = model.get_value(it, 0)

        (_, it) = self.value_selection.get_selected()
        if it is None:
            old_field_name = None
        else:
            old_field_name = self.value_store.get_value(it, 0)
        old_field_it = None
        self.value_store.clear()
        for (key, value) in sorted(record.fields, key = lambda x: x[0]):
            # FIXME: user-friendlier field name?
            it = self.value_store.append((key, value))
            if (old_field_name is not None and key == old_field_name and
                old_field_it is None):
                old_field_it = it
        if old_field_it is not None:
            self.value_selection.select_iter(old_field_it)

    def __prev_event_clicked(self, *_):
        self.position.to_prev()
        self.__load_event()

    def __next_event_clicked(self, *_):
        self.position.to_next()
        self.__load_event()

    def __close_clicked(self, *_):
        self.destroy()
        # Try to break the circular references
        self.position.disconnect()
        self.position = None
        return False
