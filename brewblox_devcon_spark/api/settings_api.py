"""
REST API for persistent settings
"""


import logging

from fastapi import APIRouter

from ..datastore import settings_store
from ..models import AutoconnectSettings

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/settings', tags=['Settings'])


@router.get('/autoconnecting')
async def settings_autoconnecting_get() -> AutoconnectSettings:
    """
    Get autoconnecting flag.
    """
    enabled = settings_store.CV.get().service_settings.autoconnecting
    return AutoconnectSettings(enabled=enabled)


@router.put('/autoconnecting')
async def settings_autoconnecting_put(args: AutoconnectSettings) -> AutoconnectSettings:
    """
    Set autoconnecting flag.
    """
    store = settings_store.CV.get()
    store.service_settings.autoconnecting = args.enabled
    await store.commit_service_settings()
    return AutoconnectSettings(enabled=args.enabled)
