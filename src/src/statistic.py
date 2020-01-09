# Value statistic gathering
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

from filters import FieldFilter, TimestampFilter
import format_versions
import lists
import util

__all__ = ('FieldStatistic')

def N_(s): return s

class _ValueRange(object):

    '''A field value range within a FieldStatistic.'''

    def get_label(self):
        '''Return an UI label for this range.'''
        raise NotImplementedError

    def get_csv_label(self):
        '''Return a valid CSV value for this range.

        "Valid" means "likely to be interpreted a value of the right type
        by a spreadsheet.'''
        return self.get_label()

    def get_filters(self):
        '''Return a list of filters limiting searches to this value range.

        May raise ValueError if limiting searches is not possible.

        '''
        raise NotImplementedError

class FieldStatistic(object):

    '''A collection of ValueRanges.'''

    def statistic_name(self):
        '''Return an user-readable name for this statistic.

        Return None if this is a default statistic and should not be presented
        to the user separately.  The name will appear in an 'Group by' combo
        box.

        '''
        raise NotImplementedError

    def clear(self):
        '''Drop all collected ranges, prepare for new statistic gathering.'''
        raise NotImplementedError

    def get_range(self, event):
        '''Return a value range for an event.

        Calls with different events mapping onto an "identical" range will
        always return the same object.

        '''
        raise NotImplementedError

    def ordered_ranges(self):
        '''Return ranges in presentation order.'''
        raise NotImplementedError

    def add_wanted_fields(self, set_):
        '''Add names of necessary event fields to set_.'''
        raise NotImplementedError

    def _load_config(self, elem):
        '''Load configuration from elem.

        Raise SyntaxError if elem is invalid.

        '''
        pass

    def save_config(self, unused_state, elem_type):
        '''Return a cElement tree representing configuration of the statistic.

        Use element_type as the element type.  Modify state if necessary.

        '''
        # Use state.ensure_version() when changing the config file format!
        return cElementTree.Element(elem_type, type = self.__xml_statistic_name)

    __xml_statistic_name_map = {}

    @staticmethod
    def _set_xml_statistic_name(xml_statistic_name, class_):
        '''Set the type field value for class_ to xml_statistic_name.'''
        class_.__xml_statistic_name = xml_statistic_name
        FieldStatistic.__xml_statistic_name_map[xml_statistic_name] = class_

    @staticmethod
    def load_statistic(elem):
        '''Load a statistic from elem.

        Return the statistic if succesful.  Raise SyntaxError if elem is
        invalid.

        '''
        type_ = util.xml_mandatory_attribute(elem, 'type')
        if type_ not in FieldStatistic.__xml_statistic_name_map:
            util.xml_raise_unknown_value(elem, 'type')
        statistic = FieldStatistic.__xml_statistic_name_map[type_]()
        statistic._load_config(elem)
        return statistic

    @staticmethod
    def options(field_name):
        '''Return a sequence of possible statistics for the specified field.

        The first returned statistic is assumed to be the default.

        '''
        if field_name == 'date':
            return (_SimpleDateStatistic(), _TimeGroupingStatistic(60),
                    _TimeGroupingStatistic(3600), _DayGroupingStatistic(),
                    _WeekGroupingStatistic(), _MonthGroupingStatistic())
        if field_name in lists.integer_field_names:
            return (_NumericFieldStatistic(field_name),)
        return (_SimpleFieldStatistic(field_name),)

 # Generic value ranges

class _OneValueRange(_ValueRange):

    '''A trivial value range, containing only a single value.'''

    def __init__(self, field, value):
        self.__field = field
        self.__value = value

    def get_label(self):
        return self.__value

    def get_filters(self):
        return [FieldFilter(self.__field, '=', self.__value)]

class _NoValueRange(_ValueRange):

    '''A "value" range containing events without a value.'''

    def get_label(self):
        return _('Unspecified')

    def get_filters(self):
        # FIXME??? is this necessary / should it be possible?
        raise ValueError

 # A generic statistic

class _NaturalKeyStatistic(FieldStatistic):

    '''A statistic which assigns keys to ranges and uses the key ordering.'''

    def __init__(self):
        self.clear()

    def clear(self):
        self.__ranges = {}

    def get_range(self, event):
        key = self._range_key(event)
        if key in self.__ranges:
            rng = self.__ranges[key]
        else:
            rng = self._create_range(key)
            self.__ranges[key] = rng
        return rng

    def _range_key(self, event):
        '''Return a key for the specified event.'''
        raise NotImplementedError

    def _create_range(self, key):
        '''Return a new range for the specified key/event.'''
        raise NotImplementedError

    def ordered_ranges(self):
        return [self.__ranges[key] for key in sorted(self.__ranges.iterkeys())]

 # Simple field statistic

