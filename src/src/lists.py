# Lists of possible field names.
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

__all__ = ('field_names')

# FIXME: maintain an authoritative list
field_names = (
'acct',
'addr',
'arch',
'audit_backlog_limit',
'audit_enabled',
'auid',
'a0',
'a1',
'a2',
'a3',
'banners',
'comm',
'dev',
'egid',
'euid',
'exe',
'exit',
'format',
'fsgid',
'fsuid',
'gid',
'hostname',
'ino',
'inode',
'item',
'items',
'key',
'name',
'node',
'old',
'op',
'path',
'pid',
'ppid',
'printer',
'range',
'res',
'scontext',
'seperms',
'seresults',
'sgid',
'subj',
'success',
'suid',
'syscall',
'tclass',
'tcontext',
'terminal',
'tty',
'type',
'uid',
'uri',
'ver'
)

integer_field_names = (
'audit_backlog_limit',
'audit_enabled',
'ino',
'inode',
'item',
'items',
'pid',
'ppid'
)
