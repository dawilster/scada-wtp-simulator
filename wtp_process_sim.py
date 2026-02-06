#!/usr/bin/env python3
"""
Tunnel Hill WTP — Realistic Process Data Generator

Produces correlated, noisy sensor data for the WTP simulator.
Drop-in replacement for the sine-wave simulation in rtu_bridge.py.

Sensor models use Ornstein-Uhlenbeck mean-reverting random walks with
Gaussian noise, diurnal patterns, and correlated rain event effects
modelling the real Freshwater Creek catchment behaviour.

Usage:
    from wtp_process_sim import ProcessDataGenerator
    gen = ProcessDataGenerator(speed=60, seed=42)
    data = gen.tick(wall_dt=1.0, coils=[0]*20)
"""

import math
import random
import logging

log = logging.getLogger("WTP_Sim")

# ═══════════════════════════════════════════════════════════
# ORNSTEIN-UHLENBECK PROCESS
# ═══════════════════════════════════════════════════════════

class OUProcess:
    """
    Mean-reverting random walk: dx = theta*(mu - x)*dt + sigma*dW
    Good model for sensor noise around a setpoint.
    """

    def __init__(self, mu=0.0, sigma=1.0, theta=0.1, x0=None):
        self.mu = mu
        self.sigma = sigma
        self.theta = theta
        self.x = x0 if x0 is not None else mu

    def step(self, dt, rng):
        if dt <= 0:
            return self.x
        drift = self.theta * (self.mu - self.x) * dt
        diffusion = self.sigma * math.sqrt(dt) * rng.gauss(0, 1)
        self.x += drift + diffusion
        return self.x

    def set_mu(self, mu):
        self.mu = mu


# ═══════════════════════════════════════════════════════════
# RAIN EVENT
# ═══════════════════════════════════════════════════════════

class RainEvent:
    """
    Models a tropical rain event hitting the Freshwater Creek catchment.
    Turbidity spikes sharply then decays exponentially. pH drops.
    Flow increases. Temperature dips slightly.
    """

    def __init__(self, start_time, peak_turb=400.0, duration_hours=6.0):
        self.start_time = start_time
        self.peak_turb = peak_turb
        self.duration = duration_hours * 3600  # seconds
        # Rise time is ~10% of duration, decay is the rest
        self.rise_time = self.duration * 0.1
        self.decay_tau = self.duration * 0.3  # exponential decay time constant
        self.ph_drop = 0.2 + 0.6 * (peak_turb / 800)  # proportional to severity
        self.flow_boost_frac = 0.1 + 0.1 * (peak_turb / 800)
        self.temp_dip = 1.0 + 1.0 * (peak_turb / 800)

    def is_active(self, sim_time):
        elapsed = sim_time - self.start_time
        return 0 <= elapsed <= self.duration

    def is_expired(self, sim_time):
        return sim_time - self.start_time > self.duration

    def turbidity_contribution(self, sim_time):
        elapsed = sim_time - self.start_time
        if elapsed < 0 or elapsed > self.duration:
            return 0.0
        if elapsed < self.rise_time:
            # Sharp rise
            frac = elapsed / self.rise_time
            return self.peak_turb * frac
        else:
            # Exponential decay
            t_decay = elapsed - self.rise_time
            return self.peak_turb * math.exp(-t_decay / self.decay_tau)

    def ph_contribution(self, sim_time):
        """Negative offset (acidic tropical runoff)."""
        turb_frac = self.turbidity_contribution(sim_time) / self.peak_turb
        return -self.ph_drop * turb_frac

    def flow_contribution(self, sim_time, base_flow):
        turb_frac = self.turbidity_contribution(sim_time) / self.peak_turb
        return base_flow * self.flow_boost_frac * turb_frac

    def temp_contribution(self, sim_time):
        turb_frac = self.turbidity_contribution(sim_time) / self.peak_turb
        return -self.temp_dip * turb_frac


