"""
Tests brewblox_controller_spark.__main__.py
"""

from brewblox_controller_spark import __main__ as main


TESTED = main.__name__


def test_main(loop, mocker):
    create_mock = mocker.patch(TESTED + '.service.create_app')
    ctrl_setup_mock = mocker.patch(TESTED + '.controller.setup')
    furnish_mock = mocker.patch(TESTED + '.service.furnish')
    run_mock = mocker.patch(TESTED + '.service.run')
    # events_mock = mocker.patch(TESTED + '.events.setup')
    app_mock = create_mock.return_value

    main.main()

    create_mock.assert_called_once_with(default_name='spark')
    furnish_mock.assert_called_once_with(app_mock)
    run_mock.assert_called_once_with(app_mock)
    ctrl_setup_mock.assert_called_once_with(app_mock)
    # events_mock.assert_called_once_with(app_mock)
