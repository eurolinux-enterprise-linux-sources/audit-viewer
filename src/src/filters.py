# auparse search filter representation
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
from gettext import gettext as _, ngettext
import time
import xml.etree.cElementTree as cElementTree

import auparse

import event_source
import util

__all__ = ('ExpressionFilter',
           'FieldFilter', 'Filter',
           'MinutesAgoFilter',
           'NowFilter',
           'ThisMonthStartFilter', 'ThisWeekStartFilter', 'ThisYearStartFilter',
           'TimestampFilter', 'TodayFilter',
           'YesterdayFilter',
           'merge_filters',)

def N_(s): return s

class Filter(object):

    '''An ausearch filter.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def apply(self, parser, date):
        '''Add itself (with auparse.AUSEARCH_RULE_AND) to parser.

        Use date as "current date" in relative time filters.

        '''
        raise NotImplementedError

    def _load_config(self, elem):
        '''Load filter-specific configuration from elem.

        Raise SyntaxError if elem is invalid.

        '''
        pass

    def save_config(self, unused_state):
        '''Return a cElement tree representing configuration of the filter.

        Modify state if necessary.

        '''
        # Use state.ensure_version when changing the config file format!
        return cElementTree.Element('filter', type = self.__xml_filter_name)

    def ui_text(self):
        '''Return an user-readable description of the filter.'''
        raise NotImplementedError

    def __eq__(self, filt):
        return type(self) is type(filt)

    def __ne__(self, filt):
        return not self.__eq__(filt)

    __xml_filter_name_map = {}

    @staticmethod
    def _set_xml_filter_name(xml_filter_name, class_):
        '''Set the type field value for class_ to xml_filter_name.'''
        class_.__xml_filter_name = xml_filter_name
        Filter.__xml_filter_name_map[xml_filter_name] = class_

    @staticmethod
    def load_filter(elem):
        '''Load a filter from elem.

        Return the filter if succesful.  Raise SyntaxError if elem is invalid.

        '''
        type_ = util.xml_mandatory_attribute(elem, 'type')
        if type_ not in Filter.__xml_filter_name_map:
            util.xml_raise_unknown_value(elem, 'type')
        filt = Filter.__xml_filter_name_map[type_]()
        filt._load_config(elem)
        return filt

class _ComparisonFilter(Filter):

    '''A filter that uses a comparison operator.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ('op',)

    def __init__(self, op = None):
        # Default value assumed to be overwritten by _load_config
        self.op = op

    def _load_config(self, elem):
        self.op = util.xml_mandatory_attribute(elem, 'op')

    def save_config(self, state):
        elem = super(_ComparisonFilter, self).save_config(state)
        elem.set('op', self.op.decode('utf-8'))
        return elem

    def __eq__(self, filt):
        return Filter.__eq__(self, filt) and self.op == filt.op


