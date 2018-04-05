"""
Tests brewblox_devcon_spark.__main__.py
"""

from brewblox_devcon_spark import __main__ as main


TESTED = main.__name__


def test_main(loop, mocker):
    create_mock = mocker.patch(TESTED + '.service.create_app')
    device_setup_mock = mocker.patch(TESTED + '.device.setup')
    furnish_mock = mocker.patch(TESTED + '.service.furnish')
    run_mock = mocker.patch(TESTED + '.service.run')
    app_mock = create_mock.return_value

    main.main()

    create_mock.assert_called_once_with(default_name='spark')
    furnish_mock.assert_called_once_with(app_mock)
    run_mock.assert_called_once_with(app_mock)
    device_setup_mock.assert_called_once_with(app_mock)
