# A "report" tab
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

import csv
import cStringIO

import gobject
import gtk
import gtkextra
import pychart.area
import pychart.axis
import pychart.bar_plot
import pychart.canvas
import pychart.category_coord
import pychart.fill_style
import pychart.legend
import pychart.theme
import rsvg

import filters
import format_versions
from statistic import FieldStatistic
from report_properties import ReportProperties
from tab import Tab
import util

__all__ = ('ReportTab')

pychart.theme.use_color = True
pychart.theme.reinitialize()

def N_(s): return s

class ReportTab(Tab):

    '''A "report" tab.'''

    _glade_widget_names = ('report_chart_error', 'report_scrolled_window')

    _menu_label = N_('_Report')
    _properties_class = ReportProperties

    __report_number = 1
    def __init__(self, filters, main_window, will_refresh = False,
                 configuring = False):
        Tab.__init__(self, filters, main_window, 'report_vbox')
        self.configuring = configuring
        if configuring:
            will_refresh = True
        self.__old_show_chart = False
        self.show_chart = False
        self.__create_report_sheet()

        self.row_statistic = FieldStatistic.options('date')[0]
        self.column_statistic = FieldStatistic.options('uid')[0]

        self.tab_name = _('Report %d') % ReportTab.__report_number
        ReportTab.__report_number += 1

        self.counts = {} # row range or (row range, column range) => event count
        self.row_ranges = ()
        self.column_ranges = ()
        self.__refresh_dont_read_events = will_refresh
        self.refresh()
        self.__refresh_dont_read_events = False

        if self.configuring:
            self._show_properties_dialog()
            if self._properties_dialog is None:
                self.destroy() # ... And let the garbage collector drop this tab
            self._properties_dialog.show_grouping_tab()

    def export(self):
        types = ((_('HTML'), '.html'), (_('CSV'), '.csv'))
        (filename, extension) = self.main_window.get_save_path(_('Export...'),
                                                               types,
                                                               self.tab_name)
        if filename is None:
            return
        try:
            if extension == '.csv':
                self.__export_csv(filename)
            else:
                assert extension == '.html', ('Unexpected export type %s'
                                              % extension)
                self.__export_html(filename)
        except (IOError, OSError), e:
            self._modal_error_dialog(_('Error writing to %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        e.strerror))

    def list_for_cell(self):
        (row, column) = self.report_sheet.get_active_cell()
        f = self.filters[:]
        row_failed = False
        try:
            f2 = self.row_ranges[row].get_filters()
        except ValueError:
            row_failed = True
        else:
            filters.add_filters(f, f2)
        if self.column_statistic is not None:
            try:
                f2 = self.column_ranges[column].get_filters()
            except ValueError:
                if not row_failed:
                    self._modal_error_dialog(_('Listing events for this column '
                                               'is not supported.'))
                else:
                    self._modal_error_dialog(_('Listing events for this cell '
                                               'is not supported.'))
                return
            filters.add_filters(f, f2)
        if row_failed:
            self._modal_error_dialog(_('Listing events for this row is not '
                                       'supported.'))
            return
        self.main_window.new_list_tab(f)

    def list_for_row(self):
        (row, unused) = self.report_sheet.get_active_cell()
        f = self.filters[:]
        try:
            f2 = self.row_ranges[row].get_filters()
        except ValueError:
            self._modal_error_dialog(_('Listing events for this row is not '
                                       'supported.'))
            return
        filters.add_filters(f, f2)
        self.main_window.new_list_tab(f)

    def list_for_column(self):
        (unused, column) = self.report_sheet.get_active_cell()
        f = self.filters[:]
        try:
            f2 = self.column_ranges[column].get_filters()
        except ValueError:
            self._modal_error_dialog(_('Listing events for this column is not '
                                       'supported.'))
            return
        filters.add_filters(f, f2)
        self.main_window.new_list_tab(f)

    def refresh(self):
        self.__refresh_main_menu()

        event_sequence = self.__refresh_get_event_sequence()
        if event_sequence is None:
            return
        self.__refresh_gather_statistics(event_sequence)

        if self.__old_show_chart != self.show_chart:
            self.report_scrolled_window.child.destroy()
            if self.show_chart:
                self.__create_report_chart()
            else:
                self.__create_report_sheet()
            self.__old_show_chart = self.show_chart
        if self.show_chart:
            self.__repaint_chart(force = True)
        else:
            self.__refresh_report_sheet()

    def save_config(self, state):
        elem = super(ReportTab, self).save_config(state)

        elem.append(self.row_statistic.save_config(state, 'row_statistic'))
        if self.column_statistic is not None:
            elem.append(self.column_statistic.save_config(state,
                                                          'column_statistic'))
        if self.show_chart:
            state.ensure_version(format_versions.
                                 report_display_type_chart_version)
            elem.set('display_type', 'chart')
        # else display_type='table' is implied

        return elem

    def tab_select(self):
        Tab.tab_select(self)
        self.main_window.menu_report_on_view.hide()
        self.main_window.menu_list_for_submenu.show()
        self.main_window.menu_event_details.hide()

    def _load_config(self, elem):
        self.column_statistic = None
        for e in elem:
            if e.tag == 'row_statistic':
                self.row_statistic = FieldStatistic.load_statistic(e)
            elif e.tag == 'column_statistic':
                self.column_statistic = FieldStatistic.load_statistic(e)
        v = elem.get('display_type')
        if v is None or v == 'table':
            self.show_chart = False
        elif v == 'chart':
            self.show_chart = True
        else:
            util.xml_raise_unknown_value(elem, 'display_type')
        self.refresh()

    def _properties_dialog_apply(self, *args):
        super(ReportTab, self)._properties_dialog_apply(self, *args)
        if self.configuring:
            self.main_window.attach_tab(self)
            # The current version does not have Apply, so the dialog should
            # close anyway.  This way we are absolutely sure the "next" dialog
            # will have Apply.
            self._properties_dialog.destroy()
            self.configuring = False

    def __export_csv(self, filename):
        '''Export data to filename in CSV.

        Raise IOError, OSError.

        '''
        def write_to_file(file):
            out = csv.writer(file)
            if self.column_statistic is None:
                data = ['', _('Count')]
            else:
                data = [''] + [rng.get_csv_label()
                               for rng in self.column_ranges]
            out.writerow(data)
            for row_range in self.row_ranges:
                data[0] = row_range.get_csv_label()
                if self.column_statistic is None:
                    data[1] = self.counts[row_range]
                else:
                    for (c, column_range) in enumerate(self.column_ranges):
                        value = self.counts.get((row_range, column_range), 0)
                        data[c + 1] = '%s' % value
                out.writerow(data)

        util.save_to_file(filename, 'wb', write_to_file)

    def __export_html(self, filename):
        '''Export data to filename in HTML.

        Raise IOError, OSError.

        '''
        def write_to_file(f):
            H = util.html_escape
            f.write('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" '
                    '"http://www.w3.org/TR/html4/strict.dtd">\n'
                    '<HTML>\n')
            f.write('<HEAD><TITLE>%s</TITLE>\n' % H(self.tab_name))
            f.write('<META http-equiv="Content-Type" '
                    'content="text/html; charset=UTF-8"></HEAD>\n')
            f.write('<BODY><H1>%s</H1>\n' % H(self.tab_name))
            if self.column_statistic is None:
                cols = 1
            else:
                cols = len(self.column_ranges)
            f.write('<TABLE border><COLGROUP span="1"><COLGROUP span="%s">'
                    '<THEAD>\n' % cols)
            f.write('<TR><TH scope="col"></TH>')
            if self.column_statistic is None:
                f.write('<TH scope="col">%s</TH>' % H(_('Count')))
            else:
                for rng in self.column_ranges:
                    f.write('<TH scope="col">%s</TH>' % H(rng.get_label()))
            f.write('</TR>\n'
                    '</THEAD><TBODY>\n')
            for row_range in self.row_ranges:
                f.write('<TR><TH scope="row">%s</TH>' %
                        H(row_range.get_label()))
                if self.column_statistic is None:
                    f.write('<TD>%s</TD>' % self.counts[row_range])
                else:
                    for column_range in self.column_ranges:
                        value = self.counts.get((row_range, column_range), 0)
                        f.write('<TD>%s</TD>' % value)
                f.write('</TR>\n')
            f.write('</TBODY></TABLE></BODY></HTML>\n')

        util.save_to_file(filename, 'w', write_to_file)

    def __report_chart_size_allocate(self, *_):
        self.__repaint_chart()

    def __create_report_chart(self):
        self.__report_chart_last_allocation = (0, 0)
        self.report_chart = gtk.Image()
        self.report_chart.connect('size-allocate',
                                  self.__report_chart_size_allocate)
        self.report_chart.show()
        self.report_scrolled_window.add_with_viewport(self.report_chart)

    def __create_report_sheet(self):
        '''Create self.report_sheet and show it.'''
        self.report_sheet = gtkextra.Sheet(0, 0, '', 1)
        self.report_sheet.show()
        self.report_scrolled_window.add(self.report_sheet)
        self.report_chart_error.hide()
        self.report_scrolled_window.show()

    def __repaint_chart(self, force = False):
        '''Paint self.report_chart.

        If force, do it even if the size has not changed.

        '''
        allocation = self.report_chart.allocation
        # Don't bother while creating the dialog or if the window is way too
        # small
        if allocation.width < 10 or allocation.height < 10:
            return
        if (not force and
            self.__report_chart_last_allocation == (allocation.width,
                                                    allocation.height)):
            return # Nothing to do

        if self.column_statistic is None:
            data = [(row_range.get_label(), self.counts[row_range])
                    for row_range in self.row_ranges]
        else:
            data = []
            for row_range in self.row_ranges:
                row = ([row_range.get_label()] +
                       [self.counts.get((row_range, column_range))
                        for column_range in self.column_ranges])
                data.append(row)
        if len(data) == 0:
            return
        # The chart painting can take extremely long with large data sets,
        # crudely avoid that.  The computed expression is the number of bars
        # in the chart.
        if len(data) * (len(data[0]) - 1) > 100:
            self.report_scrolled_window.hide()
            self.report_chart_error.show()
            return
        self.report_chart_error.hide()
        self.report_scrolled_window.show()

        # area size does not include axes and other areas.  Guess how much these
        # take...
        if self.column_statistic is None:
            width = allocation.width - 100
        else: # Include space for legend
            width = allocation.width - 200
        height = allocation.height - 40
        # Make sure the chart is not too small.  162/100 is roughly the golden
        # ratio.
        width = max(width, 162)
        height = max(height, 100)

        if self.column_statistic is None:
            legend = None
        else:
            legend = pychart.legend.T()
        area = pychart.area.T(size = (width, height),
                              x_axis = pychart.axis.X(label =
                                                      self.row_statistic.
                                                      field_name),
                              y_axis = pychart.axis.Y(format = '%d', label=''),
                              legend = legend,
                              x_coord = pychart.category_coord.T(data, 0),
                              bg_style = pychart.fill_style.Plain())
        # Always use the first fill styles from the list, the default fill_style
        # iterates all over the list and changes styles on each refresh
        if self.column_statistic is None:
            plot = pychart.bar_plot.T(data = data,
                                      fill_style = pychart.fill_style.
                                      color_standards[0])
            area.add_plot(plot)
        else:
            fill_it = pychart.fill_style.color_standards.iterate()
            for (col, column_range) in enumerate(self.column_ranges):
                plot = pychart.bar_plot.T(data = data, hcol = col + 1,
                                          fill_style = fill_it.next(),
                                          label = column_range.get_label(),
                                          cluster =
                                          (col, len(self.column_ranges)))
                area.add_plot(plot)
        f = cStringIO.StringIO()
        canvas = pychart.canvas.init(f, 'svg')
        area.draw(canvas)
        canvas.close()
        svg = f.getvalue()
        f.close()
        h = rsvg.Handle(data = svg)
        self.report_chart.set_from_pixbuf(h.get_pixbuf())

        self.__report_chart_last_allocation = (allocation.width,
                                               allocation.height)


    def __resize_sheet(self, rows, cols):
        '''Resize self.report_sheet to (rows, cols).'''

        r = self.report_sheet.get_rows_count()
        if r < rows:
            self.report_sheet.insert_rows(r, rows - r)
        elif r > rows:
            self.report_sheet.delete_rows(rows, r - rows)
        c = self.report_sheet.get_columns_count()
        if c < cols:
            self.report_sheet.insert_columns(c, cols - c)
        elif c > cols:
            self.report_sheet.delete_columns(cols, c - cols)

    def __refresh_main_menu(self):
        '''Update visibility "View->List for..." menu items.'''
        if self.show_chart:
            self.main_window.menu_list_for_submenu.hide()
        else:
            self.main_window.menu_list_for_submenu.show()
            if self.column_statistic is None:
                self.main_window.menu_list_for_cell.hide()
                self.main_window.menu_list_for_column.hide()
            else:
                self.main_window.menu_list_for_cell.show()
                self.main_window.menu_list_for_column.show()

    def __refresh_get_event_sequence(self):
        '''Return an event sequence (as if from self.main_window.read_events()).

        Return None on error.

        '''
        if self.__refresh_dont_read_events:
            return ()
        wanted_fields = set()
        self.row_statistic.add_wanted_fields(wanted_fields)
        if self.column_statistic is not None:
            self.column_statistic.add_wanted_fields(wanted_fields)
        return self.main_window.read_events(self.filters, wanted_fields, False,
                                            False)

    def __refresh_gather_statistics(self, event_sequence):
        '''Compute statistics data from event_sequence.'''
        self.counts.clear()
        self.row_statistic.clear()
        if self.column_statistic is None:
            for event in event_sequence:
                rng = self.row_statistic.get_range(event)
                self.counts[rng] = self.counts.get(rng, 0) + 1
        else:
            self.column_statistic.clear()
            for event in event_sequence:
                row_range = self.row_statistic.get_range(event)
                column_range = self.column_statistic.get_range(event)
                key = (row_range, column_range)
                self.counts[key] = self.counts.get(key, 0) + 1
            self.column_ranges = self.column_statistic.ordered_ranges()
        self.row_ranges = self.row_statistic.ordered_ranges()

    def __refresh_report_sheet(self):
        '''Update self.report_sheet from statistics data.'''
        self.report_sheet.freeze()
        try:
            rows = len(self.row_ranges)
            if self.column_statistic is None:
                cols = 1
            else:
                cols = len(self.column_ranges)
            self.__resize_sheet(rows, cols)

            for (row, rng) in enumerate(self.row_ranges):
                self.report_sheet.row_button_add_label(row, rng.get_label())
            if self.column_statistic is None:
                self.report_sheet.column_button_add_label(0, _('Count'))
            else:
                for (column, rng) in enumerate(self.column_ranges):
                    self.report_sheet.column_button_add_label(column,
                                                              rng.get_label())

            for (row, row_range) in enumerate(self.row_ranges):
                if self.column_statistic is None:
                    self.report_sheet.set_cell(row, 0, gtk.JUSTIFY_RIGHT,
                                               '%s' % self.counts[row_range])
                else:
                    for (column, column_range) in enumerate(self.column_ranges):
                        value = self.counts.get((row_range, column_range), 0)
                        self.report_sheet.set_cell(row, column,
                                                   gtk.JUSTIFY_RIGHT,
                                                   '%s' % value)
        finally:
            self.report_sheet.thaw()

ReportTab._set_xml_tab_name('count_report', ReportTab)
