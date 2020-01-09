# Common utilities.
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

import datetime
import errno
import locale
import os
import stat
import tempfile

import audit
import gtk

__all__ = ('connect_and_run',
           'filename_to_utf8',
           'html_escape',
           'is_row_separator',
           'modal_error_dialog', 'msgtype_string',
           'set_sensitive_all', 'set_combo_entry_text', 'set_combo_option',
           'save_to_file',
           'tree_model_delete', 'tree_model_move_down', 'tree_model_move_up',
           'tree_view_remove_all_columns',
           'week_day', 'week_length',
           'xml_raise_invalid_value',
           'xml_raise_unknown_value',
           'xml_mandatory_attribute')

 # GUI utilities

def connect_and_run(widget, signal, handler):
    '''Setup a signal for widget, and call the handler.'''
    widget.connect(signal, handler)
    handler()

def filename_to_utf8(filename):
    '''Return filename converted from local encoding to UTF-8.'''
    utf8 = filename.decode(locale.getpreferredencoding(), 'replace')
    return utf8.encode('utf-8')

def is_row_separator(model, it):
    '''Returns True if it represents a separator row.'''
    return model.get_value(it, 0) == ''

def modal_error_dialog(parent, msg):
    '''Show a modal error dialog.'''
    dlg = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, msg)
    dlg.run()
    dlg.destroy()

def set_sensitive_all(sensitive, *widgets):
    '''Set sensitivity of widgets to the specified value.'''
    for w in widgets:
        w.set_sensitive(sensitive)

def set_combo_entry_text(combo, string):
    '''Set combo value to string.

    Assumes the model has a single gobject.TYPE_STRING value.

    '''
    model = combo.get_model()
    it = model.get_iter_first()
    while it is not None:
        if model.get_value(it, 0) == string:
            combo.set_active_iter(it)
            break
        it = model.iter_next(it)
    else:
        combo.set_active(-1)
        combo.child.set_text(string)

def set_combo_option(combo, string):
    '''Set combo value to string.

    If string is not found, unset the value.  Assumes the model has a single
    gobject.TYPE_STRING value.

    '''
    model = combo.get_model()
    it = model.get_iter_first()
    while it is not None:
        if model.get_value(it, 0) == string:
            combo.set_active_iter(it)
            break
        it = model.iter_next(it)
    else:
        combo.set_active(-1)

def tree_model_delete(selection):
    '''Remove the item selected by selection in a gtk.TreeModel.'''
    (model, it) = selection.get_selected()
    if it is not None:
        # FIXME? confirm
        model.remove(it)

def tree_model_move_down(selection):
    '''Try to move the item selected by selection in a gtk.TreeModel down.'''
    (model, it) = selection.get_selected()
    if it is None:
        return
    it2 = model.iter_next(it)
    if it2 is not None:
        model.move_after(it, it2)

def tree_model_move_up(selection):
    '''Try to move the item selected by selection in a gtk.TreeModel up.'''
    (model, it) = selection.get_selected()
    if it is None:
        return
    path = model.get_path(it)
    if path != model.get_path(model.get_iter_first()):
        # Ugly - but pygtk doesn't seem to support gtk_tree_path_prev()
        model.move_before(it, model.get_iter((path[0] - 1,)))

def tree_view_remove_all_columns(tree_view):
    for c in tree_view.get_columns():
        tree_view.remove_column(c)

 # Audit string parsing

def msgtype_string(msgtype):
    '''Return a string representing msgtype.'''
    s = audit.audit_msg_type_to_name(msgtype)
    if s is None:
        s = str(msgtype)
    return s

 # Localized week handling

# Defaults
_week_first_day_ordinal = datetime.date(1997, 11, 30).toordinal()

# Number of days in a week
week_length = 7

def week_day(date):
    '''Return a 0-based number of day of week for date.'''
    # -1 % 7 == 6, so this works even if date < _week_first_day_ordinal
    return (date.toordinal() - _week_first_day_ordinal) % week_length

def _read_week_data_from_glibc():
    '''Read locale-specific week information from glibc, if supported.'''
    global _week_first_day_ordinal, week_length

    try:
        import subprocess
        proc = subprocess.Popen(['locale', 'week-ndays', 'week-1stday'],
                                stdout = subprocess.PIPE, close_fds = True)
        try:
            lines = proc.stdout.readlines()
        finally:
            proc.wait()
        if len(lines) == 2:
            try:
                week_length = int(lines[0])
                assert week_length > 0
            except ValueError:
                pass
            try:
                l = lines[1]
                d = datetime.date(int(l[0:4]), int(l[4:6]), int(l[6:8]))
                _week_first_day_ordinal = d.toordinal()
            except ValueError:
                pass
    except OSError:
        pass

_read_week_data_from_glibc()
del _read_week_data_from_glibc

 # Atomaically saving to files

def save_to_file(path, mode, fn):
    '''Run fn(file) and save the file to path (open with mode).

    Raise IOError, OSError.

    '''
    try:
        st_orig = os.stat(path)
    except OSError, e:
        if e.errno != errno.ENOENT:
            raise
        st_orig = None
    (dirname, filename) = os.path.split(path)
    (fd, tmp_path) = tempfile.mkstemp(prefix = filename, dir = dirname)
    unlink_tmp_path_on_error = True
    try:
        f = os.fdopen(fd, mode)
        try:
            fn(f)
        finally:
            f.close()
        if st_orig is not None:
            mode = st_orig.st_mode & (stat.S_IRWXU | stat.S_IRWXG
                                      | stat.S_IRWXO)
        else:
            orig_umask = os.umask(0)
            os.umask(orig_umask)
            mode = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP
                    | stat.S_IROTH | stat.S_IWOTH) & ~orig_umask
        os.chmod(tmp_path, mode)
        if st_orig is not None:
            backup_path = path + '~'
            try:
                os.unlink(backup_path)
            except OSError:
                pass
            os.link(path, backup_path)
        os.rename(tmp_path, path)
        unlink_tmp_path_on_error = False
    finally:
        if unlink_tmp_path_on_error: # There must have been an exception
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


 # XML handling

def html_escape(s):
    '''Return s, HTML-escaped enough to appear outside of tags.'''
    return s.replace('&', '&amp;').replace('<', '&lt;')

def xml_raise_invalid_value(elem, attr):
    '''Raise SyntaxError reporting that value of attr in elem is invalid.'''
    raise SyntaxError(_('Invalid <%s %s> value %s')
                      % (elem.tag, attr, elem.get(attr)))

def xml_raise_unknown_value(elem, attr):
    '''Raise SyntaxError reporting that value of attr in elem is unknown.'''
    raise SyntaxError(_('Unknown <%s %s> value %s')
                      % (elem.tag, attr, elem.get(attr)))

def xml_mandatory_attribute(elem, attr):
    '''Return value of attribute attr in elem, or raise SyntaxError.'''
    v = elem.get(attr)
    if v is None:
        raise SyntaxError(_('Attribute %s missing in <%s>') % (attr, elem.tag))
    return v
