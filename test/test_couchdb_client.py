"""
Tests brewblox_devcon_spark.couchdb_client
"""

from asyncio import CancelledError

import pytest
from aiohttp.client_exceptions import ClientResponseError
from aioresponses import aioresponses

from brewblox_devcon_spark import couchdb_client

TESTED = couchdb_client.__name__
SRV_URL = couchdb_client.COUCH_URL
DB_URL = f'{SRV_URL}/sparkbase'
DOC_URL = f'{DB_URL}/sparkdoc'


def err(status):
    return ClientResponseError(None, None, status=status)


@pytest.fixture
def resp():
    with aioresponses() as m:
        yield m


@pytest.fixture
def app(app, mocker):
    mocker.patch(TESTED + '.DB_RETRY_INTERVAL_S', 0.01)
    mocker.patch(TESTED + '.DB_CONTACT_TIMEOUT_S', 0.1)
    couchdb_client.setup(app)
    return app


@pytest.fixture
def cclient(app):
    return couchdb_client.get_client(app)


async def test_client_read(app, client, cclient, resp):
    # Blank database
    resp.head(SRV_URL)
    resp.put(DB_URL)
    resp.get(DOC_URL, exception=err(404))
    resp.put(DOC_URL, payload={'rev': 'rev_read'})
    assert await cclient.read('sparkbase', 'sparkdoc', [1, 2]) == ('rev_read', [1, 2])

    # Retry contact server, blank database
    resp.head(SRV_URL, exception=err(404))
    resp.head(SRV_URL)
    resp.put(DB_URL, exception=err(412))
    resp.get(DOC_URL, payload={'_rev': 'rev_read', 'data': [2, 1]})
    resp.put(DOC_URL, exception=err(409))
    assert await cclient.read('sparkbase', 'sparkdoc', []) == ('rev_read', [2, 1])


async def test_client_read_errors(app, client, cclient, resp):
    with pytest.raises(CancelledError):
        resp.head(SRV_URL, exception=CancelledError())
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(CancelledError):
        resp.head(SRV_URL)
        resp.put(DB_URL, exception=CancelledError())
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(CancelledError):
        resp.head(SRV_URL)
        resp.put(DB_URL)
        resp.get(DOC_URL, exception=err(404))
        resp.put(DOC_URL, exception=CancelledError())
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(CancelledError):
        resp.head(SRV_URL)
        resp.put(DB_URL)
        resp.get(DOC_URL, exception=CancelledError())
        resp.put(DOC_URL, exception=err(412))
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(ClientResponseError):
        resp.head(SRV_URL)
        resp.put(DB_URL, status=404, exception=err(404))
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(ClientResponseError):
        resp.head(SRV_URL)
        resp.put(DB_URL)
        resp.put(DOC_URL, exception=err(404))  # unexpected
        resp.get(DOC_URL, exception=err(404))
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(ClientResponseError):
        resp.head(SRV_URL)
        resp.put(DB_URL)
        resp.put(DOC_URL, exception=err(412))
        resp.get(DOC_URL, exception=err(500))  # unexpected
        await cclient.read('sparkbase', 'sparkdoc', [])

    with pytest.raises(ValueError):
        resp.head(SRV_URL)
        resp.put(DB_URL)
        # Either get or put must return an ok value
        resp.put(DOC_URL, exception=err(409))
        resp.get(DOC_URL, exception=err(404))
        await cclient.read('sparkbase', 'sparkdoc', [])


async def test_client_write(app, client, cclient, resp):
    resp.put(f'{DOC_URL}?rev=revy', payload={'rev': 'rev_write'})
    assert await cclient.write('sparkbase', 'sparkdoc', 'revy', [1, 2]) == 'rev_write'
