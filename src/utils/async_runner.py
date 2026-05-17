# src/utils/async_runner.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

# Executor global para tareas pesadas (ej: parsear cientos de BND4)
_executor = ThreadPoolExecutor(max_workers=8)

async def run_in_background(func: Callable, *args, **kwargs) -> Any:
    """
    Ejecuta una función síncrona bloqueante en un ThreadPoolExecutor,
    devolviendo el control al event loop asíncrono.
    """
    loop = asyncio.get_running_loop()
    # functools.partial es necesario si hay kwargs
    from functools import partial
    call = partial(func, *args, **kwargs)
    return await loop.run_in_executor(_executor, call)