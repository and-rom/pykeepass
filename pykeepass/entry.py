# FIXME python2
from __future__ import absolute_import, unicode_literals
from future.utils import python_2_unicode_compatible

import logging
from copy import deepcopy
from datetime import datetime

from lxml.builder import E
from lxml.etree import Element, _Element
from lxml.objectify import ObjectifiedElement

import pykeepass.attachment
import pykeepass.group
from pykeepass.baseelement import BaseElement

logger = logging.getLogger(__name__)
reserved_keys = [
    'Title',
    'UserName',
    'Password',
    'URL',
    'Tags',
    'IconID',
    'Times',
    'History',
    'Notes'
]

# FIXME python2
@python_2_unicode_compatible
class Entry(BaseElement):

    def __init__(self, title=None, username=None, password=None, url=None,
                 notes=None, tags=None, expires=False, expiry_time=None,
                 icon=None, autotype_sequence=None, autotype_enabled=True,
                 element=None, kp=None):

        self._kp = kp

        if element is None:
            super().__init__(
                element=Element('Entry'),
                kp=kp,
                expires=expires,
                expiry_time=expiry_time,
                icon=icon
            )
            self._element.append(E.String(E.Key('Title'), E.Value(title)))
            self._element.append(E.String(E.Key('UserName'), E.Value(username)))
            self._element.append(
                E.String(E.Key('Password'), E.Value(password, Protected="True"))
            )
            if url:
                self._element.append(E.String(E.Key('URL'), E.Value(url)))
            if notes:
                self._element.append(E.String(E.Key('Notes'), E.Value(notes)))
            if tags:
                self._element.append(
                    E.Tags(';'.join(tags) if type(tags) is list else tags)
                )
            self._element.append(
                E.AutoType(
                    E.Enabled(str(autotype_enabled)),
                    E.DataTransferObfuscation('0'),
                    E.DefaultSequence(str(autotype_sequence) if autotype_sequence else '')
                )
            )

        else:
            assert type(element) in [_Element, Element, ObjectifiedElement], \
                'The provided element is not an LXML Element, but a {}'.format(
                    type(element)
                )
            assert element.tag == 'Entry', 'The provided element is not an Entry '\
                'element, but a {}'.format(element.tag)
            self._element = element

    def _get_string_field(self, key):
        field = self._xpath('String/Key[text()="{}"]/../Value'.format(key), first=True)
        if field is not None:
            return field.text

    def _set_string_field(self, key, value):
        field = self._xpath('String/Key[text()="{}"]/..'.format(key), first=True)
        if field is not None:
            self._element.remove(field)
        self._element.append(E.String(E.Key(key), E.Value(value)))

    def _get_string_field_keys(self, exclude_reserved=False):
        results = [x.find('Key').text for x in self._element.findall('String')]
        if exclude_reserved:
            return [x for x in results if x not in reserved_keys]
        else:
            return results

    @property
    def attachments(self):
        return self._kp.find_attachments(
            element=self,
            filename='.*',
            regex=True,
            recursive=False
        )

    def add_attachment(self, id, filename):
        element = E.Binary(
            E.Key(filename),
            E.Value(Ref=str(id))
        )
        self._element.append(element)

        return pykeepass.attachment.Attachment(element=element, kp=self._kp)

    def delete_attachment(self, attachment):
        attachment.delete()

    def deref(self, attribute):
        return self._kp.deref(getattr(self, attribute))

    @property
    def title(self):
        return self._get_string_field('Title')

    @title.setter
    def title(self, value):
        return self._set_string_field('Title', value)

    @property
    def username(self):
        return self._get_string_field('UserName')

    @username.setter
    def username(self, value):
        return self._set_string_field('UserName', value)

    @property
    def password(self):
        return self._get_string_field('Password')

    @password.setter
    def password(self, value):
        return self._set_string_field('Password', value)

    @property
    def url(self):
        return self._get_string_field('URL')

    @url.setter
    def url(self, value):
        return self._set_string_field('URL', value)

    @property
    def notes(self):
        return self._get_string_field('Notes')

    @notes.setter
    def notes(self, value):
        return self._set_string_field('Notes', value)

    @property
    def icon(self):
        return self._get_subelement_text('IconID')

    @icon.setter
    def icon(self, value):
        return self._set_subelement_text('IconID', value)

    @property
    def tags(self):
        val = self._get_subelement_text('Tags')
        return val.split(';') if val else val

    @tags.setter
    def tags(self, value):
        # Accept both str or list
        v = ';'.join(value if type(value) is list else [value])
        return self._set_subelement_text('Tags', v)

    @property
    def history(self):
        if self._element.find('History') is not None:
            return [HistoryEntry(element=x, kp=self._kp) for x in self._element.find('History').findall('Entry')]
        else:
            return []

    @history.setter
    def history(self, value):
        raise NotImplementedError()

    @property
    def autotype_enabled(self):
        enabled = self._element.find('AutoType/Enabled')
        if enabled.text is not None:
            return enabled.text == 'True'

    @autotype_enabled.setter
    def autotype_enabled(self, value):
        enabled = self._element.find('AutoType/Enabled')
        if value is not None:
            enabled.text = str(value)
        else:
            enabled.text = None

    @property
    def autotype_sequence(self):
        sequence = self._element.find('AutoType/DefaultSequence')
        if sequence is None or sequence.text == '':
            return None
        return sequence.text

    @autotype_sequence.setter
    def autotype_sequence(self, value):
        self._element.find('AutoType/DefaultSequence').text = value

    @property
    def is_a_history_entry(self):
        parent = self._element.getparent()
        if parent is not None:
            return parent.tag == 'History'
        return False

    @property
    def path(self):
        """Path to element as list.  List contains all parent group names
        ending with entry title.  List may contain strings or NoneTypes."""

        # The root group is an orphan
        if self.parentgroup is None:
            return None
        p = self.parentgroup
        path = [self.title]
        while p is not None and not p.is_root_group:
            if p.name is not None:  # dont make the root group appear
                path.insert(0, p.name)
            p = p.parentgroup
        return path

    def set_custom_property(self, key, value):
        assert key not in reserved_keys, '{} is a reserved key'.format(key)
        return self._set_string_field(key, value)

    def get_custom_property(self, key):
        assert key not in reserved_keys, '{} is a reserved key'.format(key)
        return self._get_string_field(key)

    def delete_custom_property(self, key):
        if key not in self._get_string_field_keys(exclude_reserved=True):
            raise AttributeError('No such key: {}'.format(key))
        prop = self._xpath('String/Key[text()="{}"]/..'.format(key), first=True)
        if prop is None:
            raise AttributeError('Could not find property element')
        self._element.remove(prop)

    @property
    def custom_properties(self):
        keys = self._get_string_field_keys(exclude_reserved=True)
        props = {}
        for k in keys:
            props[k] = self._get_string_field(k)
        return props

    def ref(self, attribute):
        """Create reference to an attribute of this element."""
        attribute_to_field = {
            'title': 'T',
            'username': 'U',
            'password': 'P',
            'url': 'A',
            'notes': 'N',
            'uuid': 'I',
        }
        return '{{REF:{}@I:{}}}'.format(attribute_to_field[attribute], self.uuid.hex.upper())

    def save_history(self):
        '''
        Save the entry in its history
        '''
        archive = deepcopy(self._element)
        hist = archive.find('History')
        if hist is not None:
            archive.remove(hist)
            self._element.find('History').append(archive)
        else:
            history = Element('History')
            history.append(archive)
            self._element.append(history)

    def delete_history(self, history_entry=None, all=False):
        """
        Delete entries from history

        Args:
            history_entry (Entry): history item to delete
            all (bool): delete all entries from history.  Default is False
        """

        if all:
            self._element.remove(self._element.find('History'))
        else:
            self._element.find('History').remove(history_entry._element)

    def __str__(self):
        # filter out NoneTypes and join into string
        pathstr = '/'.join('' if p==None else p for p in self.path)
        return 'Entry: "{} ({})"'.format(pathstr, self.username)


class HistoryEntry(Entry):

    def __str__(self):
        pathstr = super().__str__()
        return 'HistoryEntry: {}'.format(pathstr)

    def __eq__(self, other):
        # all history items share the same uuid, so examine xml directly
        return self._element == other._element
