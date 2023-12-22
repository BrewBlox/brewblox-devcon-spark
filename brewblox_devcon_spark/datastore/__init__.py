from contextlib import AsyncExitStack, asynccontextmanager

from . import block_store, settings_store


@asynccontextmanager
async def lifespan():
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(settings_store.lifespan())
        await stack.enter_async_context(block_store.lifespan())
        yield


def setup():
    settings_store.setup()
    block_store.setup()
