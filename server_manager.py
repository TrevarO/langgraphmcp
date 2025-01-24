import asyncio
import signal
import sys
import weakref
from contextlib import asynccontextmanager, suppress
from typing import Dict, Optional
from asyncio.subprocess import Process
from src.langgraph_mcp.cleanup_manager import cleanup_manager
from src.langgraph_mcp.logging_config import cleanup_logger as logger

class ServerManager:
    def __init__(self):
        self.active_servers = weakref.WeakSet()
        self.processes: Dict[str, Process] = {}
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def add_server(self, name: str, coro) -> asyncio.Task:
        """Add a new server task"""
        async with self._lock:
            try:
                task = asyncio.create_task(coro)
                self.active_servers.add(task)
                return task
            except Exception as e:
                logger.error(f"Failed to add server {name}: {e}")
                raise

    async def create_server_process(self, name: str, cmd: list, env: dict) -> Process:
        """Create and register a server process"""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        self.processes[name] = process
        cleanup_manager.register_process(name, process)
        return process

    async def shutdown(self, timeout: float = 5.0):
        """Graceful shutdown"""
        if not self.active_servers and not self.processes:
            return

        logger.info(f"Shutting down {len(self.active_servers)} servers...")
        await cleanup_manager.shutdown(timeout)

server_manager = ServerManager()

@asynccontextmanager
async def manage_event_loop():
    """Enhanced event loop management"""
    loop = asyncio.get_event_loop()
    
    def handle_sigint():
        logger.info("Received interrupt signal")
        asyncio.create_task(server_manager.shutdown())
    
    try:
        if sys.platform == "win32":
            current_limit = sys.getrecursionlimit()
            target_limit = max(current_limit, 3000)
            sys.setrecursionlimit(target_limit)
        else:
            loop.add_signal_handler(signal.SIGINT, handle_sigint)
        
        logger.info("Event loop setup complete")
        yield loop
        
    finally:
        logger.info("Starting event loop cleanup")
        try:
            await server_manager.shutdown()
            
            pending = [t for t in asyncio.all_tasks(loop) 
                      if t is not asyncio.current_task()]
                      
            if pending:
                logger.info(f"Cancelling {len(pending)} remaining tasks")
                for task in pending:
                    task.cancel()
                
                with suppress(asyncio.CancelledError):
                    await asyncio.gather(*pending, return_exceptions=True)
                    
        except Exception as e:
            logger.error(f"Error during event loop cleanup: {e}")
            
        logger.info("Event loop cleanup complete")