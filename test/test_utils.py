"""
Tests brewblox_devcon_spark.utils
"""
import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from brewblox_devcon_spark import utils

TESTED = utils.__name__


def test_not_sentinel():
    assert utils.not_sentinel('v', 'dv') == 'v'
    assert utils.not_sentinel('', 'dv') == ''
    assert utils.not_sentinel(None, 'dv') is None
    assert utils.not_sentinel(..., 'dvt') == 'dvt'
    assert utils.not_sentinel(..., ...) is ...


def test_add_logging_level(caplog: pytest.LogCaptureFixture):
    logger = logging.getLogger('test_add_logging_level')

    utils.add_logging_level('GOSSIP', logging.WARNING - 1)

    logging.gossip('juicy')
    logger.gossip('deets')

    record = caplog.records[-2]
    assert record.levelname == 'GOSSIP'
    assert record.levelno == logging.GOSSIP
    assert record.message == 'juicy'

    record = caplog.records[-1]
    assert record.levelname == 'GOSSIP'
    assert record.levelno == logging.GOSSIP
    assert record.message == 'deets'

    # Repeat calls are ok
    utils.add_logging_level('GOSSIP', logging.WARNING - 1)

    # Mismatched level
    with pytest.raises(AttributeError):
        utils.add_logging_level('GOSSIP', logging.WARNING + 1)

    # Name is already in use
    with pytest.raises(AttributeError):
        utils.add_logging_level('Gossip', logging.WARNING - 1)


async def test_httpx_retry():
    m_ok = Mock()
    m_ok.is_success = True

    m_nok = Mock()
    m_nok.is_success = False

    f = AsyncMock()
    f.return_value = m_ok

    await asyncio.wait_for(utils.httpx_retry(f, interval=timedelta(seconds=2)), timeout=1)
    assert f.await_count == 1

    f.reset_mock()
    f.side_effect = [RuntimeError, m_nok, m_ok]
    await asyncio.wait_for(utils.httpx_retry(f, interval=timedelta()), timeout=1)
    assert f.await_count == 3
