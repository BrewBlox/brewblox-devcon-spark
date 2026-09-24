"""
Default exports for codec module
"""

import logging
from base64 import b64decode, b64encode
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

from google.protobuf import json_format
from google.protobuf.descriptor import Descriptor
from google.protobuf.message import Message
from google.protobuf.message_factory import GetMessageClass

from .. import exceptions, utils
from ..models import DecodedPayload, EncodedPayload, IntermediateRequest, IntermediateResponse, ReadMode
from . import bloxfield, descriptors, lookup, pb2, time_utils, unit_conversion
from .opts import DateFormatOpt
from .processor import ProtobufProcessor

UNKNOWN_TYPE_STR = 'UnknownType'
ERROR_TYPE_STR = 'ErrorObject'

LOGGER = logging.getLogger(__name__)
CV: ContextVar['Codec'] = ContextVar('codec.Codec')


class NeedFullRead(Exception):  # noqa: N818
    """
    A CHANGED payload can not be merged into the cached block.
    The cached data may be partially merged, and must be replaced by a full (DEFAULT) read.
    """


def _object_lookup(block_type: str) -> lookup.ObjectLookup | None:
    return lookup.CV_OBJECTS_BY_TYPE.get().get(block_type)


def _logged(nodes: Mapping[str, descriptors.LoggedNode], obj: dict, *, full: bool) -> dict:
    out = {}
    for key, node in nodes.items():
        if key not in obj or (node.skip_changed and not full):
            continue

        value = obj[key]

        if node.children is not None:
            if isinstance(value, list):
                out[key] = [_logged(node.children, v, full=full) for v in value]
            else:
                out[key] = _logged(node.children, value, full=full)

        elif bloxfield.is_quantity(value):
            out[f'{key}[{value["unit"]}]'] = value['value']

        elif bloxfield.is_link(value):
            out[f'{key}<{value["type"]}>'] = value['id']

        elif node.field.enum_type and isinstance(value, str):
            out[key] = node.field.enum_type.values_by_name[value].number

        elif descriptors.options(node.field).datetime:
            out[key] = time_utils.serialize_datetime(value, DateFormatOpt.SECONDS)

        else:
            out[key] = value

    return out


