# A generic tab
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
import copy
import xml.etree.cElementTree as cElementTree

from dialog_base import DialogBase
from filters import Filter
import util

__all__ = ('Tab')

class Tab(DialogBase):

    '''A generic tab.'''

    def __init__(self, filters, main_window, toplevel_name):
        DialogBase.__init__(self, toplevel_name, None)

        self._properties_dialog = None
        self.filters = copy.deepcopy(filters)
        self.widget = self.window
        self.main_window = main_window
        self.window = main_window.window
        self.widget.show()

    def event_details(self):
        '''Show details of this event.'''
        raise NotImplementedError

    def export(self):
        '''Export the contents of the tab.'''
        raise NotImplementedError

    def list_for_cell(self):
        '''Show a list for the current cell.'''
        raise NotImplementedError

    def list_for_row(self):
        '''Show a list for the current row.'''
        raise NotImplementedError

    def list_for_column(self):
        '''Show a list for the current column.'''
        raise NotImplementedError

    def properties(self):
        '''Edit configuration of the tab.'''
        self._show_properties_dialog()

    def refresh(self):
        '''Refresh this view.'''
        raise NotImplementedError

    def report_on_view(self):
        '''Create a report for this view.'''
        raise NotImplementedError

    def _load_config(self, elem):
        '''Load configuration from elem.

        Raise SyntaxError if elem is invalid.

        '''
        raise NotImplementedError

    def save_config(self, state):
        '''Return a cElement tree representing configuration of the tab.

        Modify state if necessary.

        '''
        # Use state.ensure_version() when changing the config file format!
        elem = cElementTree.Element('tab', type = self.__xml_tab_name,
                                    tab_name = self.tab_name.decode('utf-8'))

        filters_elem = cElementTree.Element('filters')
        for filt in self.filters:
            filters_elem.append(filt.save_config(state))
        elem.append(filters_elem)

        return elem

    def tab_select(self):
        '''Update the main window when the current tab is selected.'''
        label = self.main_window.menu_tab_submenu.child
        label.set_text_with_mnemonic(_(self._menu_label))

    def set_tab_name(self, new_name):
        '''Change the name of this tab to new_name.'''
        self.main_window.main_notebook.set_tab_label_text(self.widget, new_name)
        self.tab_name = new_name

    __xml_tab_name_map = {}

    @staticmethod
    def _set_xml_tab_name(xml_tab_name, class_):
        '''Set the type field value for class_ to xml_tab_name.'''
        class_.__xml_tab_name = xml_tab_name
        Tab.__xml_tab_name_map[xml_tab_name] = class_

    @staticmethod
    def load_tab(elem, main_window):
        '''Load a tab from elem.

        Return the tab if succesful, None if elem is not a tab.  Raise
        SyntaxError if elem is an invalid tab.

        '''
        if elem.tag != 'tab':
            return None
        tab_type = util.xml_mandatory_attribute(elem, 'type')
        if tab_type not in Tab.__xml_tab_name_map:
            util.xml_raise_unknown_value(elem, 'type')
        filters = []
        for filters_elem in elem:
            if filters_elem.tag != 'filters':
                continue
            for e in filters_elem:
                if e.tag == 'filter':
                    filters.append(Filter.load_filter(e))
        tab = Tab.__xml_tab_name_map[tab_type](filters, main_window,
                                               will_refresh = True)
        tab_name = elem.get('tab_name')
        if tab_name is not None:
            tab.set_tab_name(tab_name)
        tab._load_config(elem)
        return tab

    def _show_properties_dialog(self):
        '''Try to ensure self._properties_dialog exists, and show it to the
        user.

        Note that this may fail if the dialog does not support some filters and
        the user decides to cancel.  self._properties_dialog will be None in
        that case.

        '''
        if self._properties_dialog is None:
            self._properties_dialog = self._properties_class(self.main_window.
                                                             window)
            self._properties_dialog.connect('destroy',
                                            self.__properties_dialog_destroy)
            self._properties_dialog.connect('apply',
                                            self._properties_dialog_apply)
            if self._properties_dialog.try_loading(self) == False:
                self._properties_dialog.destroy()
                assert self._properties_dialog is None
        else:
            self._properties_dialog.present()

    def __properties_dialog_destroy(self, *_):
        self._properties_dialog = None
        return False

    def _properties_dialog_apply(self, *_):
        '''Apply the modifications in properties dialog to self.'''
        self._properties_dialog.save(self)
        self.refresh()
