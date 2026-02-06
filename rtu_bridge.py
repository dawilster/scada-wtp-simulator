#!/usr/bin/env python3
"""
Tunnel Hill WTP — RTU/PLC Bridge

Generates realistic process data via simulation, exposes as Modbus TCP
registers, runs plant state machine and alarm logic.

This simulates what a SCADAPack 300 series RTU or Schneider
Modicon M340 PLC would do at the real Tunnel Hill plant.

Usage:
    python rtu_bridge.py --speed 60 --modbus-port 5020
"""

import argparse
import threading
import time
import logging

from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusServerContext,
    ModbusSequentialDataBlock,
)
# pymodbus 3.x renamed ModbusSlaveContext to ModbusDeviceContext
try:
    from pymodbus.datastore import ModbusSlaveContext
except ImportError:
    from pymodbus.datastore import ModbusDeviceContext as ModbusSlaveContext

try:
    from pymodbus.device import ModbusDeviceIdentification
except ImportError:
    from pymodbus import ModbusDeviceIdentification

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger("RTU_Bridge")

# ═══════════════════════════════════════════════════════════
# REGISTER CONFIGURATION
# ═══════════════════════════════════════════════════════════

# Data block sizes (address 0 is unused, real addresses start at 1)
NUM_COILS = 20             # 00001-00020
NUM_DISCRETE_INPUTS = 20   # 10001-10020
NUM_INPUT_REGISTERS = 20   # 30001-30020
NUM_HOLDING_REGISTERS = 30 # 40001-40030

# Holding register offsets (0-indexed internally, maps to 40001+)
HR_TURB_RAW = 0        # 40001
HR_TURB_FILTERED = 1   # 40002
HR_PH = 2              # 40003
HR_CL2 = 3             # 40004
HR_FLOW_RAW = 4        # 40005
HR_FLOW_TREATED = 5    # 40006
HR_LEVEL_PCT = 6       # 40007
HR_TEMP = 7            # 40008
HR_ALUM_DOSE = 8       # 40009
HR_FILTER_DP = 9       # 40010
HR_DAM_RELEASE = 10    # 40011
HR_LEVEL_CM = 11       # 40012
HR_BW_COUNT = 12       # 40013
HR_TOTAL_FLOW = 13     # 40014
HR_RUNTIME = 14        # 40015

# Coil offsets (0-indexed, maps to 00001+)
CO_INTAKE_CMD = 0      # 00001
CO_ALUM_CMD = 1        # 00002
CO_CL2_CMD = 2         # 00003
CO_BW_CMD = 3          # 00004
CO_AUTO_MODE = 4       # 00005
CO_ESTOP = 5           # 00006
CO_ALARM_ACK = 6       # 00007
CO_TURB_SHUTDOWN = 7   # 00008

# Discrete input offsets (0-indexed, maps to 10001+)
DI_INTAKE_RUN = 0      # 10001
DI_ALUM_RUN = 1        # 10002
DI_CL2_RUN = 2         # 10003
DI_BW_OPEN = 3         # 10004
DI_LEVEL_HIGH = 4      # 10005
DI_LEVEL_LOW = 5       # 10006
DI_BW_ACTIVE = 6       # 10007
DI_ALM_TURB = 7        # 10008
DI_ALM_CL2 = 8         # 10009
DI_COMM_FAULT = 9      # 10010

# Input register offsets
IR_TURB_BACKUP = 0     # 30001
IR_PLANT_STATUS = 1    # 30002
IR_ALARM_WORD = 2      # 30003