class Codec:
    def __init__(self, filter_values=True):
        self._processor = ProtobufProcessor(filter_values)

    def encode_request(self, request: IntermediateRequest) -> str:
        try:
            message = pb2.command_pb2.Request()
            json_format.ParseDict(request.model_dump(mode='json'), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_request(self, b64_encoded: str) -> IntermediateRequest:
        try:
            data = b''.join(b64decode(subs) for subs in b64_encoded.split(','))

            message = pb2.command_pb2.Request()
            message.ParseFromString(data)
            decoded: dict = json_format.MessageToDict(
                message=message,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
                use_integers_for_enums=False,
            )

            return IntermediateRequest(**decoded)

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_response(self, response: IntermediateResponse) -> str:
        try:
            message = pb2.command_pb2.Response()
            json_format.ParseDict(response.model_dump(mode='json'), message)
            return b64encode(message.SerializeToString()).decode()

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_response(self, b64_encoded: str) -> IntermediateResponse:
        try:
            data = b''.join(b64decode(subs) for subs in b64_encoded.split(','))

            message = pb2.command_pb2.Response()
            message.ParseFromString(data)
            decoded: dict = json_format.MessageToDict(
                message=message,
                preserving_proto_field_name=True,
                including_default_value_fields=True,
                use_integers_for_enums=False,
            )

            return IntermediateResponse(**decoded)

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.DecodeException(msg)

    def encode_payload(self, payload: DecodedPayload, filter_values: bool | None = None) -> EncodedPayload:
        try:
            # No encoding required
            if payload.blockType is None:
                return EncodedPayload(
                    blockId=payload.blockId,
                    name=payload.name,
                )

            try:
                # We use the numeric value to find a lookup
                # This lets us use name aliases that resolve to the same value
                block_type_value = lookup.BlockType.Value(payload.blockType)
            except ValueError:
                if payload.blockType == 'EdgeCase':
                    block_type_value = 9001
                else:
                    msg = f'Unknown block type: {payload.blockType}'
                    LOGGER.debug(msg, exc_info=True)
                    raise exceptions.EncodeException(msg)

            if payload.blockType == 'Deprecated':
                return EncodedPayload(
                    blockId=payload.blockId,
                    blockType=block_type_value,
                    name=payload.name,
                    content=payload.content['bytes'],
                )

            # Interface-only payload
            if payload.content is None:
                impl = next(
                    v
                    for v in lookup.CV_COMBINED.get()  # pragma: no branch
                    if v.type_int == block_type_value
                )
                return EncodedPayload(
                    blockId=payload.blockId,
                    blockType=impl.type_int,
                    name=payload.name,
                )

            # Payload contains data
            try:
                impl = next(
                    v
                    for v in lookup.CV_OBJECTS.get()  # pragma: no branch
                    if v.type_int == block_type_value
                )
            except StopIteration:
                msg = f'No codec entry found for {payload.blockType}'
                LOGGER.debug(msg, exc_info=True)
                raise exceptions.EncodeException(msg)

            message = impl.message_cls()
            payload = self._processor.pre_encode(
                message.DESCRIPTOR, payload.model_copy(deep=True), filter_values=filter_values
            )
            json_format.ParseDict(payload.content, message)
            content: str = b64encode(message.SerializeToString()).decode()

            return EncodedPayload(
                blockId=payload.blockId,
                blockType=impl.type_int,
                name=payload.name,
                content=content,
            )

        except exceptions.EncodeException:
            raise

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            raise exceptions.EncodeException(msg)

    def decode_payload(
        self,
        payload: EncodedPayload,
        /,
        mode: ReadMode = ReadMode.DEFAULT,
        filter_values: bool | None = None,
    ) -> DecodedPayload:
        try:
            if payload.blockType == lookup.BlockType.Value('Deprecated'):
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType='Deprecated',
                    name=payload.name,
                    content={'bytes': payload.content},
                )

            # First, try to find an object lookup
            impl = lookup.CV_OBJECTS_BY_TYPE.get().get(payload.blockType)

            if impl:
                # We have an object lookup, and can decode the content
                message = impl.message_cls()
                message.ParseFromString(b64decode(payload.content))
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=impl.type_str,
                    name=payload.name,
                    content=self._decode_message(message, mode, filter_values=filter_values),
                )

            # No object lookup found. Try the interfaces.
            intf_impl = next(
                (v for v in lookup.CV_INTERFACES.get() if payload.blockType in [v.type_str, v.type_int]), None
            )

            if intf_impl:
                return DecodedPayload(
                    blockId=payload.blockId,
                    blockType=intf_impl.type_str,
                    name=payload.name,
                )

            # No lookup of any kind found
            # We're decoding (returned) data, so would rather return a stub than raise an error
            msg = f'No codec entry found for {payload.blockType}'
            LOGGER.debug(msg, exc_info=True)
            return DecodedPayload(
                blockId=payload.blockId,
                blockType=UNKNOWN_TYPE_STR,
                name=payload.name,
                content={
                    'error': msg,
                },
            )

        except Exception as ex:
            msg = utils.strex(ex)
            LOGGER.debug(msg, exc_info=True)
            return DecodedPayload(
                blockId=payload.blockId,
                blockType=ERROR_TYPE_STR,
                name=payload.name,
                content={
                    'error': msg,
                    'blockType': payload.blockType,
                },
            )

    def _decode_message(self, message: Message, mode: ReadMode, *, filter_values: bool | None = None) -> dict:
        # A CHANGED read leaves out covered leaves that are zero.
        # Traversed messages are set present, so their covered leaves decode as (typed) defaults.
        if mode == ReadMode.CHANGED:
            for path in descriptors.traversed_messages(message.DESCRIPTOR):
                submessage = message
                for name in path:
                    submessage = getattr(submessage, name)
                submessage.SetInParent()

        content: dict = json_format.MessageToDict(
            message=message,
            preserving_proto_field_name=True,
            including_default_value_fields=True,
            use_integers_for_enums=(mode == ReadMode.STORED),
        )
        self._processor.fill(message.DESCRIPTOR, content, mode)
        decoded = DecodedPayload(blockId=0, content=content)
        return self._processor.post_decode(message.DESCRIPTOR, decoded, mode=mode, filter_values=filter_values).content

    def merge_changed(self, block_type: str, cached: dict, partial: dict) -> bool:
        """
        Merges `partial`, the decoded data of a CHANGED read, into `cached`, the decoded data of the same block.
        Both are typed data in API shape (as decoded, before link ids are resolved).
        `cached` is modified in place. Returns whether it changed.

        Along the coverage tree:
        * A covered value is set from `partial`, or deleted when absent there (omit_if_zero).
        * A covered list is replaced whole.
        * A traversed message is merged recursively. If it is missing from `cached`,
          it is skipped if its partial is all default, else NeedFullRead is raised.
        Then every uncovered key in `partial` that has presence on the wire
        (an optional leaf, or a list wrapper) is set: the firmware sent it.
        Other uncovered keys are decoded defaults (skip_changed fields), and are ignored.

        Stub types (UnknownType, ErrorObject, Deprecated) are replaced, never merged.
        """
        impl = _object_lookup(block_type)
        if impl is None:
            changed = cached != partial
            cached.clear()
            cached.update(partial)
            return changed

        return self._merge_changed(impl.message_cls.DESCRIPTOR, cached, partial)

    def _merge_changed(self, desc: Descriptor, cached: dict, partial: dict) -> bool:
        changed = False
        nodes = descriptors.coverage(desc)

        for key, node in nodes.items():
            if node.children is None:
                if key in partial:
                    if key not in cached or cached[key] != partial[key]:
                        cached[key] = partial[key]
                        changed = True
                elif key in cached:
                    del cached[key]
                    changed = True

            elif key not in partial:
                continue

            elif key in cached:
                sub_changed = self._merge_changed(node.field.message_type, cached[key], partial[key])
                changed = changed or sub_changed

            else:
                # The CHANGED read of the message with every covered leaf zero
                empty = GetMessageClass(node.field.message_type)()
                if partial[key] != self._decode_message(empty, ReadMode.CHANGED):
                    raise NeedFullRead(f'{desc.full_name}.{key} is not cached, and not default')

        for key, value in partial.items():
            if key in nodes:
                continue
            field = desc.fields_by_name[key]
            if not (descriptors.is_optional(field) or descriptors.list_wrapper(field)):
                continue
            if key not in cached or cached[key] != value:
                cached[key] = value
                changed = True

        return changed

    def logged_view(self, block_type: str, data: dict, /, *, full: bool) -> dict[str, Any]:
        """
        The history view of typed block data: logged fields only, with metadata in the keys.

        * Quantity -> `key[unit]: value`
        * Link -> `key<type>: id`
        * Enum name -> number
        * ISO-8601 datetime -> seconds since epoch (0 if not set)

        List elements are kept in position: an element without logged values is `{}`.
        With `full=False`, skip_changed fields are left out: CHANGED reads do not update them.
        Stub types have no logged fields.
        """
        impl = _object_lookup(block_type)
        if impl is None:
            return {}
        return _logged(descriptors.logged_fields(impl.message_cls.DESCRIPTOR), data, full=full)


def setup():
    lookup.setup()
    unit_conversion.setup()
    CV.set(Codec())


__all__ = [
    'Codec',
    'NeedFullRead',
    'setup',
    'CV',
    'ProtobufProcessor',
    # utils
    'bloxfield',
    'descriptors',
    'time_utils',
]