class FieldFilter(_ComparisonFilter):

    '''A field value filter.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ('field', 'value')

    def __init__(self, field = None, op = None, value = None):
        '''Create a field filter.

        Note that 'value' is the interpreted, not raw, value.

        '''
        # Default values assumed to be overwritten by _load_config
        _ComparisonFilter.__init__(self, op)
        self.field = field
        self.value = value

    def apply(self, parser, unused_date):
        parser.search_add_interpreted_item(self.field, self.op, self.value,
                                           auparse.AUSEARCH_RULE_AND)

    def save_config(self, state):
        elem = super(FieldFilter, self).save_config(state)
        elem.set('field', self.field.decode('utf-8'))
        elem.set('value', self.value.decode('utf-8'))
        return elem

    def ui_text(self):
        return '%s %s %s' % (self.field, self.op, self.value)

    def _load_config(self, elem):
        _ComparisonFilter._load_config(self, elem)
        self.field = util.xml_mandatory_attribute(elem, 'field')
        self.value = util.xml_mandatory_attribute(elem, 'value')

    def __eq__(self, filt):
        return (_ComparisonFilter.__eq__(self, filt)
                and self.field == filt.field and self.value == filt.value)

Filter._set_xml_filter_name('field', FieldFilter)

class TimestampFilter(_ComparisonFilter):

    '''An event timestamp filter.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ('ms', 'sec')

    def __init__(self, op = None, sec = None, ms = None):
        # Default values assumed to be overwritten by _load_config
        _ComparisonFilter.__init__(self, op)
        self.sec = sec
        self.ms = ms

    def ts_cmp(self, filt):
        '''Compare timestamps.  Return a value as if from cmp(self, filt).'''
        r = cmp(self.sec, filt.sec)
        if r == 0:
            r = cmp(self.ms, filt.ms)
        return r

    def apply(self, parser, unused_date):
        parser.search_add_timestamp_item(self.op, self.sec, self.ms,
                                         auparse.AUSEARCH_RULE_AND)

    def save_config(self, state):
        elem = super(TimestampFilter, self).save_config(state)
        elem.set('sec', '%d' % self.sec)
        elem.set('ms', '%d' % self.ms)
        return elem

    def ui_text(self):
        tm = time.localtime(self.sec)
        return (_('date %s %s.%03d')
                % (self.op, time.strftime(_('%x %H:%M:%S'), tm), self.ms))

    def _load_config(self, elem):
        _ComparisonFilter._load_config(self, elem)
        v = util.xml_mandatory_attribute(elem, 'sec')
        try:
            self.sec = int(v)
        except ValueError:
            util.xml_raise_invalid_value(elem, 'sec')
        v = util.xml_mandatory_attribute(elem, 'ms')
        try:
            val = int(v)
        except ValueError:
            util.xml_raise_invalid_value(elem, 'ms')
        if val < 0 or val >= 1000:
            util.xml_raise_invalid_value(elem, 'ms')
        self.ms = val

    def __eq__(self, filt):
        return (_ComparisonFilter.__eq__(self, filt) and self.ms == filt.ms
                and self.sec == filt.sec)

Filter._set_xml_filter_name('timestamp', TimestampFilter)

class _DateWithChangesFilter(_ComparisonFilter):

    '''An event timestamp filter, comparing with current date after some
    modification.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        '''Return date after additional modifications.'''
        raise NotImplementedError

    def apply(self, parser, date):
        date = self._change_fn(date)
        parser.search_add_timestamp_item(self.op, int(date.strftime('%s')),
                                         date.microsecond / 1000,
                                         auparse.AUSEARCH_RULE_AND)

class NowFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with "current time".'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def ui_text(self):
        return _('date %s now') % self.op

    def _change_fn(self, date):
        return date

Filter._set_xml_filter_name('now', NowFilter)

class MinutesAgoFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with minutes before
    "current time".'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ('minutes',)

    def __init__(self, op = None, minutes = None):
        # Default values assumed to be overwritten by _load_config
        _DateWithChangesFilter.__init__(self, op)
        self.minutes = minutes

    def save_config(self, state):
        elem = super(MinutesAgoFilter, self).save_config(state)
        elem.set('minutes', '%d' % self.minutes)
        return elem

    def ui_text(self):
        return (ngettext('date %s %d minute ago', 'date %s %d minutes ago',
                         self.minutes) % (self.op, self.minutes))

    def _load_config(self, elem):
        _DateWithChangesFilter._load_config(self, elem)
        v = util.xml_mandatory_attribute(elem, 'minutes')
        try:
            self.minutes = int(v)
        except ValueError:
            util.xml_raise_invalid_value(elem, 'minutes')

    def _change_fn(self, date):
        return date + datetime.timedelta(minutes = -self.minutes)

    def __eq__(self, filt):
        return (_DateWithChangesFilter.__eq__(self, filt)
                and self.minutes == filt.minutes)

Filter._set_xml_filter_name('minutes_ago', MinutesAgoFilter)

class TodayFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with today 00:00.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        return date.replace(hour = 0, minute = 0, second = 0, microsecond = 0)

    def ui_text(self):
        return _('date %s today 00:00') % self.op

Filter._set_xml_filter_name('today', TodayFilter)

class YesterdayFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with yesterday 00:00.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        date = date.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        return date + datetime.timedelta(days = -1)

    def ui_text(self):
        return _('date %s yesterday 00:00') % self.op

Filter._set_xml_filter_name('yesterday', YesterdayFilter)

class ThisWeekStartFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with this week's first day 00:00.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        date = date.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        return date + datetime.timedelta(days = -util.week_day(date))

    def ui_text(self):
        return _('date %s start of this week') % self.op

Filter._set_xml_filter_name('this_week_start', ThisWeekStartFilter)

class ThisMonthStartFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with this month's start 00:00.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        return date.replace(day = 1, hour = 0, minute = 0, second = 0,
                            microsecond = 0)

    def ui_text(self):
        return _('date %s start of this month') % self.op

Filter._set_xml_filter_name('this_month_start', ThisMonthStartFilter)

class ThisYearStartFilter(_DateWithChangesFilter):

    '''An event timestamp filter, comparing with this year's start 00:00.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ()

    def _change_fn(self, date):
        return date.replace(day = 1, hour = 0, minute = 0, second = 0,
                            microsecond = 0)

    def ui_text(self):
        return _('date %s start of this year') % self.op

