# Main application window.
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
from gettext import gettext as _

import os
import xml.etree.cElementTree as cElementTree

import gobject
import gtk

from dialog_base import DialogBase
import event_source
import format_versions
from list_tab import ListTab
from report_tab import ReportTab
from save_extra import SaveExtra
import settings
from source_dialog import SourceDialog
from tab import Tab
import util

__all__ = ('MainWindow')

class SavingState(object):

    '''State modified while saving configuration to XML.'''

    def __init__(self):
        self.__version = format_versions.initial_version

    def ensure_version(self, version):
        '''Make sure the file format version is at least version.'''
        if format_versions.compare(self.__version, version) < 0:
            self.__version = version

    def apply(self, root_elem):
        '''Apply the state to root_elem.'''
        root_elem.set('format', self.__version)

class MainWindow(DialogBase):

    '''Main window of audit-viewer.'''

    _glade_widget_names = (
        'main_vbox', 'menu_about', 'menu_change_event_source',
        'menu_event_details', 'menu_list_for_cell', 'menu_list_for_column',
        'menu_list_for_row', 'menu_list_for_submenu', 'menu_new_list',
        'menu_new_report', 'menu_open', 'menu_quit', 'menu_refresh',
        'menu_report_on_view', 'menu_save_layout_as', 'menu_tab_close',
        'menu_tab_export', 'menu_tab_in_new_window', 'menu_tab_properties',
        'menu_tab_submenu', 'menu_tab_save_as', 'menu_view_submenu',
        'menu_window_close')

    __num_open_main_windows = 0

    __layout_file_types = ((_('Audit viewer layout'), '.audit-viewer'),)

    def __init__(self, client, source = None):
        DialogBase.__init__(self, 'main_window', None)
        self.source_dialog = None
        self.client = client
        self.event_source = source
        self.__event_error_report_only_one_depth = 0

        self.main_notebook = gtk.Notebook()
        self.main_notebook.set_scrollable(True)
        self.main_notebook.show()
        self.main_vbox.pack_end(self.main_notebook, True, True)

        self.menu_new_list.connect('activate', self.__menu_new_list_activate)
        self.menu_new_report.connect('activate',
                                     self.__menu_new_report_activate)
        self.menu_change_event_source \
            .connect('activate', self.__menu_change_event_source_activate)
        self.menu_open.connect('activate', self.__menu_open_activate)
        self.menu_save_layout_as.connect('activate',
                                         self.__menu_save_layout_as_activate)
        self.menu_window_close.connect('activate',
                                       self.__menu_window_close_activate)
        self.menu_quit.connect('activate', self.__menu_quit_activate)
        self.menu_tab_in_new_window.connect('activate', self.
                                            __menu_tab_in_new_window_activate)
        self.menu_tab_export.connect('activate',
                                     self.__menu_tab_export_activate)
        self.menu_tab_save_as.connect('activate',
                                      self.__menu_tab_save_as_activate)
        self.menu_tab_properties.connect('activate',
                                         self.__menu_tab_properties_activate)
        self.menu_tab_close.connect('activate', self.__menu_tab_close_activate)
        self.menu_report_on_view.connect('activate',
                                         self.__menu_report_on_view_activate)
        self.menu_list_for_cell.connect('activate',
                                        self.__menu_list_for_cell_activate)
        self.menu_list_for_row.connect('activate',
                                       self.__menu_list_for_row_activate)
        self.menu_list_for_column.connect('activate',
                                          self.__menu_list_for_column_activate)
        self.menu_event_details.connect('activate',
                                        self.__menu_event_details_activate)
        self.menu_refresh.connect('activate', self.__menu_refresh_activate)
        self.menu_about.connect('activate', self.__menu_about_activate)
        self.main_notebook.connect('switch-page',
                                   self.__main_notebook_switch_page)
        self.window.connect('destroy', self.__window_destroy)

        self.__tab_objects = {}
        if self.event_source is None:
            self.event_source = event_source.EmptyEventSource()
        MainWindow.__num_open_main_windows += 1

    def setup_initial_window(self, args):
        '''Ensure there is a valid event source and handle command-line args.

        Return True if a valid event source was set up, False otherwise.

        Should be called only in the initial window:  Later windows will inherit
        a valid event source from their "parent" window, and obviously shouldn't
        hanle the same command-line arguments again.

        '''
        try:
            if isinstance(self.event_source, event_source.EmptyEventSource):
                self.__event_error_report_only_one_push()
                if self.client is not None:
                    self.event_source = (event_source.
                                         ClientEventSource(self.client,
                                                           'audit.log'))
                    self.__refresh_all_tabs()
                else:
                    # Only to let the dialog work
                    self.event_source = event_source.FileEventSource('')
                    self.__show_source_dialog()
                    res = self.source_dialog.run()
                    self.source_dialog.destroy()
                    if res != gtk.RESPONSE_OK:
                        self.event_source = None
                        return False
                    # self.__source_dialog_apply() has refreshed all tabs for us
            for filename in args:
                self.__open_file(filename)
            if len(args) == 0:
                self.new_list_tab([])
        finally:
            self.__event_error_report_only_one_pop()
        return True

    def attach_tab(self, tab):
        '''Attach tab to this window's notebook.'''
        self.__tab_objects[tab.widget] = tab
        idx = self.main_notebook.append_page(tab.widget,
                                             gtk.Label(tab.tab_name))
        self.main_notebook.set_tab_reorderable(tab.widget, True)
        self.main_notebook.set_current_page(idx)
        if len(self.__tab_objects) == 1:
            self.menu_tab_submenu.show()
            self.menu_view_submenu.show()

    def new_list_tab(self, filters):
        '''Add a new list tab with the specified filters.'''
        tab = ListTab(filters, self)
        self.attach_tab(tab)

    def new_report_tab(self, filters):
        '''Add a new report tab with the specified filters.'''
        # With configuring = True, the tab will attach itself if the user
        # confirms the dialog.
        ReportTab(filters, self, configuring = True)

    def get_save_path(self, title, types, suggestion = None):
        '''Return a path and an extension to save a file to.

        Return (None, None) if the user has canceled the dialog.  types is a
        sequence of (human readable label, extension) tuples.  Note that
        selecting a types entry is separate from filtering file names, the
        returned path does not necessarily end with the returned extension; use
        the extension only to select the output format.  If suggestion is not
        None, use it an initial file name choice.

        '''
        dlg = gtk.FileChooserDialog(title, self.window,
                                    gtk.FILE_CHOOSER_ACTION_SAVE,
                                    (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                     gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT))
        if suggestion is not None:
            dlg.set_current_name(suggestion)
        self.__add_file_type_filters(dlg, types)
        extra = SaveExtra(types)
        dlg.set_extra_widget(extra.widget)
        while True:
            dlg_res = dlg.run()
            if dlg_res != gtk.RESPONSE_ACCEPT:
                break
            filename = dlg.get_filename()
            if extra.get_auto_extension() and len(types) > 0:
                if len(types) == 1:
                    extension = types[0][1]
                else:
                    extension = extra.get_extension()
                if not filename.endswith(extension):
                    filename += extension
            if not os.path.exists(filename):
                break
            (directory, basename) = os.path.split(filename)
            msg = gtk.MessageDialog(dlg, gtk.DIALOG_DESTROY_WITH_PARENT,
                                    gtk.MESSAGE_QUESTION, gtk.BUTTONS_NONE,
                                    _('A file named "%s" already exists.  Do '
                                      'you want to replace it?')
                                    % util.filename_to_utf8(basename))
            directory = os.path.basename(directory)
            msg.format_secondary_text(_('The file already exists in "%s".  '
                                        'Replacing it will overwrite its '
                                        'contents.')
                                      % util.filename_to_utf8(directory))
            # FIXME? Use the STOCK_SAVE_AS icon for the 'Replace' button.
            msg.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                            _('_Replace'), gtk.RESPONSE_OK)
            res = msg.run()
            msg.destroy()
            if res == gtk.RESPONSE_OK:
                break
        dlg.destroy()
        if dlg_res != gtk.RESPONSE_ACCEPT:
            return (None, None)
        if len(types) == 0:
            extension = None
        elif len(types) == 1:
            extension = types[0][1]
        else:
            extension = extra.get_extension()
        return (filename, extension)

    def read_events(self, filters, wanted_fields, want_other_fields,
                    keep_raw_records):
        '''Read audit events.

        Return a sequence of events, or None on error (without throwing
        exceptions).  Use filters to select events.  Store wanted_fields in
        event.fields, the rest in record.fields if want_other_fields.  Only
        store Record.raw if keep_raw_records.

        In addition, use self.__event_error_report_only_one_depth and
        self.__event_error_reported to avoid repeated error messages when
        refreshing all tabs.

        '''
        try:
            return self.event_source.read_events(filters, wanted_fields,
                                                 want_other_fields,
                                                 keep_raw_records)
        except IOError, e:
            if (self.__event_error_report_only_one_depth == 0 or
                not self.__event_error_reported):
                self.__event_error_reported = True
                self._modal_error_dialog(_('Error reading audit events: %s')
                                         % e.strerror)
            return None

    def _current_tab(self):
        '''Return the Tab object for the current tab.'''
        page_num = self.main_notebook.get_current_page()
        return self.__tab_objects[self.main_notebook.get_nth_page(page_num)]

    @staticmethod
    def __add_file_type_filters(dlg, types):
        '''Add file type filters to dlg.

        types is a sequence of (human readable label, extension) tuples.

        '''
        for (label, extension) in types:
            f = gtk.FileFilter()
            f.set_name(label)
            f.add_pattern('*' + extension)
            dlg.add_filter(f)
        if types:
            f = gtk.FileFilter()
            f.set_name(_('All files'))
            f.add_pattern('*')
            dlg.add_filter(f)

    def __show_source_dialog(self):
        '''Ensure self.source_dialog exists, and show it to the user.'''
        if self.source_dialog is None:
            self.source_dialog = SourceDialog(self.window, self.client)
            self.source_dialog.connect('destroy', self.__source_dialog_destroy)
            self.source_dialog.connect('apply', self.__source_dialog_apply)
            self.source_dialog.load(self)
        else:
            self.source_dialog.present()

    def __source_dialog_destroy(self, *_):
        self.source_dialog = None
        return False

    def __source_dialog_apply(self, *_):
        self.source_dialog.save(self)
        self.__refresh_all_tabs()

    def __close_tab(self, page_num):
        del self.__tab_objects[self.main_notebook.get_nth_page(page_num)]
        self.main_notebook.remove_page(page_num)
        if len(self.__tab_objects) == 0:
            self.menu_tab_submenu.hide()
            self.menu_view_submenu.hide()

    def __handle_saved_config(self, tree):
        '''Handle a saved configuration file.

        Raise SyntaxError if the file is invalid.

        '''
        elem = tree.getroot()
        if elem.tag == 'audit_viewer_config':
            if len(elem) != 1:
                raise SyntaxError(_('Unexpected top element contents'))
            v = util.xml_mandatory_attribute(elem, 'format')
            if format_versions.compare(v, settings.version) > 0:
                raise SyntaxError(_('Unsupported file version %s') % v)
            elem = elem[0]
        # Allow more than one tab in 'tab_configuration' - it doesn't hurt and
        # it might be useful for somebody.
        if elem.tag in ('tab_configuration', 'tab_layout'):
            tabs = []
            for e in elem:
                tab = Tab.load_tab(e, self)
                if tab is not None:
                    tabs.append(tab)
            # If we get here, there were no errors in the file
            if elem.tag == 'tab_layout':
                while len(self.__tab_objects) > 0:
                    self.__close_tab(0)
            for tab in tabs:
                self.attach_tab(tab)
        else:
            raise SyntaxError(_('Unexpected top element'))

    def __open_file(self, filename):
        '''Open filename, handle possible errors.'''
        try:
            t = cElementTree.parse(filename)
            self.__handle_saved_config(t)
        except IOError, e:
            self._modal_error_dialog(_('Error reading %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        e.strerror))
            return
        except SyntaxError, e:
            self._modal_error_dialog(_('Invalid contents of %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        str(e)))
            return

    def __event_error_report_only_one_push(self):
        '''Start a region in which only one error message should be reported.

        The region must end with a call to
        self.__event_error_report_only_one_pop().

        '''
        if self.__event_error_report_only_one_depth == 0:
            self.__event_error_reported = False
        self.__event_error_report_only_one_depth += 1

    def __event_error_report_only_one_pop(self):
        '''End a region in which only one error message should be reported.'''
        self.__event_error_report_only_one_depth -= 1

    def __refresh_all_tabs(self):
        '''Refresh all tabs, taking care to report errors only once.'''
        self.__event_error_report_only_one_push()
        try:
            for page_num in xrange(self.main_notebook.get_n_pages()):
                tab = self.__tab_objects[self.main_notebook
                                         .get_nth_page(page_num)]
                tab.refresh()
        finally:
            self.__event_error_report_only_one_pop()

    def __menu_new_list_activate(self, *_):
        self.new_list_tab([])

    def __menu_new_report_activate(self, *_):
        self.new_report_tab([])

    def __menu_change_event_source_activate(self, *_):
        self.__show_source_dialog()

    def __menu_open_activate(self, *unused):
        dlg = gtk.FileChooserDialog(_('Open...'), self.window,
                                    gtk.FILE_CHOOSER_ACTION_OPEN,
                                    (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                     gtk.STOCK_OPEN, gtk.RESPONSE_ACCEPT))
        self.__add_file_type_filters(dlg, self.__layout_file_types)
        dlg.set_current_folder(settings.configs_path)
        dlg_res = dlg.run()
        filename = dlg.get_filename()
        dlg.destroy()
        if dlg_res != gtk.RESPONSE_ACCEPT:
            return
        self.__open_file(filename)

    def __menu_save_layout_as_activate(self, *unused):
        (filename, unused) = self.get_save_path(_('Save Layout As...'),
                                                self.__layout_file_types)
        if filename is None:
            return
        state = SavingState()
        root_elem = cElementTree.Element('audit_viewer_config')
        elem = cElementTree.Element('tab_layout')
        for page_num in xrange(self.main_notebook.get_n_pages()):
            tab = self.__tab_objects[self.main_notebook.get_nth_page(page_num)]
            elem.append(tab.save_config(state))
        root_elem.append(elem)
        state.apply(root_elem)
        tree = cElementTree.ElementTree(root_elem)
        try:
            util.save_to_file(filename, 'wb',
                              lambda file: tree.write(file, 'utf-8'))
        except (IOError, OSError), e:
            self._modal_error_dialog(_('Error writing to %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        e.strerror))

    def __menu_window_close_activate(self, *_):
        self.destroy()

    def __menu_quit_activate(self, *_):
        gtk.main_quit()

    def __menu_tab_in_new_window_activate(self, *_):
        # Reuse the code to represent tab configuration in XML to copy the
        # configuration of the current tab
        state = SavingState()
        elem = self._current_tab().save_config(state)
        window = MainWindow(self.client, self.event_source)
        tab = Tab.load_tab(elem, window)
        window.attach_tab(tab)

    def __menu_tab_export_activate(self, *_):
        self._current_tab().export()

    def __menu_tab_save_as_activate(self, *unused):
        tab = self._current_tab()
        (filename, unused) = self.get_save_path(_('Save Configuration As...'),
                                                self.__layout_file_types,
                                                tab.tab_name)
        if filename is None:
            return
        state = SavingState()
        root_elem = cElementTree.Element('audit_viewer_config')
        elem = cElementTree.Element('tab_configuration')
        elem.append(tab.save_config(state))
        root_elem.append(elem)
        state.apply(root_elem)
        tree = cElementTree.ElementTree(root_elem)
        try:
            util.save_to_file(filename, 'wb',
                              lambda file: tree.write(file, 'utf-8'))
        except (IOError, OSError), e:
            self._modal_error_dialog(_('Error writing to %s: %s')
                                     % (util.filename_to_utf8(filename),
                                        e.strerror))

    def __menu_tab_properties_activate(self, *_):
        self._current_tab().properties()

    def __menu_tab_close_activate(self, *_):
        self.__close_tab(self.main_notebook.get_current_page())

    def __menu_report_on_view_activate(self, *_):
        self._current_tab().report_on_view()

    def __menu_list_for_cell_activate(self, *_):
        self._current_tab().list_for_cell()

    def __menu_list_for_row_activate(self, *_):
        self._current_tab().list_for_row()

    def __menu_list_for_column_activate(self, *_):
        self._current_tab().list_for_column()

    def __menu_event_details_activate(self, *_):
        self._current_tab().event_details()

    def __menu_refresh_activate(self, *_):
        self._current_tab().refresh()

    def __menu_about_activate(self, *unused):
        dlg = gtk.AboutDialog()
        dlg.set_name(_('Audit Viewer'))
        dlg.set_version(settings.version)
        dlg.set_copyright('Copyright © 2007 Red Hat, Inc.')
        dlg.set_license('''Copyright © 2007 Red Hat, Inc.  All rights reserved.

This copyrighted material is made available to anyone wishing to use, modify,
copy, or redistribute it subject to the terms and conditions of the GNU General
Public License v.2.  This program is distributed in the hope that it will be
useful, but WITHOUT ANY WARRANTY expressed or implied, including the implied
warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.  You should have received a copy of
the GNU General Public License along with this program; if not, write to the
Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
02110-1301, USA.  Any Red Hat trademarks that are incorporated in the source
code or documentation are not subject to the GNU General Public License and may
only be used or replicated with the express permission of Red Hat, Inc.''')
        dlg.set_authors(('Miloslav Trmač <mitr@redhat.com>',))
        s = _('translator-credits')
        if s != 'translator-credits':
            dlg.set_translator_credits(s)
        dlg.run()
        dlg.destroy()

    def __main_notebook_switch_page(self, *_):
        gobject.idle_add(lambda: self._current_tab().tab_select())

    def __window_destroy(self, *_):
        MainWindow.__num_open_main_windows -= 1
        if MainWindow.__num_open_main_windows == 0:
            gtk.main_quit()