class WTPSimulator:
    """
    Process simulation logic for the water treatment plant.
    
    In the real world, this logic runs in the PLC/RTU.
    It handles:
    - Automatic turbidity shutdown (the plant auto-shuts when turbidity
      exceeds safe levels — this is a REAL behaviour at Tunnel Hill)
    - Filter differential pressure simulation
    - Filtered turbidity calculation
    - Treated flow calculation
    - Alarm generation
    """
    
    def __init__(self):
        self.filter_dp = 0.0          # Filter differential pressure (kPa)
        self.filtered_turbidity = 0.0  # Post-filtration turbidity
        self.treated_flow = 0.0        # Treated water flow
        self.backwash_count = 0
        self.total_flow_ml = 0.0       # Totaliser (megalitres)
        self.runtime_hours = 0.0
        self.plant_status = 0          # 0=Offline
        self.last_tick = time.time()
        
        # Alarm setpoints (these are configurable in real SCADA)
        self.TURB_RAW_HIGH = 500.0      # NTU - auto shutdown threshold
        self.TURB_RAW_WARNING = 200.0   # NTU - warning level
        self.TURB_FILTERED_HIGH = 1.0   # NTU - filtered water alarm
        self.CL2_LOW = 0.2              # mg/L - minimum chlorine residual
        self.CL2_HIGH = 4.0             # mg/L - maximum chlorine
        self.PH_LOW = 6.5
        self.PH_HIGH = 8.5
        self.LEVEL_HIGH = 95.0          # % - reservoir high
        self.LEVEL_LOW = 20.0           # % - reservoir low
        self.FILTER_DP_HIGH = 150.0     # kPa - needs backwash
        
    def tick(self, sensor_data, coils):
        """
        Called every scan cycle. Processes sensor data, runs control
        logic, returns updated values.
        """
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now
        
        turb_raw = sensor_data.get('turb_raw', 0)
        ph = sensor_data.get('ph', 7.0)
        cl2 = sensor_data.get('cl2', 0)
        flow_raw = sensor_data.get('flow_raw', 0)
        level_pct = sensor_data.get('level_pct', 50)
        
        is_auto = coils[CO_AUTO_MODE]
        is_estop = coils[CO_ESTOP]
        intake_cmd = coils[CO_INTAKE_CMD]
        
        # ─── EMERGENCY STOP ───
        if is_estop:
            self.plant_status = 0  # Offline
            return self._build_result(turb_raw, ph, cl2, flow_raw, level_pct)
        
        # ─── HIGH TURBIDITY AUTO-SHUTDOWN ───
        # This is the real behaviour! The Tunnel Hill plant
        # automatically shuts down when raw turbidity exceeds safe
        # levels. Staff must then manually restart.
        turb_shutdown = turb_raw > self.TURB_RAW_HIGH
        
        if turb_shutdown and self.plant_status == 2:
            self.plant_status = 3  # Shutdown
            log.warning(f"HIGH TURBIDITY SHUTDOWN: {turb_raw:.0f} NTU > {self.TURB_RAW_HIGH} NTU")
        
        # ─── PLANT STATUS MACHINE ───
        if is_auto and intake_cmd and not turb_shutdown:
            if self.plant_status in [0, 3]:
                self.plant_status = 1  # Starting
            elif self.plant_status == 1:
                self.plant_status = 2  # Running (after a brief start)
        elif not intake_cmd or turb_shutdown:
            if self.plant_status == 2:
                self.plant_status = 3  # Shutdown
        
        # ─── PROCESS SIMULATION ───
        if self.plant_status == 2:  # Running
            # Filter removes turbidity: typical 99%+ removal
            # Real: raw 2.5-1000 NTU → filtered 0.02 NTU
            removal_efficiency = 0.98 if self.filter_dp < self.FILTER_DP_HIGH else 0.90
            self.filtered_turbidity = turb_raw * (1 - removal_efficiency)
            
            # Filter DP slowly increases (simulates filter loading)
            self.filter_dp += 0.1 * dt  # Slow increase
            
            # Treated flow = raw flow * plant efficiency
            self.treated_flow = flow_raw * 0.95  # 5% loss to backwash/waste
            
            # Totaliser
            self.total_flow_ml += (self.treated_flow * dt) / 1_000_000  # L/s → ML
            
            # Runtime counter
            self.runtime_hours += dt / 3600.0
        else:
            self.filtered_turbidity = 0
            self.treated_flow = 0
        
        # ─── BACKWASH SIMULATION ───
        if coils[CO_BW_CMD] and self.plant_status == 2:
            self.plant_status = 4  # Backwash mode
            self.filter_dp = max(0, self.filter_dp - 5.0 * dt)
            if self.filter_dp < 5.0:
                self.backwash_count += 1
                self.filter_dp = 0
        
        # ─── ALARM GENERATION ───
        alarm_word = 0
        if turb_raw > self.TURB_RAW_WARNING:   alarm_word |= (1 << 0)
        if self.filtered_turbidity > self.TURB_FILTERED_HIGH: alarm_word |= (1 << 1)
        if cl2 < self.CL2_LOW:                 alarm_word |= (1 << 2)
        if ph > self.PH_HIGH:                  alarm_word |= (1 << 3)
        if ph < self.PH_LOW:                   alarm_word |= (1 << 4)
        if level_pct > self.LEVEL_HIGH:        alarm_word |= (1 << 5)
        if level_pct < self.LEVEL_LOW:         alarm_word |= (1 << 6)
        
        return self._build_result(
            turb_raw, ph, cl2, flow_raw, level_pct,
            alarm_word, turb_shutdown
        )
    
    def _build_result(self, turb_raw, ph, cl2, flow_raw, level_pct,
                      alarm_word=0, turb_shutdown=False):
        return {
            'turb_raw': turb_raw,
            'turb_filtered': self.filtered_turbidity,
            'ph': ph,
            'cl2': cl2,
            'flow_raw': flow_raw,
            'flow_treated': self.treated_flow,
            'level_pct': level_pct,
            'filter_dp': self.filter_dp,
            'plant_status': self.plant_status,
            'alarm_word': alarm_word,
            'backwash_count': self.backwash_count,
            'total_flow_ml': self.total_flow_ml,
            'runtime_hours': self.runtime_hours,
            'turb_shutdown': turb_shutdown,
        }


