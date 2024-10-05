"""
REST endpoints for persistent settings
"""

import logging

from fastapi import APIRouter

from .. import datastore_settings
from ..models import AutoconnectSettings
from .. import state_machine

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
    store.service_settings.enabled = args.enabled # update local settings
    state_machine.CV.get().set_enabled(args.enabled) # apply settings
    await store.commit_service_settings() # commit local settings to datastore
    # change event from MQTT will come in, but settings are the same and callbacks will be skipped.
    # if we would only apply on MQTT event, toggling enabled would depend on round trip through the datastore and eventbus.
    return AutoconnectSettings(enabled=args.enabled)
