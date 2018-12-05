import asyncio
from typing import Any, Awaitable, Tuple

from aiohttp import ClientSession, client_exceptions, web
from brewblox_service import brewblox_logger, features

LOGGER = brewblox_logger(__name__)

DB_CONTACT_TIMEOUT_S = 30
DB_RETRY_INTERVAL_S = 1
COUCH_URL = 'http://couchstore:5984'


def setup(app: web.Application):
    features.add(app, CouchDBClient(app))


def get_client(app: web.Application) -> 'CouchDBClient':
    return features.get(app, CouchDBClient)


class CouchDBClient(features.ServiceFeature):

    def __init__(self, app: web.Application):
        super().__init__(app)

        self._session: ClientSession = None
        self._rev = None

    def __str__(self):
        return f'<{type(self).__name__} for {COUCH_URL}>'

    async def startup(self, app: web.Application):
        await self.shutdown(app)
        self._session = await ClientSession(raise_for_status=True).__aenter__()

    async def shutdown(self, app: web.Application):
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None

    async def read(self, database: str, document: str, default_data: Any) -> Awaitable[Tuple[str, Any]]:
        db_url = f'{COUCH_URL}/{database}'
        document_url = f'{db_url}/{document}'

        async def contact_store():
            while True:
                try:
                    await self._session.head(COUCH_URL, raise_for_status=False)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await asyncio.sleep(DB_RETRY_INTERVAL_S)
                else:
                    return

        async def ensure_database():
            try:
                await self._session.put(db_url)
                LOGGER.info(f'{self} New database created ({database})')

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 412:  # Already exists
                    raise ex

        async def create_document():
            try:
                resp = await self._session.put(document_url, json={'data': default_data})
                resp_content = await resp.json()

                rev = resp_content['rev']
                data = default_data
                LOGGER.info(f'{self} New document created ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 409:  # Conflict: already exists
                    raise ex

        async def read_document():
            try:
                resp = await self._session.get(document_url)
                resp_content = await resp.json()

                rev = resp_content['_rev']
                data = resp_content['data']
                LOGGER.info(f'{self} Existing document found ({document})')
                return rev, data

            except client_exceptions.ClientResponseError as ex:
                if ex.status != 404:
                    raise ex

        try:
            await asyncio.wait_for(contact_store(), DB_CONTACT_TIMEOUT_S)
            await ensure_database()
            read_result, create_result = await asyncio.gather(read_document(), create_document())
            (rev, data) = read_result or create_result or (None, None)
            if rev is None:
                raise ValueError('Data was neither read nor created')
            return rev, data

        except asyncio.CancelledError:
            raise

        except Exception as ex:
            LOGGER.error(f'{self} {type(ex).__name__}({ex})')
            raise ex

    async def write(self, database: str, document: str, rev: str, data: Any) -> Awaitable[str]:
        kwargs = {
            'url': f'{COUCH_URL}/{database}/{document}',
            'json': {'data': data},
            'params': [('rev', rev)],
        }

        resp = await self._session.put(**kwargs)
        resp_content = await resp.json()
        return resp_content['rev']
