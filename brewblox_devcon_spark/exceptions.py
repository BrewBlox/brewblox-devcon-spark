"""
Lists various possible BrewBlox-related exceptions.
This improves clarity as to what actually went wrong.
"""

from aiohttp import web


class BrewbloxException(Exception):
    http_error = web.HTTPInternalServerError


##################################################################################################
# Generic exceptions
##################################################################################################


class InvalidInput(BrewbloxException):
    http_error = web.HTTPBadRequest


class MissingInput(InvalidInput):
    pass


##################################################################################################
# ID exceptions
##################################################################################################


class IdException(BrewbloxException):
    http_error = web.HTTPBadRequest


class InvalidId(IdException):
    pass


class ExistingId(IdException):
    http_error = web.HTTPConflict


class UnknownId(IdException):
    pass


##################################################################################################
# Command exceptions
##################################################################################################


class CommandException(BrewbloxException):
    pass


class CommandParseException(CommandException):
    http_error = web.HTTPFailedDependency


class CommandBuildException(CommandException):
    http_error = web.HTTPBadRequest


class CRCFailed(CommandException):
    pass


class CommandTimeout(CommandException):
    http_error = web.HTTPFailedDependency


class UpdateInProgress(CommandException):
    http_error = web.HTTPFailedDependency


##################################################################################################
# Codec exceptions
##################################################################################################


class CodecException(BrewbloxException):
    pass


class EncodeException(CodecException):
    http_error = web.HTTPBadRequest


class DecodeException(CodecException):
    http_error = web.HTTPFailedDependency


class UnknownCodecType(CodecException):
    http_error = web.HTTPUnprocessableEntity


##################################################################################################
# Connection exceptions
##################################################################################################


class ConnectionException(BrewbloxException):
    http_error = web.HTTPFailedDependency


class NotConnected(ConnectionException):
    pass


class ConnectionImpossible(ConnectionException):
    pass


class ConnectionPaused(ConnectionException):
    pass


##################################################################################################
# Firmware exceptions
##################################################################################################

class FirmwareException(BrewbloxException):
    http_error = web.HTTPFailedDependency


class IncompatibleFirmware(FirmwareException):
    pass


class FirmwareUpdateFailed(FirmwareException):
    pass


class InvalidDeviceId(ConnectionException):
    pass
