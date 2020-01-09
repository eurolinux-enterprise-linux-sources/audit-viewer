# Common tab properties dialog code.
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
import datetime
from gettext import gettext as _
import sys

import gobject
import gtk

from dialog_base import DialogBase
import event_source
import filters
import lists
import util

__all__ = ('TabProperties')

def N_(s): return s

class _FilterHandler(object):

    '''A filter handler chosen by _DateSection._date_date_type.'''

    def get_filter(self, section, op):
        '''Return a filter for section using the specified operator.'''
        raise NotImplementedError

    def set_filter(self, section, filt):
        '''Update section from filt.'''
        raise NotImplementedError

    def set_filter_class(self, filter_class):
        '''Work on filter_class.  Can be used in generic filter handlers.'''
        pass

    def update_sensitivity(self, section, sensitive):
        '''Update widget state in section after activating this handler.'''
        # We ignore sensitivity of our selector
        util.set_sensitive_all(sensitive and self._use_date,
                               section._date_date, section._date_hour,
                               section._date_minute_label, section._date_minute,
                               section._date_second_label, section._date_second,
                               section._date_ms_label, section._date_ms)

class _DateFilterHandler(_FilterHandler):

    '''A filter handler for a specified date.'''

    _use_date = True

    def get_filter(self, section, op):
        date = datetime.datetime.fromtimestamp(section._date_date.get_time())
        date = date.replace(hour = int(section._date_hour.get_value()),
                            minute = int(section._date_minute.get_value()),
                            second = int(section._date_second.get_value()))
        return filters.TimestampFilter(op, int(date.strftime('%s')),
                                       int(section._date_ms.get_value()))

    def set_filter(self, section, filt):
        section._date_date.set_time(filt.sec)
        date = datetime.datetime.fromtimestamp(filt.sec)
        section._date_hour.set_value(date.hour)
        section._date_minute.set_value(date.minute)
        section._date_second.set_value(date.second)
        section._date_ms.set_value(filt.ms)

class _NonDateFilterHandler(_FilterHandler):

    '''A filter handler that doesn't use the date widgets.'''

    _use_date = False

class _SimpleFilterHandler(_NonDateFilterHandler):

    '''A filter handler that just instantiates a filter class.'''

    def __init__(self):
        _NonDateFilterHandler.__init__(self)

    def get_filter(self, _, op):
        return self.__filter_class(op)

    def set_filter(self, _, filt):
        pass

    def set_filter_class(self, filter_class):
        self.__filter_class = filter_class

class _MinutesAgoDateHandler(_NonDateFilterHandler):

    '''A filter handler for a specified number of minutes ago.'''

    def __init__(self, minutes):
        _NonDateFilterHandler.__init__(self)
        self.minutes = minutes

    def get_filter(self, _, op):
        return filters.MinutesAgoFilter(op, self.minutes)

    def set_filter(self, _, filt):
        assert filt.minutes == self.minutes