# ═══════════════════════════════════════════════════════════
# CHLORINE DOSING MODEL
# ═══════════════════════════════════════════════════════════

class ChlorineDoseModel:
    """
    Sawtooth-ish chlorine residual: periodic dosing pulse + exponential decay.
    Real plants dose continuously but residual fluctuates due to demand.
    """

    def __init__(self, rng):
        self.residual = 1.5  # mg/L starting
        self.dose_interval = 900  # ~15 min cycle
        self.time_since_dose = 0.0
        self.decay_rate = 0.0003  # per second, base
        self.rng = rng
        self.dosing_active = True

    def step(self, dt, rain_active=False):
        if not self.dosing_active:
            # Decay only
            self.residual *= math.exp(-self.decay_rate * 2 * dt)
            self.residual = max(0.0, self.residual)
            return self.residual

        self.time_since_dose += dt
        # Decay (faster during rain — organics consume chlorine)
        decay = self.decay_rate * (2.0 if rain_active else 1.0)
        self.residual *= math.exp(-decay * dt)

        # Periodic dose
        if self.time_since_dose >= self.dose_interval:
            self.time_since_dose = 0.0
            # Dose brings residual up
            dose_amount = 0.8 + self.rng.gauss(0, 0.1)
            self.residual += max(0.1, dose_amount)

        # Clamp
        self.residual = max(0.0, min(5.0, self.residual))
        # Add small noise
        self.residual += self.rng.gauss(0, 0.02)
        self.residual = max(0.0, min(5.0, self.residual))
        return self.residual


# ═══════════════════════════════════════════════════════════
# DIURNAL DEMAND CURVE
# ═══════════════════════════════════════════════════════════

def diurnal_flow(hour_of_day, base=500.0):
    """
    Realistic daily water demand curve for Cairns.
    Low overnight (~60% base), morning peak 6-9am (~120%),
    slight midday dip, afternoon peak 5-7pm (~115%).
    """
    h = hour_of_day % 24
    # Composite of gaussians for peaks + low overnight baseline
    overnight = 0.60
    am_peak = 0.60 * math.exp(-((h - 7.5) ** 2) / 4.0)
    pm_peak = 0.45 * math.exp(-((h - 17.5) ** 2) / 3.0)
    midday = 0.20 * math.exp(-((h - 12.0) ** 2) / 6.0)
    fraction = overnight + am_peak + pm_peak + midday
    return base * fraction


def diurnal_temp(hour_of_day, base_min=22.0, base_max=28.0):
    """Daily temperature cycle — coolest at 5am, warmest at 2pm."""
    h = hour_of_day % 24
    # Sinusoidal with phase shift: min at 5am, max at 2pm (~14h)
    mid = (base_min + base_max) / 2
    amp = (base_max - base_min) / 2
    # Map: h=5 → -1 (min), h=14 → +1 (max) ⟹ phase=-5*2π/24 shifted
    phase = 2 * math.pi * (h - 14) / 24
    return mid - amp * math.cos(phase)


# ═══════════════════════════════════════════════════════════
# MAIN GENERATOR
# ═══════════════════════════════════════════════════════════

