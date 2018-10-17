"""
Persistent configuration. Is read from file on startup, and then periodically flushes changes to file.
"""

import asyncio
import json
from concurrent.futures import CancelledError
from contextlib import contextmanager

import aiofiles
from aiohttp import web
from brewblox_service import brewblox_logger, features, scheduler

LOGGER = brewblox_logger(__name__)

FLUSH_DELAY_S = 5


class FileConfig(features.ServiceFeature):

    def __init__(self, app: web.Application, filename: str):
        features.ServiceFeature.__init__(self, app)
        self._config: dict = {}
        self._filename: str = filename
        self._flush_task: asyncio.Task = None
        self._changed_event: asyncio.Event = None

        try:
            self.read_file()
        except FileNotFoundError:
            LOGGER.warn(f'{self} file not found.')
        except Exception:
            LOGGER.error(f'{self} unable to read objects.')
            raise

    def __str__(self):
        return f'<{type(self).__name__} for {self._filename}>'

    @property
    def active(self):
        return self._flush_task and not self._flush_task.done()

    @contextmanager
    def open(self):
        before = json.dumps(self._config)
        yield self._config
        after = json.dumps(self._config)
        if before != after and self._changed_event:
            self._changed_event.set()

    def read_file(self):
        with open(self._filename) as f:
            self._config = json.load(f)

    async def write_file(self):
        async with aiofiles.open(self._filename, mode='w') as f:
            await f.write(json.dumps(self._config))

    async def _autoflush(self):
        while True:
            try:
                await self._changed_event.wait()
                await asyncio.sleep(FLUSH_DELAY_S)
                await self.write_file()
                self._changed_event.clear()

            except CancelledError:
                await self.write_file()
                break

            except Exception as ex:
                LOGGER.warn(f'{self} {type(ex).__name__}({ex})')

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._changed_event = asyncio.Event()
        self._flush_task = await scheduler.create_task(app, self._autoflush())

    async def shutdown(self, app: web.Application):
        self._changed_event = None
        await scheduler.cancel_task(app, self._flush_task)
