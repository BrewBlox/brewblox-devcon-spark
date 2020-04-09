"""
Parses stream data into controlbox events and data
"""

import re
from queue import Queue
from typing import Generator

from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)


class ControlboxParser():

    def __init__(self):
        self._buffer: str = ''
        self._events = Queue()
        self._data = Queue()

    def event_messages(self) -> Generator[str, None, None]:
        while self._events.qsize() > 0:
            yield self._events.get_nowait()

    def data_messages(self) -> Generator[str, None, None]:
        while self._data.qsize() > 0:
            yield self._data.get_nowait()

    def push(self, recv: str):
        self._buffer += recv

        # Annotations use < and > as start/end characters
        # Most annotations can be discarded, except for event messages
        # Event messages are annotations that start with !
        for msg in self._coerce_message_from_buffer(start='<', end='>'):
            if msg.startswith('!'):  # Event
                self._events.put(msg[1:])
            else:
                LOGGER.info(f'Spark log: {msg}')

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for msg in self._coerce_message_from_buffer(start='^', end='\n'):
            self._data.put(msg)

    def _coerce_message_from_buffer(self, start: str, end: str):
        """ Filters separate messages from the buffer.

        It makes some assumptions about messages:
        * They have a fixed start/end special character
        * Start/end characters should not be included in yielded messages
        * Messages do not include start/end characters of other message types
        * Messages can be nested

        Returned messages are ordered on the position of their end character.
        Given the buffer: (< and > are start/end characters)

            '<messageA <messageB> <messageC> > data <messageD>'

        Yielded messages will be:

            [
                'messageB',
                'messageC',
                'messageA   ',
                'messageD'
            ]

        Afterwards, the buffer will contain ' data '
        """
        messages = []

        def extract_message(matchobj) -> str:
            msg = matchobj.group('message').rstrip()
            messages.append(msg)
            return ''

        while re.search(f'.*{start}.*{end}', self._buffer):
            self._buffer = re.sub(
                pattern=f'{start}(?P<message>[^{start}]*?){end}',
                repl=extract_message,
                string=self._buffer,
                count=1)

        yield from messages
