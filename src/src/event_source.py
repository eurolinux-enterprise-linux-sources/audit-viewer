# Various audit event sources.
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
import collections
import datetime
import os.path
import re

import auparse

__all__ = ('ClientEventSource', 'ClientWithRotatedEventSource',
           'EmptyEventSource', 'Event', 'EventSource',
           'FileEventSource', 'FileWithRotatedEventSource',
           'StringEventSource',
           'Record',
           'check_expression',
           'is_rotated_file_name',
           'sorted_log_files')

class Event(object):

    '''A single audit event.'''

    __slots__ = ('id', 'fields', 'records')

    def __init__(self):
        # { key: [interpreted values] }, only for requested fields
        self.fields = {}
        self.records = []

    def __str__(self):
        return '%s|%s: %s' % (self.id.serial, self.id.sec,
                              '\n\t'.join((str(r) for r in self.records)))

class Record(object):

    '''An audit record within an event.'''

    __slots__ = ('fields', 'raw', 'type')

    def __init__(self, type, raw):
        self.type = type
        # [(key, interpreted value)...], only for fields not requested for
        # event.fields, and only if requested at all
        self.fields = []
        self.raw = raw

    def __str__(self):
        return '%s:<%s>' % (self.type, ', '.join(('%s=%s' % f
                                                  for f in self.fields)))

class EventSource(object):

    '''A source of audit events.'''

    def read_events(self, filters, wanted_fields, want_other_fields,
                    keep_raw_records):
        '''Return a sequence of audit events read from the source.

        Use filters to select events.  Store wanted_fields in event.fields, the
        rest in record.fields if want_other_fields.  Only store Record.raw if
        keep_raw_records.  Raise IOError.

        Note that the events are returned in random order, not necessarily in
        the order defined in the source file!

        '''
        raise NotImplementedError

class EmptyEventSource(EventSource):

    '''A 'source' of audit events, returning no events.'''

    def read_events(self, _filters, _wanted_fields, _want_other_fields,
                    _keep_raw_records):
        return ()


class _ParserEventSource(EventSource):

    '''A source of audit events, reading from an auparse parser.'''

    def read_events(self, filters, wanted_fields, want_other_fields,
                    keep_raw_records):
        '''Return a sequence of audit events read from parser.

        Use filters to select events.  Store wanted_fields in event.fields, the
        rest in record.fields if want_other_fields.  Only store Record.raw if
        keep_raw_records.

        Note that the events are returned in random order, not necessarily in
        the order defined in the source file!

        '''
        # This function is time critical, so it is a bit ugly.  "#o" comments
        # contain the "nice" version of some constructs
        parser = self._create_parser()
        events = collections.defaultdict(Event)

        parser.search_set_stop(auparse.AUSEARCH_STOP_EVENT)
        if len(filters) > 0:
            date = datetime.datetime.now()
            for filt in filters:
                # FIXME: more complex expressions?
                filt.apply(parser, date)
            next_event_fn = parser.search_next_event
        else:
            next_event_fn = parser.parse_next_event
        # Precompute as many lookups as possible
        parser_first_field = parser.first_field
        parser_first_record = parser.first_record
        parser_get_field_name = parser.get_field_name
        parser_get_field_str = parser.get_field_str
        parser_get_record_text = parser.get_record_text
        parser_get_timestamp = parser.get_timestamp
        parser_get_type = parser.get_type
        parser_interpret_field = parser.interpret_field
        parser_next_field = parser.next_field
        parser_next_record = parser.next_record
        parser_parse_next_event = parser.parse_next_event
        Record_constructor = Record
        while next_event_fn():
            ts = parser_get_timestamp()
            # FIXME: ts.host seems to be valid only until the next event is read
            e = events[(ts.serial, ts.sec, ts.milli)]
            # The Event() constructor does not have access to ts.  Most events
            # have only a single record, so this usually does not overwrite the
            # ID unnecessarily.
            e.id = ts
            if parser_first_record():
                e_fields = e.fields
                while 1: #o while True:
                    if keep_raw_records:
                        r = Record_constructor(parser_get_type(),
                                               parser_get_record_text())
                    else:
                        r = Record_constructor(parser_get_type(), None)
                    if parser_first_field():
                        if want_other_fields:
                            r_fields_append = r.fields.append # Precompute
                            while 1: #o while True:
                                key = parser_get_field_name()
                                value = parser_interpret_field()
                                if value is None:
                                    value = parser_get_field_str()
                                if key in wanted_fields:
                                    if key not in e_fields:
                                        e_fields[key] = [value]
                                    else:
                                        e_fields[key].append(value)
                                else:
                                    r_fields_append((key, value))
                                if not parser_next_field():
                                    break
                        else:
                            while 1: #o while True:
                                key = parser_get_field_name()
                                if key in wanted_fields:
                                    value = parser_interpret_field()
                                    if value is None:
                                        value = parser_get_field_str()
                                    if key not in e_fields:
                                        e_fields[key] = [value]
                                    else:
                                        e_fields[key].append(value)
                                if not parser_next_field():
                                    break
                    e.records.append(r)
                    if not parser_next_record():
                        break

            if filters: #o if len(filters) > 0:
                parser_parse_next_event()

        return events.itervalues()

    def _create_parser(self):
        '''Return a parser for the source.'''
        raise NotImplementedError

