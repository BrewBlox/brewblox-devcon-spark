"""
REST endpoints for persistent settings
"""

import logging

from fastapi import APIRouter

from .. import datastore_settings
from ..models import AutoconnectSettings

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix='/settings', tags=['Settings'])


@router.get('/enabled')
async def settings_enabled_get() -> AutoconnectSettings:
    """
    Get enabled flag.
    """
    enabled = datastore_settings.CV.get().service_settings.enabled
    return AutoconnectSettings(enabled=enabled)


@router.put('/enabled')
async def settings_enabled_put(args: AutoconnectSettings) -> AutoconnectSettings:
    """
    Set enabled flag.
    """
    store = datastore_settings.CV.get()
    store.service_settings.enabled = args.enabled
    await store.commit_service_settings()
    return AutoconnectSettings(enabled=args.enabled)
