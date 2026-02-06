#!/usr/bin/env python3
"""
Tunnel Hill WTP — Live Web Dashboard Server

Serves a single-page dashboard over HTTP and pushes live data
via WebSocket at ~1 Hz. Runs as a thread inside the RTU bridge.

Requires: websockets (pip install websockets)
"""

import asyncio
import json
import logging
import os
import threading

import websockets
from http.server import HTTPServer, SimpleHTTPRequestHandler

log = logging.getLogger("Dashboard")

DASHBOARD_HTML_PATH = os.path.join(os.path.dirname(__file__), 'dashboard.html')


class DashboardServer:
    """
    Combined HTTP + WebSocket server for the live dashboard.

    HTTP serves dashboard.html on the main port.
    WebSocket runs on main port + 1 (e.g., 8081).
    """

    def __init__(self, bridge, port=8080):
        self.bridge = bridge
        self.http_port = port
        self.ws_port = port + 1
        self.clients = set()
        self._loop = None

    def start(self):
        """Start HTTP and WebSocket servers (blocking)."""
        # Start HTTP server in a sub-thread
        http_thread = threading.Thread(target=self._run_http, daemon=True)
        http_thread.start()

        # Run WebSocket server in asyncio event loop (blocking)
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_ws())

    def _run_http(self):
        """Serve dashboard.html via basic HTTP."""
        dashboard_dir = os.path.dirname(DASHBOARD_HTML_PATH) or '.'

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=dashboard_dir, **kwargs)

            def do_GET(self):
                if self.path == '/' or self.path == '/dashboard.html':
                    self.path = '/dashboard.html'
                super().do_GET()

            def log_message(self, format, *args):
                pass  # Suppress HTTP access logs

        server = HTTPServer(('0.0.0.0', self.http_port), Handler)
        log.info(f"HTTP server on port {self.http_port}")
        server.serve_forever()

    async def _run_ws(self):
        """WebSocket server: push data at 1 Hz, accept commands."""

        async def handler(websocket):
            self.clients.add(websocket)
            try:
                async for message in websocket:
                    # Handle commands from dashboard
                    try:
                        cmd = json.loads(message)
                        self._handle_command(cmd)
                    except json.JSONDecodeError:
                        pass
            finally:
                self.clients.discard(websocket)

        async with websockets.serve(handler, '0.0.0.0', self.ws_port):
            log.info(f"WebSocket server on port {self.ws_port}")
            # Push data loop
            while True:
                await asyncio.sleep(1)
                if self.clients:
                    try:
                        data = self.bridge.get_dashboard_data()
                        msg = json.dumps(data)
                        # Send to all connected clients
                        disconnected = set()
                        for ws in self.clients:
                            try:
                                await ws.send(msg)
                            except websockets.exceptions.ConnectionClosed:
                                disconnected.add(ws)
                        self.clients -= disconnected
                    except Exception as e:
                        log.debug(f"Dashboard push error: {e}")

    def _handle_command(self, cmd):
        """Process commands from the dashboard UI."""
        if not self.bridge.data_generator:
            return

        action = cmd.get('action')
        if action == 'rain':
            peak = cmd.get('peak', 400)
            self.bridge.data_generator.inject_event('rain', peak_turb=float(peak))
        elif action == 'dose_off':
            self.bridge.data_generator.inject_event('dose_off')
        elif action == 'dose_on':
            self.bridge.data_generator.inject_event('dose_on')
        elif action == 'fault':
            sensor = cmd.get('sensor', 'chlorine')
            self.bridge.data_generator.inject_event('fault', sensor=sensor)
        elif action == 'clear':
            sensor = cmd.get('sensor', 'chlorine')
            self.bridge.data_generator.inject_event('clear', sensor=sensor)
        elif action == 'glitch':
            self.bridge.data_generator.inject_event('glitch')
        elif action == 'set_coil':
            # Allow dashboard to toggle coils
            coil_idx = cmd.get('coil', 0)
            value = cmd.get('value', 0)
            self.bridge.store.setValues(1, coil_idx, [value])
