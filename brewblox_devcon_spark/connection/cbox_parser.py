"""
Parses stream data into controlbox events and data
"""

import logging
import re
from collections import deque
from collections.abc import Generator

LOGGER = logging.getLogger(__name__)

# Pattern: '{start}(?P<message>[^{start}{end}]*){end}'
# The same match as a lazy `[^{start}]*?`, without a backtracking step per character
EVENT_END = '>'
EVENT_PATTERN = re.compile('<(?P<message>[^<>]*)>')
DATA_END = '\n'
DATA_PATTERN = re.compile('^(?P<message>[^^\n]*)\n')


class CboxParser:
    def __init__(self):
        self._buffer: str = ''
        self._events: deque[str] = deque()
        self._data: deque[str] = deque()
        self._messages: list[str] = []

    def event_messages(self) -> Generator[str, None, None]:
        while self._events:
            yield self._events.popleft()

    def data_messages(self) -> Generator[str, None, None]:
        while self._data:
            yield self._data.popleft()

    def reset(self):
        """
        Discard any buffered bytes and queued messages.
        Called on handshake to treat it as a hard sync boundary:
        anything parsed before was boot/reconnect noise.
        """
        self._buffer = ''
        self._messages = []
        self._events.clear()
        self._data.clear()

    def push(self, recv: str):
        self._buffer += recv

        # Annotations use < and > as start/end characters
        # Event messages are annotations that start with !
        # Other annotations (including wrapped firmware logs) are handled by _on_event
        for msg in self._coerce_message_from_buffer(EVENT_PATTERN, EVENT_END):
            if msg:  # Skip empty annotations (e.g. from newlines)
                self._events.append(msg)

        # Once annotations are filtered, all that remains is data
        # Data is newline-separated
        for msg in self._coerce_message_from_buffer(DATA_PATTERN, DATA_END):
            if msg:  # Skip empty lines
                self._data.append(msg)

    def _extract_message(self, matchobj: re.Match) -> str:
        msg = matchobj.group('message').rstrip()
        self._messages.append(msg)
        return ''

    def _coerce_message_from_buffer(self, pattern: re.Pattern, end: str):
        """Filters separate messages from the buffer.

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
            self._buffer = re.sub(pattern=pattern, repl=self._extract_message, string=self._buffer, count=1)

        yield from self._messages
        self._messages = []
