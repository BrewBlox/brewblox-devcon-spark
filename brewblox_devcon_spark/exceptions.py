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
    pass


class CommandBuildException(CommandException):
    pass


class CRCFailed(CommandException):
    pass


##################################################################################################
# Codec exceptions
##################################################################################################


class CodecException(BrewBloxException):
    pass


class EncodeException(CodecException):
    pass


class DecodeException(CodecException):
    pass


##################################################################################################
# Connection exceptions
##################################################################################################


class ConnectionException(BrewBloxException):
    pass


class NotConnected(ConnectionException):
    pass
