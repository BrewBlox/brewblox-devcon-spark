"""
Parses stream data into controlbox events and data
"""

import re
from queue import Queue
from typing import Generator, List

from brewblox_service import brewblox_logger

LOGGER = brewblox_logger(__name__)

# Pattern: '{start}(?P<message>[^{start}]*?){end}'
EVENT_END = '>'
EVENT_PATTERN = re.compile('<(?P<message>[^<]*?)>')
DATA_END = '\n'
DATA_PATTERN = re.compile('^(?P<message>[^^]*?)\n')


class ControlboxParser():

    def __init__(self):
        self._buffer: str = ''
        self._events = Queue()
        self._data = Queue()
        self._messages: List[str] = []

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
        for msg in self._coerce_message_from_buffer(EVENT_PATTERN, EVENT_END):
            if msg.startswith('!'):  # Event
                self._events.put(msg[1:])
            else:
                LOGGER.info(f'Spark log: {msg}')

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for msg in self._coerce_message_from_buffer(DATA_PATTERN, DATA_END):
            self._data.put(msg)

    def _extract_message(self, matchobj: re.Match) -> str:
        msg = matchobj.group('message').rstrip()
        self._messages.append(msg)
        return ''

    def _coerce_message_from_buffer(self, pattern: re.Pattern, end: str):
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
        prev_len = 0

        # Don't bother checking if end char is not in buffer
        # Break the loop when buffer is unchanged after re.sub()
        # The break is required if the buffer receives malformed data
        while end in self._buffer and prev_len != len(self._buffer):
            prev_len = len(self._buffer)
            self._buffer = re.sub(
                pattern=pattern,
                repl=self._extract_message,
                string=self._buffer,
                count=1)

        yield from self._messages
        self._messages = []
