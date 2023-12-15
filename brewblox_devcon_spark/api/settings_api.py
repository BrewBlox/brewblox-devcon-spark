"""
REST API for persistent settings
"""


import logging

from fastapi import APIRouter

from .. import service_status, service_store
from ..models import AutoconnectSettings

LOGGER = logging.getLogger(__name__)


router = APIRouter(prefix='/settings', tags=['Settings'])


@router.get('/autoconnecting')
async def settings_autoconnecting_get() -> AutoconnectSettings:
    """
    Get autoconnecting flag.
    """
    with service_store.CV.get().open() as data:
        enabled = data.autoconnecting
    return AutoconnectSettings(enabled=enabled)


@router.put('/autoconnecting')
async def settings_autoconnecting_put(args: AutoconnectSettings) -> AutoconnectSettings:
    """
    Set autoconnecting flag.
    """
    service_status.CV.get().set_enabled(args.enabled)
    with service_store.CV.get().open() as data:
        data.autoconnecting = args.enabled
    return AutoconnectSettings(enabled=args.enabled)