class _DateSection(object):

    '''A set of widgets for specifying a date filter.'''

    __tab_glade_widget_names = ('_date', '_date_type', '_hour', '_minute',
                                '_minute_label', '_ms', '_ms_label', '_second',
                                '_second_label')

    # (name, _FilterHandler, type used for filter selection).  The handler
    # object instance is used for identifying _DateSection.__type_store
    # entries.
    __date_filter_handlers = (
        (N_('Specific time'), _DateFilterHandler(), filters.TimestampFilter),
        ('', None, None),
        (N_('Now'), _SimpleFilterHandler(), filters.NowFilter),
        (N_('10 minutes ago'), _MinutesAgoDateHandler(10),
         filters.MinutesAgoFilter),
        ('', None, None),
        (N_('Today'), _SimpleFilterHandler(), filters.TodayFilter),
        (N_('Yesterday'), _SimpleFilterHandler(), filters.YesterdayFilter),
        (N_('This week'), _SimpleFilterHandler(), filters.ThisWeekStartFilter),
        (N_('This month'), _SimpleFilterHandler(),
         filters.ThisMonthStartFilter),
        (N_('This year'), _SimpleFilterHandler(), filters.ThisYearStartFilter))

    @staticmethod
    def glade_widget_names(prefix):
        '''Return names of widgets for the specified prefix.'''
        return (prefix + name
                for name in _DateSection.__tab_glade_widget_names)

    def __init__(self, dialog, prefix):
        self.prefix = prefix
        for name in self.__tab_glade_widget_names:
            setattr(self, '_date' + name, getattr(dialog, prefix + name))

        self.__type_store = gtk.ListStore(gobject.TYPE_STRING,
                                          gobject.TYPE_PYOBJECT)
        for (label, handler, filter_class) in self.__date_filter_handlers:
            if handler is not None:
                handler.set_filter_class(filter_class)
            if label != '':
                label = _(label)
            self.__type_store.append((label, handler))
        self._date_date_type.set_model(self.__type_store)
        cell = gtk.CellRendererText()
        self._date_date_type.pack_start(cell, True)
        self._date_date_type.set_attributes(cell, text = 0)
        self._date_date_type.set_row_separator_func(util.is_row_separator)
        self._date_date_type.set_active_iter(self.__type_store.get_iter_first())

        self.__sensitive = True
        util.connect_and_run(self._date_date_type, 'changed',
                             self.__date_date_type_changed)

    def set_filter(self, filt):
        '''Update self to reflect filt.

        Return a list of user-readable reasons why editing the tab might lose
        information (ideally [].)

        '''
        for (_, handler, filter_class) in self.__date_filter_handlers:
            if filter_class is not None and isinstance(filt, filter_class):
                break
        else:
            return [_('Unsupported date filter "%s"') % filt.ui_text()]
        it = self.__type_store.get_iter_first()
        while it is not None:
            if self.__type_store.get_value(it, 1) is handler:
                self._date_date_type.set_active_iter(it)
                break
            it = self.__type_store.iter_next(it)
        else:
            assert False, 'Handler not found'
        handler.set_filter(self, filt)
        return []

    def get_filter(self, op):
        '''Return a filter for self using the specified operator.'''
        it = self._date_date_type.get_active_iter()
        handler = self.__type_store.get_value(it, 1)
        return handler.get_filter(self, op)

    def set_sensitive(self, sensitive):
        '''Change sensitivity status.'''
        self._date_date_type.set_sensitive(sensitive)
        self.__sensitive = sensitive
        self.__update_handler_sensitivity()

    def __date_date_type_changed(self, *_):
        self.__update_handler_sensitivity()

    def __update_handler_sensitivity(self, *_):
        '''Update sensitivity of widgets handled by the handler.'''
        it = self._date_date_type.get_active_iter()
        handler = self.__type_store.get_value(it, 1)
        handler.update_sensitivity(self, self.__sensitive)

