"""
Tests brewblox_devcon_spark.commander
"""

import pytest
from brewblox_service import scheduler
from brewblox_service.testing import matching

from brewblox_devcon_spark import codec, commander, connection, service_status
from brewblox_devcon_spark.models import ErrorCode, IntermediateResponse

TESTED = commander.__name__


@pytest.fixture
def app(app, mocker):
    app['config']['command_timeout'] = 1
    service_status.setup(app)
    scheduler.setup(app)
    codec.setup(app)
    connection.setup(app)
    commander.setup(app)
    return app


async def test_unexpected_message(app, client, mocker):
    m_log_error = mocker.patch(TESTED + '.LOGGER.error', autospec=True)
    cmder = commander.fget(app)
    response = IntermediateResponse(
        msgId=123,
        error=ErrorCode.OK,
        payload=[]
    )
    message = codec.fget(app).encode_response(response)
    await cmder._data_callback(message)
    m_log_error.assert_called_with(matching(r'.*Unexpected message'))
