"""
REST API for persistent settings
"""


import logging

from fastapi import APIRouter

from ..datastore import settings_store
from ..models import AutoconnectSettings

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/settings', tags=['Settings'])


@router.get('/enabled')
async def settings_enabled_get() -> AutoconnectSettings:
    """
    Get enabled flag.
    """
    enabled = settings_store.CV.get().service_settings.enabled
    return AutoconnectSettings(enabled=enabled)


@router.put('/enabled')
async def settings_enabled_put(args: AutoconnectSettings) -> AutoconnectSettings:
    """
    Set enabled flag.
    """
    store = settings_store.CV.get()
    store.service_settings.enabled = args.enabled
    await store.commit_service_settings()
    return AutoconnectSettings(enabled=args.enabled)