class TabProperties(DialogBase):

    '''Tab properties dialog.'''

    __gsignals__ = { 'destroy': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                                 ()),
                     'apply': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()) }

    __tab_glade_widget_names = (('_filter_add', '_filter_delete',
                                 '_filter_expression', '_filter_field',
                                 '_filter_op', '_filter_value', '_filters',
                                 '_name',
                                 '_use_start_date', '_use_end_date')
                                + tuple(_DateSection.glade_widget_names('_end'))
                                + tuple(_DateSection
                                        .glade_widget_names('_start')))
    @staticmethod
    def _tab_glade_widget_names(prefix):
        '''Return names of common widgets for the specified prefix.'''
        return (prefix + name
                for name in TabProperties.__tab_glade_widget_names)

    def __init__(self, parent, prefix):
        DialogBase.__init__(self, prefix + '_properties', parent,
                            notebook_name = prefix + '_properties_notebook')
        for name in self.__tab_glade_widget_names:
            setattr(self, '_tab' + name, getattr(self, prefix + name))

        self.__filter_store = gtk.ListStore(gobject.TYPE_PYOBJECT,
                                            gobject.TYPE_STRING)
        self._tab_filters.set_model(self.__filter_store)
        c = gtk.TreeViewColumn(_('Rule'), gtk.CellRendererText(), text = 1)
        self._tab_filters.append_column(c)
        self._tab_filters.add_events(gtk.gdk.KEY_PRESS_MASK)
        self._tab_filters.connect('key-press-event', self.__filters_key_press)
        self.__filters_selection = self._tab_filters.get_selection()
        util.connect_and_run(self.__filters_selection, 'changed',
                             self.__filters_selection_changed)
        self._tab_filter_delete.connect('clicked',
                                        self.__tab_filter_delete_clicked)
        self._tab_filter_add.connect('clicked', self.__tab_filter_add_clicked)
        self._init_field_combo(self._tab_filter_field)
        self.__filter_op_store = gtk.ListStore(gobject.TYPE_STRING)
        for op in ('=', '!='):
            self.__filter_op_store.append((op,))
        self._tab_filter_op.set_model(self.__filter_op_store)
        cell = gtk.CellRendererText()
        self._tab_filter_op.pack_start(cell, True)
        self._tab_filter_op.set_attributes(cell, text = 0)

        self._start_date = _DateSection(self, '_tab_start')
        self._end_date = _DateSection(self, '_tab_end')
        util.connect_and_run(self._tab_use_start_date, 'toggled',
                             self.__tab_use_start_date_toggled)
        util.connect_and_run(self._tab_use_end_date, 'toggled',
                             self.__tab_use_end_date_toggled)
        self.window.connect('destroy', self.__window_destroy)
        self.window.connect('response', self.__window_response)

        self.__filter_expression_buffer = (self._tab_filter_expression
                                           .get_buffer())

    def load(self, tab):
        '''Modify dialog controls to reflect tab.

        Return a list of user-readable reasons why editing the tab might
        lose information (ideally [].)

        '''
        self._tab_name.set_text(tab.tab_name)
        self.__update_dialog_title()

        errors = []
        expressions = []
        start_date = None
        start_date_filter = None
        end_date = None
        end_date_filter = None
        self.__filter_store.clear()
        # Field filters can be applied immediately.  For time filters, use the
        # most restrictive TimestampFilter, and if none exists, use simply the
        # first other filter.  (Reports add TimestampFilters, so they should
        # always be more restrictive than the other time filters; we can't
        # compare other time filters than TimestampFilter).
        for filt in tab.filters:
            if isinstance(filt, filters.FieldFilter):
                it = self.__filter_store.append()
                self.__filter_store.set_value(it, 0, filt)
                self.__update_filter_store_row(it)
            elif isinstance(filt, filters.ExpressionFilter):
                expressions.append(filt.expression)
            elif isinstance(filt, filters.TimestampFilter):
                date = (filt.sec, filt.ms)
                if filt.op == '>=':
                    if start_date is None or start_date < date:
                        start_date = date
                        start_date_filter = filt
                elif filt.op == '<':
                    if end_date is None or end_date > date:
                        end_date = date
                        end_date_filter = filt
                else:
                    errors.append(_('Unsupported timestamp operator in "%s"')
                                  % filt.ui_text())
            else:
                if filt.op == '>=':
                    if start_date is None:
                        start_date_filter = filt
                elif filt.op == '<':
                    if end_date is None:
                        end_date_filter = filt
        if start_date_filter is not None:
            e = self._start_date.set_filter(start_date_filter)
            if len(e) > 0:
                errors += e
                start_date_filter = None
        self._tab_use_start_date.set_active(start_date_filter is not None)
        if end_date_filter is not None:
            e = self._end_date.set_filter(end_date_filter)
            if len(e) > 0:
                errors += e
                end_date_filter = None
        self._tab_use_end_date.set_active(end_date_filter is not None)
        if len(expressions) == 0:
            expr = ''
        elif len(expressions) == 1:
            expr = expressions[0]
        else:
            expr = ' && '.join(['(%s)' % e for e in expressions])
        self.__filter_expression_buffer.set_text(expr)
        return errors

    def save(self, tab):
        '''Modify tab to reflect dialog state.'''
        tab.set_tab_name(self._tab_name.get_text())
        self.__update_dialog_title()

        del tab.filters[:]
        it = self.__filter_store.get_iter_first()
        while it is not None:
            tab.filters.append(self.__filter_store.get_value(it, 0))
            it = self.__filter_store.iter_next(it)
        # start_date > end_date not tested for; because the filters can be
        # relative to current time, the answer can vary with time.
        if self._tab_use_start_date.get_active():
            tab.filters.append(self._start_date.get_filter('>='))
        if self._tab_use_end_date.get_active():
            tab.filters.append(self._end_date.get_filter('<'))
        expr = self.__get_filter_expression()
        if expr != '':
            # Validated in self._validate_get_failure()
            tab.filters.append(filters.ExpressionFilter(expr))

    def try_loading(self, tab):
        '''Try to modify dialog controls to reflect tab.

        If editing the tab might lose information, ask the user what to do.
        Return True if the tab was loaded correctly, False if not (and the user
        decided to cancel).

        '''
        errors = self.load(tab)
        if len(errors) > 0:
            dlg = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT,
                                    gtk.MESSAGE_WARNING, gtk.BUTTONS_NONE,
                                    _('Editing of some filters is not '
                                      'supported'))
            dlg.format_secondary_text(_('If you edit properties of this tab, '
                                        'these filters will be dropped from '
                                        "the tab's configuration:\n"
                                        '%s\n'
                                        'Do you still want to edit properties '
                                        'of this tab?') % '\n'.join(errors))
            dlg.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                            gtk.STOCK_EDIT, gtk.RESPONSE_OK)
            res = dlg.run()
            dlg.destroy()
            if res != gtk.RESPONSE_OK:
                return False
        return True

    def _validate_get_failure(self):
        if self._tab_name.get_text() == '':
            return (_('Tab name must not be empty'), 0, self._tab_name)
        expr = self.__get_filter_expression()
        if expr != '':
            msg = event_source.check_expression(expr)
            if msg is not None:
                return (msg, 4, self._tab_filter_expression)
        return None

    @staticmethod
    def _init_field_combo(combo):
        '''Initialize a GtkComboBoxEntry with known field names.'''
        store = gtk.ListStore(gobject.TYPE_STRING)
        for field in lists.field_names:
            store.append((field,))
        combo.set_model(store)
        combo.set_text_column(0)

    def __get_filter_expression(self):
        '''Return the text in self._tab_filter_expression.'''
        b = self.__filter_expression_buffer
        return b.get_text(b.get_start_iter(), b.get_end_iter())

    def __update_dialog_title(self):
        '''Update dialog title to match self._tab_name.'''
        # self._validate_get_failure() doesn't allow empty tab name
        self.window.set_title(_('%s Properties') % self._tab_name.get_text())

    def __filters_key_press(self, unused_widget, event):
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete):
            (model, it) = self.__filters_selection.get_selected()
            if it is not None:
                self.__tab_filter_delete_clicked()
            return True
        return False

    def __filters_selection_changed(self, *_):
        (model, it) = self.__filters_selection.get_selected()
        self._tab_filter_delete.set_sensitive(it is not None)

    def __tab_filter_add_clicked(self, *_):
        field = self._tab_filter_field.child.get_text()
        # FIXME: do something if field is empty
        it = self._tab_filter_op.get_active_iter()
        if it is None:
            return
        op = self.__filter_op_store.get_value(it, 0)
        value = self._tab_filter_value.get_text()
        (model, it) = self.__filters_selection.get_selected()
        it = model.insert_before(it)
        model.set_value(it, 0, filters.FieldFilter(field, op, value))
        self.__update_filter_store_row(it)
        self.__filters_selection.select_iter(it)

    def __tab_filter_delete_clicked(self, *_):
        util.tree_model_delete(self.__filters_selection)

    def __update_filter_store_row(self, it):
        '''Update the text in the self.filter_store row selected by it.'''
        filt = self.__filter_store.get_value(it, 0)
        self.__filter_store.set_value(it, 1, filt.ui_text())

    def __tab_use_start_date_toggled(self, *_):
        self._start_date.set_sensitive(self._tab_use_start_date.get_active())

    def __tab_use_end_date_toggled(self, *_):
        self._end_date.set_sensitive(self._tab_use_end_date.get_active())

    def __window_destroy(self, *_):
        self.emit('destroy')
        return False

    def __window_response(self, unused_widget, response):
        if response in (gtk.RESPONSE_APPLY, gtk.RESPONSE_OK):
            if not self._validate_values():
                return # Don't destroy the dialog
            self.emit('apply')
        if response != gtk.RESPONSE_APPLY:
            self.destroy()
