"""
REST API for persistent settings
"""

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger
from pydantic import BaseModel

from brewblox_devcon_spark import service_status, service_store

LOGGER = brewblox_logger(__name__)
routes = web.RouteTableDef()


def setup(app: web.Application):
    app.router.add_routes(routes)


class AutoconnectSettings(BaseModel):
    enabled: bool


@routes.view('/settings/autoconnecting')
class AutoconnectingView(PydanticView):
    async def get(self) -> r200[AutoconnectSettings]:
        """
        Get autoconnecting flag.

        Tags: Settings
        """
        enabled = service_store.get_autoconnecting(self.request.app)
        settings = AutoconnectSettings(enabled=enabled)
        return web.json_response(
            settings.dict()
        )

    async def put(self, args: AutoconnectSettings) -> r200[AutoconnectSettings]:
        """
        Set autoconnecting flag.

        Tags: Settings
        """
        enabled = service_store.set_autoconnecting(self.request.app,
                                                   args.enabled)
        service_status.set_enabled(self.request.app, enabled)
        settings = AutoconnectSettings(enabled=enabled)
        return web.json_response(
            settings.dict()
        )
