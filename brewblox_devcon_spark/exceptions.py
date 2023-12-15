"""
Lists various possible BrewBlox-related exceptions.
This improves clarity as to what actually went wrong.
"""


from fastapi import HTTPException, status


class BrewbloxException(HTTPException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, msg: str) -> None:
        super().__init__(status_code=self.__class__.status_code,
                         detail=msg)


##################################################################################################
# Generic exceptions
##################################################################################################


class InvalidInput(BrewbloxException):
    status_code = status.HTTP_400_BAD_REQUEST


class MissingInput(InvalidInput):
    pass


##################################################################################################
# ID exceptions
##################################################################################################


class IdException(BrewbloxException):
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidId(IdException):
    pass


class ExistingId(IdException):
    status_code = status.HTTP_409_CONFLICT


class UnknownId(IdException):
    pass


##################################################################################################
# Command exceptions
##################################################################################################


class CommandException(BrewbloxException):
    pass


class CommandParseException(CommandException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY


class CommandBuildException(CommandException):
    status_code = status.HTTP_400_BAD_REQUEST


class CRCFailed(CommandException):
    pass


class CommandTimeout(CommandException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY


class UpdateInProgress(CommandException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY


##################################################################################################
# Codec exceptions
##################################################################################################


class CodecException(BrewbloxException):
    pass


class EncodeException(CodecException):
    status_code = status.HTTP_400_BAD_REQUEST


class DecodeException(CodecException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY


class UnknownCodecType(CodecException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


##################################################################################################
# Connection exceptions
##################################################################################################


class ConnectionException(BrewbloxException):
    status_code = status.HTTP_424_FAILED_DEPENDENCY


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
    status_code = status.HTTP_424_FAILED_DEPENDENCY


class IncompatibleFirmware(FirmwareException):
    pass


class FirmwareUpdateFailed(FirmwareException):
    pass


class InvalidDeviceId(ConnectionException):
    pass