class ProcessDataGenerator:
    """
    Produces realistic, correlated sensor data for the WTP simulator.

    Args:
        speed: Time compression factor. At speed=60, one wall second = one sim minute.
        seed: Random seed for reproducibility. None for random.
        auto_events: If True, rain events fire via Poisson process.
    """

    def __init__(self, speed=1.0, seed=None, auto_events=True):
        self.speed = speed
        self.auto_events = auto_events
        self.rng = random.Random(seed)

        # Simulated clock (seconds since start, at simulated rate)
        self.sim_time = 0.0
        # Start at 6am for interesting diurnal behaviour
        self.sim_time_offset = 6 * 3600

        # ── Sensor processes ──
        self.turb_ou = OUProcess(mu=3.5, sigma=0.4, theta=0.001, x0=3.5)
        self.ph_ou = OUProcess(mu=7.2, sigma=0.03, theta=0.005, x0=7.2)
        self.flow_ou = OUProcess(mu=0.0, sigma=15.0, theta=0.01, x0=0.0)  # offset from diurnal
        self.level_ou = OUProcess(mu=65.0, sigma=0.05, theta=0.1, x0=65.0)  # light sensor noise only
        self.temp_ou = OUProcess(mu=0.0, sigma=0.1, theta=0.01, x0=0.0)  # offset from diurnal

        # Chlorine model
        self.cl2_model = ChlorineDoseModel(self.rng)

        # Reservoir level integrator
        self.reservoir_level = 65.0  # %

        # ── Rain events ──
        self.active_events = []
        self.next_rain_time = self._schedule_next_rain()

        # ── Equipment fault states ──
        self.faults = {
            'chlorine': False,
            'flow': False,
            'turbidity': False,
        }

        # ── Glitch state ──
        self.glitch_until = 0.0

    def _schedule_next_rain(self):
        """Poisson process: mean interval 18-36 simulated hours."""
        if not self.auto_events:
            return float('inf')
        mean_interval = self.rng.uniform(18, 36) * 3600  # sim seconds
        return self.sim_time + self.rng.expovariate(1.0 / mean_interval)

    def inject_event(self, event_type, **kwargs):
        """
        Inject a scenario event.

        Events:
            rain [peak_turb]: Trigger rain event (default peak 400 NTU)
            dose_off: Stop chlorine dosing
            dose_on: Resume chlorine dosing
            fault <sensor>: Force a sensor into fault
            clear <sensor>: Clear a sensor fault
            glitch: Random data glitch for 30 sim-seconds
        """
        if event_type == 'rain':
            peak = kwargs.get('peak_turb', 400.0)
            duration = kwargs.get('duration_hours', 6.0)
            evt = RainEvent(self.sim_time, peak_turb=peak, duration_hours=duration)
            self.active_events.append(evt)
            log.info(f"Rain event injected: peak={peak} NTU, duration={duration}h")
        elif event_type == 'dose_off':
            self.cl2_model.dosing_active = False
            log.info("Chlorine dosing DISABLED")
        elif event_type == 'dose_on':
            self.cl2_model.dosing_active = True
            log.info("Chlorine dosing ENABLED")
        elif event_type == 'fault':
            sensor = kwargs.get('sensor', 'chlorine')
            self.faults[sensor] = True
            log.info(f"Fault injected: {sensor}")
        elif event_type == 'clear':
            sensor = kwargs.get('sensor', 'chlorine')
            self.faults[sensor] = False
            log.info(f"Fault cleared: {sensor}")
        elif event_type == 'glitch':
            self.glitch_until = self.sim_time + 30
            log.info("Data glitch injected (30 sim-seconds)")

    def tick(self, wall_dt, coils=None):
        """
        Advance simulation by wall_dt seconds (scaled by speed).
        Returns dict with all simulated sensor values.

        Args:
            wall_dt: Wall-clock seconds since last tick.
            coils: Current Modbus coil states (list), or None.
        """
        sim_dt = wall_dt * self.speed
        self.sim_time += sim_dt

        # Current simulated hour of day
        total_sim_seconds = self.sim_time + self.sim_time_offset
        hour_of_day = (total_sim_seconds / 3600) % 24

        # ── Auto rain events ──
        if self.auto_events and self.sim_time >= self.next_rain_time:
            peak = self.rng.uniform(200, 800)
            duration = self.rng.uniform(3, 10)
            self.inject_event('rain', peak_turb=peak, duration_hours=duration)
            self.next_rain_time = self._schedule_next_rain()

        # Clean up expired events
        self.active_events = [e for e in self.active_events if not e.is_expired(self.sim_time)]

        any_rain = any(e.is_active(self.sim_time) for e in self.active_events)

        # ═══ TURBIDITY ═══
        # Base: slow OU walk around 2-5 NTU
        self.turb_ou.step(sim_dt, self.rng)
        turb_base = max(0.5, self.turb_ou.x)
        # Add rain contributions
        turb_rain = sum(e.turbidity_contribution(self.sim_time) for e in self.active_events)
        turb_raw = turb_base + turb_rain
        # Noise: 2% + 0.3 NTU floor
        turb_noise = self.rng.gauss(0, max(0.3, turb_raw * 0.02))
        turb_raw = max(0.0, turb_raw + turb_noise)

        if self.faults.get('turbidity'):
            turb_raw = self.rng.uniform(900, 999)

        # ═══ pH ═══
        # Daily sinusoidal drift around 7.0-7.4
        ph_diurnal = 7.2 + 0.2 * math.sin(2 * math.pi * hour_of_day / 24)
        self.ph_ou.set_mu(ph_diurnal)
        self.ph_ou.step(sim_dt, self.rng)
        ph = self.ph_ou.x
        # Rain: acidic tropical runoff
        ph += sum(e.ph_contribution(self.sim_time) for e in self.active_events)
        ph = max(4.0, min(10.0, ph))

        # ═══ CHLORINE ═══
        cl2 = self.cl2_model.step(sim_dt, rain_active=any_rain)
        if self.faults.get('chlorine'):
            cl2 = max(0.0, cl2 - 1.5)  # Simulate dosing pump failure

        # ═══ FLOW ═══
        base_flow = diurnal_flow(hour_of_day, base=500.0)
        self.flow_ou.step(sim_dt, self.rng)
        flow_raw = base_flow + self.flow_ou.x
        # Rain boost
        flow_raw += sum(e.flow_contribution(self.sim_time, base_flow) for e in self.active_events)
        # Noise: 3%
        flow_raw += self.rng.gauss(0, flow_raw * 0.03)
        flow_raw = max(0.0, flow_raw)

        if self.faults.get('flow'):
            flow_raw = 0.0  # Flow sensor failure

        # ═══ RESERVOIR LEVEL ═══
        # Integrates: inflow raises level, demand (outflow) lowers it.
        # When plant is offline (intake pump off), no water enters the reservoir
        # but consumers keep drawing from it, so level drops.
        # A typical reservoir might hold ~50 ML. At 500 L/s demand,
        # it drains from 100% to 0% in ~28 hours with no inflow.
        intake_running = coils[0] if coils else 1
        inflow = flow_raw if intake_running else 0.0
        demand = diurnal_flow(hour_of_day, base=500.0)
        # Rate: ~3.6% per simulated hour at 500 L/s with no inflow
        net_flow_pct_per_sec = (inflow - demand) / 500.0 * (3.6 / 3600.0)
        self.reservoir_level += net_flow_pct_per_sec * sim_dt
        self.reservoir_level = max(0.0, min(100.0, self.reservoir_level))
        # Small noise around the actual level, no mean-reversion to a fixed point
        self.level_ou.set_mu(self.reservoir_level)
        self.level_ou.step(sim_dt, self.rng)
        level_pct = max(0.0, min(100.0, self.level_ou.x))
        # Keep OU tracking actual level so it doesn't fight the integrator
        self.level_ou.x = level_pct
        self.reservoir_level = level_pct
        level_cm = level_pct * 30  # 100% = 3000cm (30m tank)

        # ═══ TEMPERATURE ═══
        temp_base = diurnal_temp(hour_of_day)
        self.temp_ou.step(sim_dt, self.rng)
        temp = temp_base + self.temp_ou.x
        temp += sum(e.temp_contribution(self.sim_time) for e in self.active_events)
        temp = max(10.0, min(45.0, temp))

        # ═══ GLITCH ═══
        if self.sim_time < self.glitch_until:
            turb_raw += self.rng.uniform(-50, 200)
            ph += self.rng.uniform(-2, 2)
            flow_raw += self.rng.uniform(-200, 200)
            turb_raw = max(0, turb_raw)
            ph = max(0, min(14, ph))
            flow_raw = max(0, flow_raw)

        # ═══ DIGITAL STATES ═══
        # Derive from coils if available, else default running
        if coils:
            p_intake = 1 if coils[0] else 0
            p_alum = 1 if coils[1] else 0
            p_cl2 = 1 if coils[2] else 0
            v_bw = 1 if coils[3] else 0
        else:
            p_intake = 1
            p_alum = 1
            p_cl2 = 1
            v_bw = 0

        lvl_hi = 1 if level_pct > 95 else 0
        lvl_lo = 1 if level_pct < 20 else 0

        return {
            'turb_raw': round(turb_raw, 1),
            'ph': round(ph, 2),
            'cl2': round(cl2, 2),
            'flow_raw': round(flow_raw, 1),
            'level_pct': round(level_pct, 1),
            'level_cm': round(level_cm, 1),
            'temp': round(temp, 1),
            'lvl_hi': lvl_hi,
            'lvl_lo': lvl_lo,
            'pulses': int(flow_raw * 0.02),  # Simulated pulse count
            'p_intake': p_intake,
            'p_alum': p_alum,
            'p_cl2': p_cl2,
            'v_bw': v_bw,
        }

    def get_state_summary(self):
        """Return a summary of the current simulation state for the dashboard."""
        total_sim_seconds = self.sim_time + self.sim_time_offset
        hour_of_day = (total_sim_seconds / 3600) % 24
        sim_day = int(total_sim_seconds / 86400)
        return {
            'sim_time': self.sim_time,
            'sim_hour': round(hour_of_day, 2),
            'sim_day': sim_day,
            'speed': self.speed,
            'active_rain_events': len([e for e in self.active_events if e.is_active(self.sim_time)]),
            'dosing_active': self.cl2_model.dosing_active,
            'faults': {k: v for k, v in self.faults.items() if v},
        }