Filter._set_xml_filter_name('this_year_start', ThisYearStartFilter)

class ExpressionFilter(Filter):

    '''An expression filter.'''

    # Used to make sure __eq__() doesn't miss anything.  The space savings, if
    # any, are not really important.
    __slots__ = ('expression',)

    def __init__(self, expression = None):
        # Default values assumed to be overwritten by _load_config
        Filter.__init__(self)
        self.expression = expression

    def apply(self, parser, unused_date):
        parser.search_add_expression(self.expression,
                                     auparse.AUSEARCH_RULE_AND)

    def _load_config(self, elem):
        self.expression = util.xml_mandatory_attribute(elem, 'expression')
        msg = event_source.check_expression(self.expression)
        if msg is not None:
            raise SyntaxError(msg)

    def save_config(self, state):
        elem = super(ExpressionFilter, self).save_config(state)
        elem.set('expression', self.expression.decode('utf-8'))
        return elem

    def ui_text(self):
        '''Return an user-readable description of the filter.'''
        return '(%s)' % self.expression

    def __eq__(self, filt):
        return (Filter.__eq__(self, filt)
                and self.expression == filt.expression)

Filter._set_xml_filter_name('expression', ExpressionFilter)

def add_filters(filters, additional):
    '''Append filters from additional to filters.

    Try to avoid duplicate and redundant filters.

    '''
    # As a special case, handle TimestampFilter instances with '>=', '<' and
    # '=' (in "additional" only); ignore the other possible operators because
    # they cannot be created from the GUI.  For the same reason, assume there
    # is always at most one TimestampFilter for a signle operator in "filters"
    ts_ge_filt = None
    ts_lt_filt = None
    for filt in filters:
        if type(filt) is not TimestampFilter:
            continue
        if filt.op == '>=':
            ts_ge_filt = filt
        elif filt.op == '<':
            ts_lt_filt = filt
    for filt in additional:
        if type(filt) is TimestampFilter:
            if filt.op == '>=':
                if ts_ge_filt is None or filt.ts_cmp(ts_ge_filt) >= 0:
                    if ts_ge_filt is not None:
                        filters.remove(ts_ge_filt)
                    filters.append(filt)
                    ts_ge_filt = filt
                continue
            elif filt.op == '<':
                if ts_lt_filt is None or filt.ts_cmp(ts_lt_filt) < 0:
                    if ts_lt_filt is not None:
                        filters.remove(ts_lt_filt)
                    filters.append(filt)
                    ts_lt_filt = filt
                continue
            elif filt.op == '=':
                if ts_ge_filt is not None and filt.ts_cmp(ts_ge_filt) >= 0:
                    filters.remove(ts_ge_filt)
                    ts_ge_filt = None
                if ts_lt_filt is not None and filt.ts_cmp(ts_lt_filt) < 0:
                    filters.remove(ts_lt_filt)
                    ts_lt_filt = None
                # ... and continue into the generic code
            # Other operators are handled by the generic code below
        if filt not in filters:
            filters.append(filt)