class FileEventSource(_ParserEventSource):

    '''A source of audit events, reading from a file.'''

    def __init__(self, path):
        self.path = path

    def _create_parser(self):
        return auparse.AuParser(auparse.AUSOURCE_FILE, self.path)

class FileWithRotatedEventSource(_ParserEventSource):

    '''A source of audit events, reading from files, including rotated files
    with the same base name.'''

    def __init__(self, path):
        if is_rotated_file_name(path):
            self.base = path[:path.rfind('.')]
        else:
            self.base = path

    __suffix_re = re.compile('^(\.\d+)?$')
    def _create_parser(self):
        dir = os.path.dirname(self.base)
        name_base = os.path.basename(self.base)
        files = (os.path.join(dir, name) for name in os.listdir(dir)
                 if name.startswith(name_base)
                 and self.__suffix_re.match(name[len(name_base):]) is not None)
        files = sorted_log_files(files)
        return auparse.AuParser(auparse.AUSOURCE_FILE_ARRAY, files)

class ClientEventSource(_ParserEventSource):

    '''A source of audit events, reading from the privileged server.'''

    def __init__(self, client, filename):
        self.client = client
        self.filename = filename

    def _create_parser(self):
        data = self.client.read_file(self.filename)
        return auparse.AuParser(auparse.AUSOURCE_BUFFER, data)

class ClientWithRotatedEventSource(_ParserEventSource):

    '''A source of audit events, reading from the privileged server, including
    rotated files with the same base name.

    '''

    def __init__(self, client, base):
        self.client = client
        self.base = base

    __suffix_re = re.compile('^(\.\d+)?$')
    def _create_parser(self):
        files = (name for name in self.client.list_files()
                 if name.startswith(self.base)
                 and self.__suffix_re.match(name[len(self.base):]) is not None)
        files = sorted_log_files(files)
        data = ''.join(self.client.read_file(f) for f in files)
        return auparse.AuParser(auparse.AUSOURCE_BUFFER, data)

class StringEventSource(_ParserEventSource):

    '''A source of audit events, reading from a string.'''

    def __init__(self, str):
        self.str = str

    def _create_parser(self):
        return auparse.AuParser(auparse.AUSOURCE_BUFFER, self.str)

def check_expression(expr):
    '''Check expr.

    Return None if expr is valid, an error message otherwise.

    '''
    parser = auparse.AuParser(auparse.AUSOURCE_BUFFER, '')
    try:
        parser.search_add_expression(expr, auparse.AUSEARCH_RULE_AND)
    except EnvironmentError, e:
        msg = e.message
    else:
        msg = None
    del parser
    return msg

__digits_re = re.compile('^\d+$')
def is_rotated_file_name(name):
    '''Return True if name is a rotated log file.'''
    pos = name.rfind('.')
    if pos != -1:
        return __digits_re.match(name[pos + 1:]) is not None
    return False

def sorted_log_files(names):
    '''Return names, sorted as log file names in "time order" (newest last).'''
    # Sort key is ('audit.log', 0) for 'audit.log',
    # ('audit.log', -1) for 'audit.log.1'
    def key(name):
        pos = name.rfind('.')
        if pos != -1:
            suffix = name[pos + 1:]
            if __digits_re.match(suffix) is not None:
                return (name[:pos], -int(suffix))
        return (name, 0)
    return sorted(names, key = key)

