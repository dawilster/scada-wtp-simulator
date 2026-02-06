# Tunnel Hill WTP — Modbus Register Map

This is the complete register map for the RTU bridge. Every SCADA system is built on a register map — a documented table that defines what every Modbus address means. In a real plant, you'd get this from the PLC programmer or the system integrator's documentation.

> **Scaling convention:** "Scale ×10" means register value `2345` = `234.5 NTU`. This is standard practice because Modbus registers are 16-bit unsigned integers (0–65535) — no floating point. You'll see this everywhere in industrial SCADA.

---

## Holding Registers (Read/Write) — Function Code 3/6/16

| Address | Offset | Name                   | Units  | Range     | Scale |
|---------|--------|------------------------|--------|-----------|-------|
| 40001   | HR0    | Raw Water Turbidity    | NTU    | 0–1000    | ×10   |
| 40002   | HR1    | Filtered Turbidity     | NTU    | 0–10      | ×100  |
| 40003   | HR2    | pH Level               | pH     | 0–14      | ×100  |
| 40004   | HR3    | Chlorine Residual      | mg/L   | 0–5.0     | ×100  |
| 40005   | HR4    | Raw Water Flow Rate    | L/s    | 0–1200    | ×10   |
| 40006   | HR5    | Treated Water Flow     | L/s    | 0–1200    | ×10   |
| 40007   | HR6    | Reservoir Level        | %      | 0–100     | ×10   |
| 40008   | HR7    | Water Temperature      | °C     | 0–50      | ×10   |
| 40009   | HR8    | Alum Dose Rate         | mg/L   | 0–100     | ×10   |
| 40010   | HR9    | Filter Diff. Pressure  | kPa    | 0–200     | ×10   |
| 40011   | HR10   | Dam Release Rate       | ML/day | 0–123     | ×10   |
| 40012   | HR11   | Reservoir Level (cm)   | cm     | 0–3000    | ×1    |
| 40013   | HR12   | Backwash Cycle Count   | count  | 0–65535   | ×1    |
| 40014   | HR13   | Plant Flow Totaliser   | ML     | 0–65535   | ×1    |
| 40015   | HR14   | Plant Runtime Hours    | hours  | 0–65535   | ×1    |

---

## Coils (Read/Write) — Function Code 1/5/15

| Address | Offset | Name                   | State               |
|---------|--------|------------------------|----------------------|
| 00001   | CO0    | Intake Pump Command    | 0=Stop, 1=Run       |
| 00002   | CO1    | Alum Dosing Pump Cmd   | 0=Stop, 1=Run       |
| 00003   | CO2    | Chlorine Dosing Cmd    | 0=Stop, 1=Run       |
| 00004   | CO3    | Backwash Valve Cmd     | 0=Close, 1=Open     |
| 00005   | CO4    | Plant Auto Mode        | 0=Manual, 1=Auto    |
| 00006   | CO5    | Emergency Stop         | 0=Normal, 1=E-Stop  |
| 00007   | CO6    | Alarm Acknowledge      | 0=Normal, 1=Ack     |
| 00008   | CO7    | High Turbidity Shutdn  | 0=Normal, 1=Shutdown |

---

## Discrete Inputs (Read Only) — Function Code 2

| Address | Offset | Name                   | State               |
|---------|--------|------------------------|----------------------|
| 10001   | DI0    | Intake Pump Running    | 0=Stopped, 1=Running|
| 10002   | DI1    | Alum Pump Running      | 0=Stopped, 1=Running|
| 10003   | DI2    | Chlorine Pump Running  | 0=Stopped, 1=Running|
| 10004   | DI3    | Backwash Valve Open    | 0=Closed, 1=Open    |
| 10005   | DI4    | Reservoir High Level   | 0=Normal, 1=High    |
| 10006   | DI5    | Reservoir Low Level    | 0=Normal, 1=Low     |
| 10007   | DI6    | Filter Backwash Active | 0=Normal, 1=Active  |
| 10008   | DI7    | High Turbidity Alarm   | 0=Normal, 1=Alarm   |
| 10009   | DI8    | Low Chlorine Alarm     | 0=Normal, 1=Alarm   |
| 10010   | DI9    | Communication Fault    | 0=OK, 1=Fault       |

---

## Input Registers (Read Only) — Function Code 4

| Address | Offset | Name                   | Type     | Values                                              |
|---------|--------|------------------------|----------|------------------------------------------------------|
| 30001   | IR0    | Raw Turbidity (backup) | NTU ×10  | Redundant turbidity reading                          |
| 30002   | IR1    | Plant Status Code      | enum     | 0=Offline, 1=Starting, 2=Running, 3=Shutdown, 4=Backwash, 5=Fault |
| 30003   | IR2    | Alarm Word 1           | bitfield | See below                                            |

### Alarm Word 1 — Bit Definitions

| Bit | Alarm                 |
|-----|-----------------------|
| 0   | High turbidity raw    |
| 1   | High turbidity filt.  |
| 2   | Low chlorine          |
| 3   | High pH               |
| 4   | Low pH                |
| 5   | Reservoir high level  |
| 6   | Reservoir low level   |
| 7   | Communication fault   |
| 8   | Pump fault            |
| 9   | Valve fault           |
