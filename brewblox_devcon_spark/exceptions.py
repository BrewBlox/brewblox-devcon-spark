"""
Lists various possible BrewBlox-related exceptions.
This improves clarity as to what actually went wrong.
"""


class BrewBloxException(Exception):
    status_code = 500


##################################################################################################
# Generic exceptions
##################################################################################################


class InvalidInput(BrewBloxException):
    status_code = 400  # HTTP bad request


class MissingInput(InvalidInput):
    pass


##################################################################################################
# ID exceptions
##################################################################################################


class IdException(BrewBloxException):
    status_code = 400  # HTTP bad request


class InvalidId(IdException):
    pass


class ExistingId(IdException):
    status_code = 409  # HTTP conflict


class UnknownId(IdException):
    pass


##################################################################################################
# Command exceptions
##################################################################################################


class CommandException(BrewBloxException):
    pass


class CommandParseException(CommandException):
    status_code = 424  # HTTP failed dependency


class CommandBuildException(CommandException):
    status_code = 400  # HTTP bad request


class CRCFailed(CommandException):
    pass


class CommandTimeout(CommandException):
    status_code = 424  # HTTP failed dependency


##################################################################################################
# Codec exceptions
##################################################################################################


class CodecException(BrewBloxException):
    pass


class EncodeException(CodecException):
    status_code = 400  # HTTP bad request


class DecodeException(CodecException):
    status_code = 424  # HTTP failed dependency


class UnknownCodecType(CodecException):
    status_code = 422  # HTTP unprocessable entity


##################################################################################################
# Connection exceptions
##################################################################################################


class ConnectionException(BrewBloxException):
    status_code = 424  # HTTP failed dependency


class NotConnected(ConnectionException):
    pass


class ConnectionImpossible(ConnectionException):
    pass
