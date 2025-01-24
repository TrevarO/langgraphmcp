import asyncio
import weakref
from typing import Dict, Set, Optional
from asyncio.subprocess import Process
from contextlib import suppress
from src.langgraph_mcp.logging_config import cleanup_logger as logger
from src.langgraph_mcp.transport_manager import transport_manager

class CleanupManager:
    def __init__(self):
        self._processes: Dict[str, Process] = {}
        self._transports = weakref.WeakSet()
        self._cleanup_lock = asyncio.Lock()
        self._cleaning = False
        
    def register_process(self, name: str, process: Process) -> None:
        """Register a subprocess for cleanup"""
        self._processes[name] = process
        logger.debug(f"Registered process: {name}")
        
    def register_transport(self, transport) -> None:
        """Register a transport for cleanup"""
        self._transports.add(transport)
        if hasattr(transport, '_loop'):
            def cleanup_callback():
                self._transports.discard(transport)
            transport._loop.call_soon(cleanup_callback)
        logger.debug(f"Registered transport: {id(transport)}")

    async def cleanup_process(self, name: str, process: Process, timeout: float = 5.0) -> bool:
        """Cleanup a single process with timeout"""
        if process.returncode is not None:
            return True
            
        try:
            logger.debug(f"Terminating process: {name}")
            process.terminate()
            
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
                logger.debug(f"Process terminated gracefully: {name}")
                return True
            except asyncio.TimeoutError:
                logger.warning(f"Process kill required: {name}")
                process.kill()
                with suppress(Exception):
                    await process.wait()
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning up process {name}: {e}")
            return False

    async def cleanup_transport(self, transport, timeout: float = 2.0) -> bool:
        """Cleanup a single transport with timeout"""
        try:
            if not transport.is_closing():
                logger.debug(f"Closing transport: {id(transport)}")
                transport.close()
                if hasattr(transport, 'wait_closed'):
                    try:
                        await asyncio.wait_for(transport.wait_closed(), timeout=timeout)
                    except asyncio.TimeoutError:
                        pass
                return True
            return True
        except Exception as e:
            logger.error(f"Error cleaning up transport: {e}")
            return False

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Graceful shutdown sequence"""
        if self._cleaning:
            return
                
        async with self._cleanup_lock:
            try:
                self._cleaning = True
                logger.info("Starting cleanup sequence")
                
                # First cleanup transports
                await transport_manager.cleanup()
                
                # Then cleanup processes
                process_tasks = []
                for name, process in list(self._processes.items()):
                    task = asyncio.create_task(
                        self.cleanup_process(name, process, timeout)
                    )
                    process_tasks.append(task)
                    
                if process_tasks:
                    results = await asyncio.gather(*process_tasks, return_exceptions=True)
                    successes = sum(1 for r in results if isinstance(r, bool) and r)
                    logger.info(f"Process cleanup complete. Successes: {successes}/{len(process_tasks)}")
                    
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
            finally:
                self._cleaning = False
                logger.info("Cleanup sequence finished")

cleanup_manager = CleanupManager()