def parse_stdin_command(line, generator):
    """
    Parse interactive stdin commands.

    Commands:
        rain [peak_ntu]     - Trigger rain event (default 400)
        dose off            - Stop chlorine dosing
        dose on             - Resume chlorine dosing
        fault <sensor>      - Inject sensor fault (chlorine, flow, turbidity)
        clear <sensor>      - Clear sensor fault
        glitch              - Random data glitch
        status              - Print simulation state
        help                - Show commands
    """
    parts = line.strip().lower().split()
    if not parts:
        return

    cmd = parts[0]
    if cmd == 'rain':
        peak = float(parts[1]) if len(parts) > 1 else 400.0
        generator.inject_event('rain', peak_turb=peak)
    elif cmd == 'dose':
        if len(parts) > 1 and parts[1] == 'off':
            generator.inject_event('dose_off')
        else:
            generator.inject_event('dose_on')
    elif cmd == 'fault':
        sensor = parts[1] if len(parts) > 1 else 'chlorine'
        generator.inject_event('fault', sensor=sensor)
    elif cmd == 'clear':
        sensor = parts[1] if len(parts) > 1 else 'chlorine'
        generator.inject_event('clear', sensor=sensor)
    elif cmd == 'glitch':
        generator.inject_event('glitch')
    elif cmd == 'status':
        state = generator.get_state_summary()
        print(f"  Sim time: {state['sim_time']:.0f}s | Hour: {state['sim_hour']:.1f} | Day: {state['sim_day']}")
        print(f"  Speed: {state['speed']}x | Rain events: {state['active_rain_events']}")
        print(f"  Dosing: {'ON' if state['dosing_active'] else 'OFF'} | Faults: {state['faults'] or 'none'}")
    elif cmd == 'help':
        print("Commands: rain [ntu], dose on/off, fault <sensor>, clear <sensor>, glitch, status, help")
    else:
        print(f"Unknown command: {cmd}. Type 'help' for commands.")
