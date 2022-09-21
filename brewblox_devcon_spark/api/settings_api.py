"""
REST API for persistent settings
"""

from aiohttp import web
from aiohttp_pydantic import PydanticView
from aiohttp_pydantic.oas.typing import r200
from brewblox_service import brewblox_logger
from pydantic import BaseModel

from brewblox_devcon_spark import synchronization

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
        syncher = synchronization.fget(self.request.app)
        settings = AutoconnectSettings(
            enabled=syncher.get_autoconnecting()
        )
        return web.json_response(
            settings.dict()
        )

    async def put(self, args: AutoconnectSettings) -> r200[AutoconnectSettings]:
        """
        Set autoconnecting flag.

        Tags: Settings
        """
        syncher = synchronization.fget(self.request.app)
        settings = AutoconnectSettings(
            enabled=await syncher.set_autoconnecting(args.enabled)
        )
        return web.json_response(
            settings.dict()
        )