class _SimpleFieldStatistic(FieldStatistic):

    '''A non-aggregating field statistic.'''

    def __init__(self, field_name = None):
        # field_name default value assumed to be overwritten by _load_config
        self.field_name = field_name
        self.clear()

    def statistic_name(self):
        return None

    def clear(self):
        self._ranges = {}
        self._no_value = None

    def get_range(self, event):
        if self.field_name in event.fields:
            value = event.fields[self.field_name][0]
            if value in self._ranges:
                rng = self._ranges[value]
            else:
                rng = _OneValueRange(self.field_name, value)
                self._ranges[value] = rng
            return rng
        else:
            if self._no_value is None:
                self._no_value = _NoValueRange()
            return self._no_value

    def ordered_ranges(self):
        l = sorted(self._ranges.itervalues(),
                   key = lambda range: range.get_label())
        if self._no_value is not None:
            l.append(self._no_value)
        return l

    def add_wanted_fields(self, set_):
        set_.add(self.field_name)

    def save_config(self, state, elem_type):
        elem = super(_SimpleFieldStatistic, self).save_config(state, elem_type)
        elem.set('field', self.field_name.decode('utf-8'))
        return elem

    def _load_config(self, elem):
        self.field_name = util.xml_mandatory_attribute(elem, 'field')

FieldStatistic._set_xml_statistic_name('simple_field', _SimpleFieldStatistic)

class _NumericFieldStatistic(_SimpleFieldStatistic):

    '''A non-aggregating field statistic that sorts numbers by their value.'''

    def ordered_ranges(self):
        numeric_ranges = []
        other_ranges = []
        for r in self._ranges.itervalues():
            key = r.get_label()
            try:
                v = int(key)
            except ValueError:
                v = None
            if v is not None:
                numeric_ranges.append(r)
            else:
                other_ranges.append(r)
        numeric_ranges.sort(key = lambda range: int(range.get_label()))
        other_ranges.sort(key = lambda range: range.get_label())
        l = numeric_ranges + other_ranges
        if self._no_value is not None:
            l.append(self._no_value)
        return l

    def save_config(self, state, elem_type):
        state.ensure_version(format_versions.numeric_field_statistic_version)
        return super(_NumericFieldStatistic, self).save_config(state, elem_type)

    def _load_config(self, elem):
        self.field_name = util.xml_mandatory_attribute(elem, 'field')

FieldStatistic._set_xml_statistic_name('numeric_field', _NumericFieldStatistic)

 # Date field statistics

# FIXME: Should ordered_ranges() include also all unused ranges within the used
# interval?

class _OneDateRange(_ValueRange):

    '''A simple date range, containing only a single date.'''

    def __init__(self, date_pair):
        (self.__sec, self.__msec) = date_pair

    def get_label(self):
        tm = time.localtime(self.__sec)
        return time.strftime(_('%x %H:%M:%S'), tm) + ('.%03d' % self.__msec)

    def get_csv_label(self):
        # This loses the microsecond precision
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.__sec))

    def get_filters(self):
        return [TimestampFilter('=', self.__sec, self.__msec)]

class _SimpleDateStatistic(_NaturalKeyStatistic):

    '''A non-aggregating date statistic.'''

    field_name = 'date'

    def statistic_name(self):
        return None

    def add_wanted_fields(self, set_):
        pass

    def _range_key(self, event):
        return (event.id.sec, event.id.milli)

    def _create_range(self, key):
        return _OneDateRange(key)

FieldStatistic._set_xml_statistic_name('simple_date', _SimpleDateStatistic)

class _SecondIntervalRange(_ValueRange):

    '''A half-open date range, displaying the time in seconds as well.'''

    def __init__(self, start, end):
        self._start = start
        self._end = end

    def get_label(self):
        return time.strftime(_('%x %X'), time.localtime(self._start))

    def get_csv_label(self):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._start))

    def get_filters(self):
        return [TimestampFilter('>=', self._start, 0),
                TimestampFilter('<', self._end, 0)]

class _MinuteIntervalRange(_SecondIntervalRange):

    '''A half-open date range, displaying the time in minutes as well.'''

    def get_label(self):
        return time.strftime(_('%x %H:%M'), time.localtime(self._start))

    def get_csv_label(self):
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(self._start))

class _HourIntervalRange(_SecondIntervalRange):

    '''A half-open date range, displaying the time in hours as well.'''

    def get_label(self):
        return time.strftime(_('%x %H'), time.localtime(self._start))

    def get_csv_label(self):
        # Just %H doesn't work in OpenOffice.org
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(self._start))

