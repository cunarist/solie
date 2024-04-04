import asyncio
import sys

from solie.common import prepare_process_pool

from .lifetime import live


def bring_to_life():
    prepare_process_pool()
    asyncio.run(live())
    sys.exit()
