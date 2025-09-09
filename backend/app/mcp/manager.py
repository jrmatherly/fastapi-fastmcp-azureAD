"""
MCP Server Manager - Background process management for MCP servers.

This module handles starting, stopping, and monitoring multiple MCP servers
as background processes from within the main FastAPI application.
"""

import asyncio
import logging
import signal
import subprocess
import sys

import psutil

logger = logging.getLogger(__name__)


class MCPServerManager:
    """Manages multiple MCP servers as background processes."""

    def __init__(self):
        self.processes: dict[str, subprocess.Popen] = {}
        self.server_configs = {
            "weather": {
                "module": "app.mcp.weather_server:app",
                "port": 8001,
                "description": "Weather MCP Server with Azure AD",
            },
            # Add future servers here
            # "finance": {
            #     "module": "app.mcp.finance_server:app",
            #     "port": 8002,
            #     "description": "Finance MCP Server"
            # }
        }

    async def start_server(self, server_name: str) -> bool:
        """Start a specific MCP server."""
        if server_name not in self.server_configs:
            logger.error(f"Unknown server: {server_name}")
            return False

        if server_name in self.processes:
            logger.warning(f"Server {server_name} already running")
            return True

        config = self.server_configs[server_name]

        try:
            # Build uvicorn command
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                config["module"],
                "--host",
                "0.0.0.0",
                "--port",
                str(config["port"]),
                "--reload",
            ]

            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=None
                if sys.platform == "win32"
                else lambda: signal.signal(signal.SIGINT, signal.SIG_IGN),
            )

            self.processes[server_name] = process
            logger.info(
                f"✅ Started MCP server '{server_name}' on port {config['port']} (PID: {process.pid})"
            )

            # Give it a moment to start
            await asyncio.sleep(2)

            # Check if it's still running
            if process.poll() is None:
                return True
            else:
                logger.error(f"❌ MCP server '{server_name}' failed to start")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to start MCP server '{server_name}': {e}")
            return False

    async def stop_server(self, server_name: str) -> bool:
        """Stop a specific MCP server."""
        if server_name not in self.processes:
            logger.warning(f"Server {server_name} not running")
            return True

        process = self.processes[server_name]

        try:
            # Graceful shutdown
            if sys.platform != "win32":
                process.send_signal(signal.SIGTERM)
            else:
                process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown failed
                process.kill()
                process.wait()

            del self.processes[server_name]
            logger.info(f"✅ Stopped MCP server '{server_name}'")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to stop MCP server '{server_name}': {e}")
            return False

    async def start_all_servers(self) -> dict[str, bool]:
        """Start all configured MCP servers."""
        results = {}
        for server_name in self.server_configs:
            results[server_name] = await self.start_server(server_name)
        return results

    async def stop_all_servers(self) -> dict[str, bool]:
        """Stop all running MCP servers."""
        results = {}
        for server_name in list(self.processes.keys()):
            results[server_name] = await self.stop_server(server_name)
        return results

    def get_server_status(self) -> dict[str, dict]:
        """Get status of all MCP servers."""
        status = {}

        for server_name, config in self.server_configs.items():
            if server_name in self.processes:
                process = self.processes[server_name]
                if process.poll() is None:
                    # Process is running
                    try:
                        proc = psutil.Process(process.pid)
                        status[server_name] = {
                            "status": "running",
                            "pid": process.pid,
                            "port": config["port"],
                            "description": config["description"],
                            "cpu_percent": proc.cpu_percent(),
                            "memory_mb": proc.memory_info().rss / 1024 / 1024,
                            "uptime_seconds": proc.create_time(),
                        }
                    except psutil.NoSuchProcess:
                        status[server_name] = {
                            "status": "dead",
                            "port": config["port"],
                            "description": config["description"],
                        }
                else:
                    # Process has terminated
                    status[server_name] = {
                        "status": "terminated",
                        "exit_code": process.poll(),
                        "port": config["port"],
                        "description": config["description"],
                    }
                    # Clean up dead process
                    del self.processes[server_name]
            else:
                status[server_name] = {
                    "status": "stopped",
                    "port": config["port"],
                    "description": config["description"],
                }

        return status


# Global manager instance
mcp_manager = MCPServerManager()


# FastAPI integration functions
async def startup_mcp_servers():
    """Startup function to be called from FastAPI lifespan."""
    logger.info("🚀 Starting MCP servers...")
    results = await mcp_manager.start_all_servers()

    for server_name, success in results.items():
        if success:
            logger.info(f"✅ MCP server '{server_name}' started successfully")
        else:
            logger.error(f"❌ Failed to start MCP server '{server_name}'")


async def shutdown_mcp_servers():
    """Shutdown function to be called from FastAPI lifespan."""
    logger.info("🔄 Shutting down MCP servers...")
    results = await mcp_manager.stop_all_servers()

    for server_name, success in results.items():
        if success:
            logger.info(f"✅ MCP server '{server_name}' stopped successfully")
        else:
            logger.error(f"❌ Failed to stop MCP server '{server_name}'")
