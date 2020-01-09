# List of file format versions.
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

initial_version = '0.1'
# <*_statistic type='numeric_field'>
numeric_field_statistic_version = '0.2'
# <tab type="count_report" display_type="chart">
report_display_type_chart_version = '0.2'

def compare(a, b):
    '''Return an integer with the same sign as (a - b), where a and b are
    versions.

    '''
    # 'DEVEL' in src/settings.py is more than any numeric strings
    if a == 'DEVEL':
        return 1
    elif b == 'DEVEL':
        return -1
    a_ints = [int(v) for v in a.split('.')]
    b_ints = [int(v) for v in b.split('.')]
    if a_ints > b_ints:
        return 1
    if a_ints < b_ints:
        return -1
    return 0
