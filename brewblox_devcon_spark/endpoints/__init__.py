"""
Namespace for all REST API modules.
"""

from fastapi import APIRouter

from . import (http_backup, http_blocks, http_debug, http_settings, http_sim,
               http_system, mqtt_blocks)

routers: list[APIRouter] = [
    http_backup.router,
    http_blocks.router,
    http_debug.router,
    http_settings.router,
    http_sim.router,
    http_system.router,
]


def setup():
    mqtt_blocks.setup()
