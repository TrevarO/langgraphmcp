import asyncio
import weakref
from typing import Set, Dict, Optional
import logging
from contextlib import suppress

logger = logging.getLogger(__name__)

class TransportManager:
    def __init__(self):
        self._transports: Set = set()
        self._closing = False
        self._lock = asyncio.Lock()
        
    def register(self, transport) -> None:
        """Register a transport for cleanup"""
        if transport is None:
            return
            
        self._transports.add(transport)
        logger.debug(f"Registered transport: {id(transport)}")
        
    def unregister(self, transport) -> None:
        """Unregister a transport"""
        with suppress(KeyError):
            self._transports.remove(transport)
            logger.debug(f"Unregistered transport: {id(transport)}")
            
    async def close_transport(self, transport, timeout: float = 2.0) -> bool:
        """Close a single transport with timeout"""
        try:
            if hasattr(transport, 'is_closing') and not transport.is_closing():
                transport.close()
                if hasattr(transport, 'wait_closed'):
                    try:
                        await asyncio.wait_for(transport.wait_closed(), timeout)
                    except asyncio.TimeoutError:
                        logger.warning(f"Transport {id(transport)} close timeout")
                return True
            return True
        except Exception as e:
            logger.error(f"Error closing transport {id(transport)}: {e}")
            return False
            
    async def cleanup(self, timeout: float = 5.0) -> None:
        """Clean up all transports"""
        if self._closing:
            return
            
        async with self._lock:
            try:
                self._closing = True
                if not self._transports:
                    return
                    
                logger.info(f"Cleaning up {len(self._transports)} transports")
                close_tasks = []
                
                for transport in list(self._transports):
                    if transport is not None:
                        task = asyncio.create_task(
                            self.close_transport(transport, timeout/2)
                        )
                        close_tasks.append(task)
                        
                if close_tasks:
                    results = await asyncio.gather(*close_tasks, return_exceptions=True)
                    successes = sum(1 for r in results if isinstance(r, bool) and r)
                    logger.info(f"Transport cleanup complete. Successes: {successes}/{len(close_tasks)}")
                    
            except Exception as e:
                logger.error(f"Transport cleanup error: {e}")
            finally:
                self._closing = False
                self._transports.clear()

transport_manager = TransportManager()