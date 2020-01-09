# "Event report" tab properties dialog.
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

from statistic import FieldStatistic
from tab_properties import TabProperties
import util

__all__ = ('ReportProperties')

class ReportProperties(TabProperties):

    '''Report properties dialog.'''

    _glade_widget_names = (('report_apply',
                            'report_column_field', 'report_column_field_label',
                            'report_column_group', 'report_column_grouping',
                            'report_properties_notebook', 'report_row_field',
                            'report_row_group', 'report_row_grouping',
                            'report_show_chart', 'report_use_column') +
                           tuple(TabProperties.
                                 _tab_glade_widget_names('report')))

    def __init__(self, parent):
        TabProperties.__init__(self, parent, 'report')
        super(ReportProperties, self).__gobject_init__()

        self.__old_row_field = None
        self._init_field_combo(self.report_row_field)
        # String first is assumed by util.set_combo_option
        self.row_grouping_store = gtk.ListStore(gobject.TYPE_STRING,
                                                gobject.TYPE_PYOBJECT)
        util.connect_and_run(self.report_row_field, 'changed',
                             self.__report_row_field_changed)
        util.connect_and_run(self.report_row_group, 'toggled',
                             self.__report_row_group_toggled)
        self.report_row_grouping.set_model(self.row_grouping_store)
        cell = gtk.CellRendererText()
        self.report_row_grouping.pack_start(cell, True)
        self.report_row_grouping.set_attributes(cell, text = 0)
        util.connect_and_run(self.report_use_column, 'toggled',
                             self.__report_use_column_toggled)
        self.__old_column_field = None
        self._init_field_combo(self.report_column_field)
        self.column_grouping_store = gtk.ListStore(gobject.TYPE_STRING,
                                                   gobject.TYPE_PYOBJECT)
        util.connect_and_run(self.report_column_field, 'changed',
                             self.__report_column_field_changed)
        util.connect_and_run(self.report_column_group, 'toggled',
                             self.__report_column_group_toggled)
        self.report_column_grouping.set_model(self.column_grouping_store)
        cell = gtk.CellRendererText()
        self.report_column_grouping.pack_start(cell, True)
        self.report_column_grouping.set_attributes(cell, text = 0)

    def load(self, tab):
        errors = super(ReportProperties, self).load(tab)

        self.report_show_chart.set_active(tab.show_chart)
        util.set_combo_entry_text(self.report_row_field,
                                  tab.row_statistic.field_name)
        self.__update_row_grouping()
        name = tab.row_statistic.statistic_name()
        self.report_row_group.set_active(name is not None)
        if name is not None:
            util.set_combo_option(self.report_row_grouping, name)
        self.report_use_column.set_active(tab.column_statistic is not None)
        if tab.column_statistic is not None:
            util.set_combo_entry_text(self.report_column_field,
                                      tab.column_statistic.field_name)
            self.__update_column_grouping()
            name = tab.column_statistic.statistic_name()
            self.report_column_group.set_active(name is not None)
            if name is not None:
                util.set_combo_option(self.report_column_grouping, name)

        if tab.configuring:
            self.report_apply.destroy()
        return errors

    def save(self, tab):
        super(ReportProperties, self).save(tab)

        tab.show_chart = self.report_show_chart.get_active()
        # FIXME: handle empty field names
        field = self.report_row_field.child.get_text()
        if not self.report_row_group.get_active():
            tab.row_statistic = FieldStatistic.options(field)[0]
        else:
            it = self.report_row_grouping.get_active_iter()
            assert it is not None
            tab.row_statistic = self.row_grouping_store.get_value(it, 1)
        if self.report_use_column.get_active():
            field = self.report_column_field.child.get_text()
            if not self.report_column_group.get_active():
                tab.column_statistic = FieldStatistic.options(field)[0]
            else:
                it = self.report_column_grouping.get_active_iter()
                assert it is not None
                tab.column_statistic = self.column_grouping_store.get_value(it,
                                                                            1)
        else:
            tab.column_statistic = None

    def show_grouping_tab(self):
        '''Show the grouping tab.'''
        self.report_properties_notebook.set_current_page(1)

    def _validate_get_failure(self):
        r = TabProperties._validate_get_failure(self)
        if r is not None:
            return r

        return None

    def __update_row_grouping(self):
        '''Update self.row_grouping_store for self.report_row_field.'''
        field = self.report_row_field.child.get_text()
        if self.__old_row_field is None or self.__old_row_field != field:
            have_grouping = False
            self.row_grouping_store.clear()
            for s in FieldStatistic.options(field):
                name = s.statistic_name()
                if name is not None:
                    self.row_grouping_store.append((name, s))
                    have_grouping = True
            if not have_grouping:
                self.report_row_group.set_active(False)
            self.report_row_group.set_sensitive(have_grouping)
            self.__old_row_field = field

    def __update_column_grouping(self):
        '''Update self.column_grouping_store for self.report_column_field.'''
        field = self.report_column_field.child.get_text()
        if self.__old_column_field is None or self.__old_column_field != field:
            have_grouping = False
            self.column_grouping_store.clear()
            for s in FieldStatistic.options(field):
                name = s.statistic_name()
                if name is not None:
                    self.column_grouping_store.append((name, s))
                    have_grouping = True
            if not have_grouping:
                self.report_column_group.set_active(False)
            self.report_column_group.set_sensitive(have_grouping)
            self.__old_column_field = field

    def __report_row_field_changed(self, *_):
        self.__update_row_grouping()

    def __report_row_group_toggled(self, *_):
        val = self.report_row_group.get_active()
        self.report_row_grouping.set_sensitive(val)
        if val and self.report_row_grouping.get_active_iter() is None:
            first = self.row_grouping_store.get_iter_first()
            if first:
                self.report_row_grouping.set_active_iter(first)

    def __report_use_column_toggled(self, *_):
        util.set_sensitive_all(self.report_use_column.get_active(),
                               self.report_column_field_label,
                               self.report_column_field,
                               self.report_column_group
                               # self.report_column_grouping excluded
                               )
        # Handles self.report_column_grouping
        self.__report_column_group_toggled()

    def __report_column_field_changed(self, *_):
        self.__update_column_grouping()

    def __report_column_group_toggled(self, *_):
        val = (self.report_use_column.get_active() and
               self.report_column_group.get_active())
        self.report_column_grouping.set_sensitive(val)
        if val and self.report_column_grouping.get_active_iter() is None:
            first = self.column_grouping_store.get_iter_first()
            if first:
                self.report_column_grouping.set_active_iter(first)