class _TimeGroupingStatistic(_NaturalKeyStatistic):

    '''A date statistic aggregating by a specified number of seconds.'''

    field_name = 'date'

    def __init__(self, interval = 1):
        _NaturalKeyStatistic.__init__(self)
        self.interval = interval
        if self.interval % 3600 == 0:
            self.range_class = _HourIntervalRange
        elif self.interval % 60 == 0:
            self.range_class = _MinuteIntervalRange
        else:
            self.range_class = _SecondIntervalRange

    def statistic_name(self):
        if self.interval == 3600:
            return _('hour')
        elif self.interval % 3600 == 0:
            hours = self.interval / 3600
            return ngettext('%d hour', '%d hours', hours) % hours
        elif self.interval == 60:
            return _('minute')
        elif self.interval % 60 == 0:
            minutes = self.interval / 60
            return ngettext('%d minute', '%d minutes', minutes) % minutes
        elif self.interval == 1:
            return _('second')
        else:
            return (ngettext('%d second', '%d seconds', self.interval)
                    % self.interval)

    def add_wanted_fields(self, set_):
        pass

    def save_config(self, state, elem_type):
        elem = super(_TimeGroupingStatistic, self).save_config(state, elem_type)
        elem.set('interval', '%d' % self.interval)
        return elem

    def _load_config(self, elem):
        v = util.xml_mandatory_attribute(elem, 'interval')
        try:
            self.interval = int(v)
        except ValueError:
            util.xml_raise_invalid_value(elem, 'interval')

    def _range_key(self, event):
        return event.id.sec / self.interval

    def _create_range(self, key):
        return self.range_class(key * self.interval, (key + 1) * self.interval)

FieldStatistic._set_xml_statistic_name('time_grouping', _TimeGroupingStatistic)

class _DayIntervalRange(_ValueRange):

    '''A half-open date range.'''

    def __init__(self, start_ordinal, end_ordinal):
        # There seems to be no better way to convert an ordinal back to a
        # timestamp.
        date = datetime.date.fromordinal(start_ordinal)
        self.__start_ts = int(date.strftime('%s'))
        date = datetime.date.fromordinal(end_ordinal)
        self.__end_ts = int(date.strftime('%s'))

    def get_label(self):
        return time.strftime('%x', time.localtime(self.__start_ts))

    def get_csv_label(self):
        return time.strftime('%Y-%m-%d', time.localtime(self.__start_ts))

    def get_filters(self):
        return [TimestampFilter('>=', self.__start_ts, 0),
                TimestampFilter('<', self.__end_ts, 0)]

class _DayGroupingStatistic(_NaturalKeyStatistic):

    '''A date statistic aggregating by days.'''

    field_name = 'date'

    def statistic_name(self):
        return _('day')

    def add_wanted_fields(self, set_):
        pass

    def _range_key(self, event):
        return datetime.date.fromtimestamp(event.id.sec).toordinal()

    def _create_range(self, key):
        return _DayIntervalRange(key, key + 1)

FieldStatistic._set_xml_statistic_name('day_grouping', _DayGroupingStatistic)

class _WeekGroupingStatistic(_NaturalKeyStatistic):

    '''A date statistic aggregating by weeks.'''

    field_name = 'date'

    def statistic_name(self):
        return _('week')

    def add_wanted_fields(self, set_):
        pass

    def _range_key(self, event):
        date = datetime.date.fromtimestamp(event.id.sec)
        return date.toordinal() - util.week_day(date)

    def _create_range(self, key):
        return _DayIntervalRange(key, key + util.week_length)

FieldStatistic._set_xml_statistic_name('week_grouping', _WeekGroupingStatistic)

class _MonthRange(_ValueRange):

    '''A month date range.'''

    def __init__(self, date_ordinal):
        date = datetime.date.fromordinal(date_ordinal)
        self.__start_ts = int(date.strftime('%s'))
        if date.month != 12:
            date = date.replace(month = date.month + 1)
        else:
            date = date.replace(year = date.year + 1, month = 1)
        self.__end_ts = int(date.strftime('%s'))

    def get_label(self):
        return time.strftime(_('%b %Y'), time.localtime(self.__start_ts))

    def get_csv_label(self):
        # Just %Y-%m doesn't work in OpenOffice.org
        return time.strftime('%Y-%m-01', time.localtime(self.__start_ts))

    def get_filters(self):
        return [TimestampFilter('>=', self.__start_ts, 0),
                TimestampFilter('<', self.__end_ts, 0)]

class _MonthGroupingStatistic(_NaturalKeyStatistic):

    '''A date statistic aggregating by days.'''

    field_name = 'date'

    def statistic_name(self):
        return _('month')

    def add_wanted_fields(self, set_):
        pass

    def _range_key(self, event):
        return (datetime.date.fromtimestamp(event.id.sec).replace(day = 1)
                .toordinal())

    def _create_range(self, key):
        return _MonthRange(key)

FieldStatistic._set_xml_statistic_name('week_grouping', _WeekGroupingStatistic)
