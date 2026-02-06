# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Water treatment plant process simulator modelled on the Tunnel Hill WTP (Cairns Regional Council). Generates realistic correlated process data and exposes it as Modbus TCP registers — designed as a data source for SCADA development, Ignition training, and learning industrial protocols. Three-layer architecture modelling the real plant that treats water from Copperlode Falls Dam for 165,000+ residents.

## Architecture

Three-layer system mirroring real industrial control architecture:

1. **Process Simulator** (`wtp_process_sim.py`) — Ornstein-Uhlenbeck mean-reverting random walks for sensor noise, diurnal demand curves for flow, sawtooth chlorine dosing model, and correlated rain events (turbidity spike + pH drop + flow increase + temp dip). Rain events fire automatically via Poisson process or can be triggered interactively. Virtual clock supports time compression via `--speed`.

2. **Python RTU Bridge** (`rtu_bridge.py`) — Middleman simulating a SCADAPack RTU. Runs process simulation logic (`WTPSimulator` class), exposes data as Modbus TCP registers using `ProcessDataGenerator` from `wtp_process_sim.py` for realistic correlated sensor data with rain events, diurnal patterns, and time compression.

3. **Web Dashboard** (`dashboard.py` + `dashboard.html`) — HTTP server + WebSocket pushing data at 1 Hz. Single HTML file with Chart.js via CDN. Shows live gauges, rolling time-series, plant state machine, alarm panel, and scenario/coil control buttons. HTTP on `--dashboard-port` (default 8080), WebSocket on port+1.

4. **Ignition SCADA** (external, not in repo) — Connects to the RTU bridge via Modbus TCP. Provides HMI screens, alarm management, historian, and trend displays.

## Running

```bash
# Install dependencies
pip install pymodbus websockets

# Quickest way to see it working
python rtu_bridge.py --speed 60 --modbus-port 5020
# Then open http://localhost:8080

# All options
python rtu_bridge.py --speed 60 --seed 42 --no-auto-events --modbus-port 5020 --dashboard-port 9000
```

## Key Implementation Details

**Modbus register scaling:** All analog values are scaled to 16-bit unsigned integers. The scale factors (x10, x100) are defined in `register_map.md` and must match between `rtu_bridge.py` (where values are written) and Ignition tag configuration (where they're scaled back). For example, turbidity 234.5 NTU is stored as register value 2345 (x10).

**Plant status state machine** in `WTPSimulator.tick()`: Offline(0) -> Starting(1) -> Running(2) -> Shutdown(3), with Backwash(4) and Fault(5) branches. Auto-mode + intake command + no turbidity shutdown transitions forward; turbidity >500 NTU forces shutdown (real Tunnel Hill behaviour during wet season).

**Alarm word** (Input Register 30003): Bitfield where each bit maps to a specific alarm condition. Bit definitions are in `register_map.md`.

**Threading model** in `RTUBridge`: Five concurrent threads — data reader, process logic (1s scan cycle), command writer (0.5s poll for coil changes), stdin command loop (interactive scenario control), and the dashboard server (HTTP + WebSocket). The pymodbus TCP server runs on the main thread.

**Sensor models** in `wtp_process_sim.py` all use `OUProcess` (Ornstein-Uhlenbeck). The `ProcessDataGenerator.tick()` method advances the virtual clock by `wall_dt * speed`, computes all sensor values, applies rain event contributions, and returns a dict with all simulated sensor values.

**pymodbus compatibility:** The imports handle both pymodbus 2.x (`ModbusSlaveContext`, `pymodbus.device`) and 3.x (`ModbusDeviceContext`, top-level import) APIs.

## File Layout

- `rtu_bridge.py` — Python RTU bridge (the main runnable component)
- `wtp_process_sim.py` — Realistic process data generator
- `dashboard.py` — Web dashboard server (HTTP + WebSocket)
- `dashboard.html` — Single-file dashboard UI (Chart.js via CDN)
- `register_map.md` — Modbus register map (addresses, scaling, function codes)

- `*.svg` — Architecture, tag structure, and process flow diagrams