class RTUBridge:
    """
    Main bridge between process simulator and SCADA (Modbus TCP).
    """

    def __init__(self, modbus_port=502,
                 speed=1.0, seed=None, auto_events=True, dashboard_port=8080):
        self.modbus_port = modbus_port
        self.dashboard_port = dashboard_port
        self.simulator = WTPSimulator()
        self.latest_sensor_data = {}
        self.running = True
        self.data_generator = None
        self.speed = speed
        self.seed = seed
        self.auto_events = auto_events
        
        # Build Modbus data store
        # pymodbus uses 0-indexed internally
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * (NUM_DISCRETE_INPUTS + 1)),
            co=ModbusSequentialDataBlock(0, [0] * (NUM_COILS + 1)),
            hr=ModbusSequentialDataBlock(0, [0] * (NUM_HOLDING_REGISTERS + 1)),
            ir=ModbusSequentialDataBlock(0, [0] * (NUM_INPUT_REGISTERS + 1)),
        )
        self.context = ModbusServerContext(devices=self.store, single=True)
    
    def start(self):
        """Start all threads and the Modbus server."""
        # Create the realistic data generator
        from wtp_process_sim import ProcessDataGenerator
        self.data_generator = ProcessDataGenerator(
            speed=self.speed, seed=self.seed, auto_events=self.auto_events,
        )
        log.info(f"Simulator active: speed={self.speed}x, "
                 f"seed={self.seed}, auto_events={self.auto_events}")

        # Start data reader thread
        data_thread = threading.Thread(target=self._data_reader, daemon=True)
        data_thread.start()

        # Start process logic thread
        logic_thread = threading.Thread(target=self._process_logic, daemon=True)
        logic_thread.start()

        # Start command writer thread
        cmd_thread = threading.Thread(target=self._command_writer, daemon=True)
        cmd_thread.start()

        # Start interactive stdin thread and dashboard
        stdin_thread = threading.Thread(target=self._stdin_command_loop, daemon=True)
        stdin_thread.start()

        try:
            from dashboard import DashboardServer
            self._dashboard = DashboardServer(
                bridge=self, port=self.dashboard_port,
            )
            dash_thread = threading.Thread(target=self._dashboard.start, daemon=True)
            dash_thread.start()
            log.info(f"Dashboard: http://localhost:{self.dashboard_port}")
        except Exception as e:
            log.warning(f"Dashboard not started: {e}")
        
        # Start Modbus TCP server (blocks)
        identity = ModbusDeviceIdentification()
        identity.VendorName = 'Tunnel Hill WTP'
        identity.ProductCode = 'RTU-SIM'
        identity.ProductName = 'WTP RTU Simulator'
        identity.ModelName = 'SCADAPack-SIM'
        
        log.info(f"Starting Modbus TCP server on port {self.modbus_port}")
        log.info("Connect Ignition to localhost:502, Unit ID 1")
        log.info("=" * 60)
        
        StartTcpServer(
            context=self.context,
            identity=identity,
            address=("0.0.0.0", self.modbus_port),
        )
    
    def _data_reader(self):
        """Read sensor data from the process simulator."""
        while self.running:
            try:
                coils = self.store.getValues(1, 0, count=NUM_COILS)
                self.latest_sensor_data = self.data_generator.tick(
                    wall_dt=1.0, coils=coils,
                )
                time.sleep(1)
            except Exception as e:
                log.error(f"Data reader error: {e}")
                time.sleep(1)
    
    def _process_logic(self):
        """
        Run process simulation and update Modbus registers.
        This is the PLC scan cycle.
        """
        while self.running:
            try:
                if not self.latest_sensor_data:
                    time.sleep(0.5)
                    continue
                
                # Read current coil states (SCADA may have written these)
                coils = self.store.getValues(1, 0, count=NUM_COILS)  # fc=1 for coils
                
                # Run process simulation
                result = self.simulator.tick(self.latest_sensor_data, coils)
                
                # ─── UPDATE HOLDING REGISTERS ───
                # Scale to integers (standard Modbus practice)
                hr_values = [0] * NUM_HOLDING_REGISTERS
                hr_values[HR_TURB_RAW] = int(result['turb_raw'] * 10)
                hr_values[HR_TURB_FILTERED] = int(result['turb_filtered'] * 100)
                hr_values[HR_PH] = int(result['ph'] * 100)
                hr_values[HR_CL2] = int(result['cl2'] * 100)
                hr_values[HR_FLOW_RAW] = int(result['flow_raw'] * 10)
                hr_values[HR_FLOW_TREATED] = int(result['flow_treated'] * 10)
                hr_values[HR_LEVEL_PCT] = int(result['level_pct'] * 10)
                hr_values[HR_TEMP] = int(self.latest_sensor_data.get('temp', 25) * 10)
                hr_values[HR_FILTER_DP] = int(result['filter_dp'] * 10)
                hr_values[HR_BW_COUNT] = int(result['backwash_count'])
                hr_values[HR_TOTAL_FLOW] = int(result['total_flow_ml'])
                hr_values[HR_RUNTIME] = int(result['runtime_hours'])
                
                # Clamp to uint16
                hr_values = [max(0, min(65535, v)) for v in hr_values]
                self.store.setValues(3, 0, hr_values)  # fc=3 for holding registers
                
                # ─── UPDATE DISCRETE INPUTS ───
                sd = self.latest_sensor_data
                di_values = [0] * NUM_DISCRETE_INPUTS
                di_values[DI_INTAKE_RUN] = sd.get('p_intake', 0)
                di_values[DI_ALUM_RUN] = sd.get('p_alum', 0)
                di_values[DI_CL2_RUN] = sd.get('p_cl2', 0)
                di_values[DI_BW_OPEN] = sd.get('v_bw', 0)
                di_values[DI_LEVEL_HIGH] = sd.get('lvl_hi', 0)
                di_values[DI_LEVEL_LOW] = sd.get('lvl_lo', 0)
                di_values[DI_ALM_TURB] = 1 if result.get('turb_shutdown') else 0
                di_values[DI_ALM_CL2] = 1 if result['cl2'] < 0.2 else 0
                di_values[DI_COMM_FAULT] = 0 if self.latest_sensor_data else 1
                
                self.store.setValues(2, 0, di_values)  # fc=2 for discrete inputs
                
                # ─── UPDATE INPUT REGISTERS ───
                ir_values = [0] * NUM_INPUT_REGISTERS
                ir_values[IR_TURB_BACKUP] = int(result['turb_raw'] * 10)
                ir_values[IR_PLANT_STATUS] = result['plant_status']
                ir_values[IR_ALARM_WORD] = result.get('alarm_word', 0)
                
                self.store.setValues(4, 0, ir_values)  # fc=4 for input registers
                
            except Exception as e:
                log.error(f"Process logic error: {e}")
            
            time.sleep(1)  # 1-second scan rate
    
    def _command_writer(self):
        """Watch for SCADA command changes (coil writes) and log them."""
        prev_coils = [0] * NUM_COILS

        while self.running:
            try:
                coils = self.store.getValues(1, 0, count=NUM_COILS)

                cmd_map = {
                    CO_INTAKE_CMD: "INTAKE",
                    CO_ALUM_CMD: "ALUM",
                    CO_CL2_CMD: "CHLORINE",
                    CO_BW_CMD: "BACKWASH",
                }

                for idx, device_name in cmd_map.items():
                    if coils[idx] != prev_coils[idx]:
                        log.info(f"SCADA command: {device_name}={coils[idx]}")

                prev_coils = list(coils)

            except Exception as e:
                log.error(f"Command writer error: {e}")

            time.sleep(0.5)

    def _stdin_command_loop(self):
        """Read interactive commands from stdin in simulation mode."""
        from wtp_process_sim import parse_stdin_command
        import sys
        log.info("Interactive commands available. Type 'help' for list.")
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                parse_stdin_command(line, self.data_generator)
            except Exception as e:
                log.debug(f"stdin error: {e}")

    def get_dashboard_data(self):
        """Return current data snapshot for the web dashboard."""
        data = dict(self.latest_sensor_data)
        # Add process simulation results
        ir_values = self.store.getValues(4, 0, count=NUM_INPUT_REGISTERS)
        data['plant_status'] = ir_values[IR_PLANT_STATUS]
        data['alarm_word'] = ir_values[IR_ALARM_WORD]
        # Add holding register derived values
        hr_values = self.store.getValues(3, 0, count=NUM_HOLDING_REGISTERS)
        data['turb_filtered'] = hr_values[HR_TURB_FILTERED] / 100.0
        data['flow_treated'] = hr_values[HR_FLOW_TREATED] / 10.0
        data['filter_dp'] = hr_values[HR_FILTER_DP] / 10.0
        data['backwash_count'] = hr_values[HR_BW_COUNT]
        data['total_flow_ml'] = hr_values[HR_TOTAL_FLOW]
        data['runtime_hours'] = hr_values[HR_RUNTIME]
        # Add simulation state if available
        if self.data_generator:
            data['sim_state'] = self.data_generator.get_state_summary()
        return data


def main():
    parser = argparse.ArgumentParser(description='Tunnel Hill WTP RTU Bridge')
    parser.add_argument('--modbus-port', type=int, default=502,
                        help='Modbus TCP port (default 502, use 5020 if port 502 needs sudo)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Simulation speed multiplier (e.g., 60 = 1 sim-minute per wall-second)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducible simulation')
    parser.add_argument('--no-auto-events', action='store_true',
                        help='Disable automatic rain events in simulation')
    parser.add_argument('--dashboard-port', type=int, default=8080,
                        help='Web dashboard port (default 8080)')
    args = parser.parse_args()

    bridge = RTUBridge(
        modbus_port=args.modbus_port,
        speed=args.speed,
        seed=args.seed,
        auto_events=not args.no_auto_events,
        dashboard_port=args.dashboard_port,
    )
    bridge.start()


if __name__ == '__main__':
    main()
