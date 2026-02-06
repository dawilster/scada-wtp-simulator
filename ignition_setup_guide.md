# Ignition Setup Guide for Tunnel Hill WTP Simulator

Step-by-step guide to connect Ignition Maker Edition to the RTU bridge and build a functional SCADA interface.

---

## Prerequisites

Before starting Ignition setup, make sure the simulator is running:

```bash
python rtu_bridge.py --speed 60 --modbus-port 5020
```

You should see:
```
Simulator active: speed=60.0x
Starting Modbus TCP server on port 5020
Dashboard: http://localhost:8080
```

Leave this running in a terminal. The web dashboard at http://localhost:8080 is useful for verifying data is flowing.

---

## Part 1: Install Ignition

### 1.1 Download and Install

1. Download Ignition Maker Edition from the installer you started
2. Run the installer, accept defaults
3. When prompted for edition, select **Maker Edition**
4. Set a username and password for the gateway (remember these!)
5. Wait for installation to complete

### 1.2 Start the Gateway

After installation:
- **macOS:** Ignition runs as a service automatically. Open http://localhost:8088
- **Windows:** Ignition Gateway Control Utility should appear in system tray. Click "Start Gateway" if needed.
- **Linux:** Run `sudo systemctl start ignition` or `/usr/local/bin/ignition/ignition.sh start`

### 1.3 First Login

1. Open **http://localhost:8088** in your browser
2. You'll see the Ignition Gateway home page
3. Click **Config** (top right)
4. Log in with the credentials you created during installation

---

## Part 2: Create the Modbus Device Connection

This connects Ignition to the RTU bridge running on your machine.

### 2.1 Navigate to Device Connections

1. In the Gateway Config page, expand **OPC UA** in the left menu
2. Click **Device Connections**
3. Click **Create new Device...**

### 2.2 Select Device Type

1. In the dropdown, select **Modbus TCP**
2. Click **Next**

### 2.3 Configure the Device

Fill in these settings:

| Setting | Value |
|---------|-------|
| **Name** | `TunnelHill_RTU` |
| **Enabled** | Checked |
| **Hostname** | `localhost` |
| **Port** | `5020` |
| **Unit ID** | `1` |

Leave other settings at defaults. Click **Create New Device**.

### 2.4 Verify Connection

1. Back on the Device Connections page, you should see `TunnelHill_RTU` listed
2. The **Status** column should show **Connected** (green)
3. If it shows **Disconnected** (red), check that:
   - The RTU bridge is running (`python rtu_bridge.py --speed 60 --modbus-port 5020`)
   - Port 5020 is correct
   - No firewall is blocking localhost connections

---

## Part 3: Create Tags

Tags are named references to Modbus registers. This is the foundation of every SCADA system.

### 3.1 Open the Designer

1. From the Gateway home page (http://localhost:8088), click **Get Designer**
2. Download and install the Ignition Designer Launcher
3. Launch the Designer and connect to your gateway (localhost:8088)
4. Log in with your gateway credentials
5. Create a new project called `TunnelHill_WTP`

### 3.2 Open the Tag Browser

In the Designer:
1. Look for the **Tag Browser** panel (usually on the left side)
2. If not visible, go to **View → Panels → Tag Browser**

### 3.3 Create Tag Folders

Right-click on the **Tags** folder and create this structure:

```
Tags/
├── RawWater/
├── Treatment/
├── Distribution/
├── Equipment/
└── Alarms/
```

To create a folder: Right-click → **New Folder**

### 3.4 Create OPC Tags

Now create tags that read from the Modbus device. For each tag:

1. Right-click the appropriate folder → **New Tag → OPC Tag**
2. Configure the settings as shown below
3. Click **OK**

#### RawWater Folder

| Tag Name | OPC Item Path | Data Type | Scale Mode | Raw Range | Scaled Range | Eng Units |
|----------|---------------|-----------|------------|-----------|--------------|-----------|
| Turbidity | `[TunnelHill_RTU]HR0` | Int2 | Linear | 0-10000 | 0-1000 | NTU |
| pH | `[TunnelHill_RTU]HR2` | Int2 | Linear | 0-1400 | 0-14 | pH |
| Flow | `[TunnelHill_RTU]HR4` | Int2 | Linear | 0-12000 | 0-1200 | L/s |
| Temperature | `[TunnelHill_RTU]HR7` | Int2 | Linear | 0-500 | 0-50 | °C |

#### Treatment Folder

| Tag Name | OPC Item Path | Data Type | Scale Mode | Raw Range | Scaled Range | Eng Units |
|----------|---------------|-----------|------------|-----------|--------------|-----------|
| FilteredTurbidity | `[TunnelHill_RTU]HR1` | Int2 | Linear | 0-1000 | 0-10 | NTU |
| ChlorineResidual | `[TunnelHill_RTU]HR3` | Int2 | Linear | 0-500 | 0-5 | mg/L |
| FilterDP | `[TunnelHill_RTU]HR9` | Int2 | Linear | 0-2000 | 0-200 | kPa |
| TreatedFlow | `[TunnelHill_RTU]HR5` | Int2 | Linear | 0-12000 | 0-1200 | L/s |

#### Distribution Folder

| Tag Name | OPC Item Path | Data Type | Scale Mode | Raw Range | Scaled Range | Eng Units |
|----------|---------------|-----------|------------|-----------|--------------|-----------|
| ReservoirLevel | `[TunnelHill_RTU]HR6` | Int2 | Linear | 0-1000 | 0-100 | % |

#### Equipment Folder — Status Tags (Read-Only)

| Tag Name | OPC Item Path | Data Type |
|----------|---------------|-----------|
| IntakePumpRunning | `[TunnelHill_RTU]DI0` | Boolean |
| AlumPumpRunning | `[TunnelHill_RTU]DI1` | Boolean |
| ChlorinePumpRunning | `[TunnelHill_RTU]DI2` | Boolean |
| BackwashValveOpen | `[TunnelHill_RTU]DI3` | Boolean |
| PlantStatus | `[TunnelHill_RTU]IR1` | Int2 |

#### Equipment Folder — Command Tags (Read/Write)

| Tag Name | OPC Item Path | Data Type |
|----------|---------------|-----------|
| IntakePumpCmd | `[TunnelHill_RTU]CO0` | Boolean |
| AlumPumpCmd | `[TunnelHill_RTU]CO1` | Boolean |
| ChlorinePumpCmd | `[TunnelHill_RTU]CO2` | Boolean |
| BackwashValveCmd | `[TunnelHill_RTU]CO3` | Boolean |
| AutoMode | `[TunnelHill_RTU]CO4` | Boolean |
| EStop | `[TunnelHill_RTU]CO5` | Boolean |

#### Alarms Folder

| Tag Name | OPC Item Path | Data Type |
|----------|---------------|-----------|
| AlarmWord | `[TunnelHill_RTU]IR2` | Int2 |

### 3.5 Verify Tags Are Reading

1. In the Tag Browser, expand your folders
2. Each tag should show a value (not "Bad" or "Stale")
3. Values should be updating — watch the Turbidity or Flow tag change over a few seconds
4. If tags show "Bad" quality, check the OPC Item Path matches the register map

**Tip:** Compare values with the web dashboard (http://localhost:8080) to verify scaling is correct.

---

## Part 4: Configure Alarms

Alarms are what make SCADA more than a dashboard. They notify operators when something needs attention.

### 4.1 Add Alarms to Tags

For each tag that needs alarms:

1. In the Tag Browser, right-click the tag → **Edit Tag**
2. Go to the **Alarms** section
3. Click **Add** to create a new alarm

### 4.2 Alarm Configuration

Configure these alarms:

#### RawWater/Turbidity
| Alarm Name | Mode | Setpoint | Priority | Display Path |
|------------|------|----------|----------|--------------|
| High | Above Setpoint | 200 | Medium | RawWater/Turbidity High |
| HighHigh | Above Setpoint | 500 | Critical | RawWater/Turbidity Critical |

#### Treatment/ChlorineResidual
| Alarm Name | Mode | Setpoint | Priority | Display Path |
|------------|------|----------|----------|--------------|
| Low | Below Setpoint | 0.2 | Critical | Treatment/Chlorine Low |
| High | Above Setpoint | 4.0 | Medium | Treatment/Chlorine High |

#### RawWater/pH
| Alarm Name | Mode | Setpoint | Priority | Display Path |
|------------|------|----------|----------|--------------|
| Low | Below Setpoint | 6.5 | Medium | RawWater/pH Low |
| High | Above Setpoint | 8.5 | Medium | RawWater/pH High |

#### Distribution/ReservoirLevel
| Alarm Name | Mode | Setpoint | Priority | Display Path |
|------------|------|----------|----------|--------------|
| Low | Below Setpoint | 20 | Critical | Distribution/Level Low |
| High | Above Setpoint | 95 | Medium | Distribution/Level High |

#### Treatment/FilterDP
| Alarm Name | Mode | Setpoint | Priority | Display Path |
|------------|------|----------|----------|--------------|
| High | Above Setpoint | 150 | Medium | Treatment/FilterDP High |

### 4.3 Test Alarms

1. In the web dashboard, click **"Heavy Rain (700)"**
2. Watch the turbidity spike above 500 NTU
3. In Ignition Designer, go to **Tools → Diagnostics → Alarms**
4. You should see the Turbidity HighHigh alarm appear as Active

---

## Part 5: Enable Tag History

The historian stores tag values over time for trending and analysis.

### 5.1 Configure History on Tags

For each analog tag you want to trend:

1. Right-click the tag → **Edit Tag**
2. Go to the **History** section
3. Enable **History Enabled**
4. Set:
   - **Storage Provider:** (default is fine)
   - **Sample Mode:** On Change
   - **Deadband:** 1 (for most tags) or 0.01 (for pH)
   - **Max Time Between Samples:** 60 seconds

Enable history on these tags:
- RawWater/Turbidity
- RawWater/pH
- RawWater/Flow
- Treatment/ChlorineResidual
- Treatment/FilteredTurbidity
- Treatment/FilterDP
- Distribution/ReservoirLevel

### 5.2 Verify History Is Recording

1. Let the system run for a few minutes
2. In Designer, right-click a tag with history → **View in Easy Chart**
3. You should see historical data plotted

---

## Part 6: Build an HMI Screen (Perspective)

Now build a visual interface. We'll use Perspective (web-based HMI).

### 6.1 Create a New View

1. In the Designer Project Browser, expand **Perspective → Views**
2. Right-click **Views** → **New View**
3. Name it `PlantOverview`
4. Select **Coordinate** layout (allows free positioning)
5. Click **Create**

### 6.2 Add a Header

1. From the Component Palette, drag a **Label** onto the view
2. Set the text to `Tunnel Hill WTP - Plant Overview`
3. Style it: larger font, bold, centered at the top

### 6.3 Add Value Displays

For each process value, add a display:

1. Drag a **Numeric Label** component onto the view
2. In the Property Editor, bind the **value** property:
   - Click the binding icon next to **value**
   - Select **Tag** binding
   - Browse to the tag (e.g., `RawWater/Turbidity`)
   - Click **OK**
3. Set **fractionDigits** to 1 or 2 as appropriate
4. Add a regular **Label** next to it for the name and units

Create displays for:
- Raw Turbidity (NTU)
- pH
- Chlorine Residual (mg/L)
- Raw Flow (L/s)
- Reservoir Level (%)
- Filter DP (kPa)

### 6.4 Add Status Indicators

For equipment status (pumps running, valves open):

1. Drag an **LED Display** component onto the view
2. Bind the **value** property to the status tag (e.g., `Equipment/IntakePumpRunning`)
3. The LED will show green when true, grey when false
4. Add a label next to each LED

Create indicators for:
- Intake Pump Running
- Alum Pump Running
- Chlorine Pump Running
- Backwash Valve Open

### 6.5 Add Control Buttons

For operator controls:

1. Drag a **Toggle Switch** component onto the view
2. Bind the **value** property to the command tag (e.g., `Equipment/AutoMode`)
3. Make sure the binding is **bidirectional** (two-way arrow icon)
4. Add a label: "Auto Mode"

Create toggles for:
- Auto Mode
- Intake Pump Command
- Backwash Valve Command

### 6.6 Add a Plant Status Display

1. Drag a **Label** component
2. Bind the **text** property using an **Expression** binding:
   ```
   switch({[~]Equipment/PlantStatus},
     0, "OFFLINE",
     1, "STARTING",
     2, "RUNNING",
     3, "SHUTDOWN",
     4, "BACKWASH",
     5, "FAULT",
     "UNKNOWN"
   )
   ```
3. Optionally bind the **style** to change color based on status

### 6.7 Add a Trend Chart

1. Drag a **Time Series Chart** component onto the view
2. Make it large enough to see trends clearly
3. In the property editor, find **series** and add pens:
   - Click **+** to add a series
   - Set **name** to "Turbidity"
   - Bind **source** to `tag:RawWater/Turbidity` (historical)
4. Add additional series for pH, Chlorine, Level as desired

### 6.8 Add an Alarm Status Table

1. Drag an **Alarm Status Table** component onto the view
2. It will automatically show active alarms from your configured alarm tags
3. Resize to fit your layout

### 6.9 Preview the View

1. Click the **Preview** button (play icon) in the toolbar
2. Your HMI should show live values updating
3. Try toggling Auto Mode and Intake Pump to start the plant
4. Trigger a rain event in the web dashboard and watch alarms appear

---

## Part 7: Launch the Session

### 7.1 Set Up the Session

1. In Designer, go to **Perspective → Sessions**
2. Create or edit the default session
3. Set the **Startup Page** to your `PlantOverview` view

### 7.2 Launch in Browser

1. Save your project in Designer (**File → Save**)
2. Open a browser and go to: `http://localhost:8088/data/perspective/client/TunnelHill_WTP`
3. Your HMI should load and show live data

### 7.3 Test the Full System

1. Make sure the RTU bridge is running with `--speed 60`
2. In Ignition, toggle **Auto Mode** ON, then **Intake Pump** ON
3. Watch the Plant Status change: OFFLINE → STARTING → RUNNING
4. In the web dashboard, click **"Heavy Rain (700)"**
5. Watch turbidity spike in both the dashboard and Ignition trend
6. See the alarm appear in the Alarm Status Table
7. Watch the plant auto-shutdown when turbidity exceeds 500 NTU
8. Observe reservoir level dropping while the plant is offline

---

## Troubleshooting

### Tags Show "Bad" Quality

- Check the RTU bridge is running
- Verify the OPC Item Path matches the register map (HR0, HR1, etc.)
- Check the Device Connection shows "Connected" in Gateway Config

### Values Don't Match Dashboard

- Check your scaling configuration (Raw Range and Scaled Range)
- Refer to `register_map.md` for the correct scale factors

### Alarms Don't Trigger

- Verify alarm is enabled on the tag
- Check the setpoint is correct
- Make sure alarm priority is set

### Can't Write to Command Tags

- Coil tags must be writable — verify the OPC Item Path uses CO (not DI)
- Check the tag's read/write settings

### Designer Can't Connect to Gateway

- Make sure the gateway is running (http://localhost:8088 should load)
- Check firewall settings
- Try restarting the Ignition gateway service

---

## Next Steps

Once you have the basics working:

1. **Add more HMI screens** — Create a detailed Filtration screen, an Alarm Summary screen, an Equipment Status screen

2. **Improve the overview** — Add a process flow diagram with pipes, tanks, and animated pumps

3. **Build reports** — Use the Reporting module to generate daily water quality summaries

4. **Explore alarms further** — Set up alarm shelving, acknowledgement, and alarm journal queries

---

## Quick Reference: Modbus Register Map

| Register | Address | Scale | Description |
|----------|---------|-------|-------------|
| HR0 | 40001 | ÷10 | Raw Turbidity (NTU) |
| HR1 | 40002 | ÷100 | Filtered Turbidity (NTU) |
| HR2 | 40003 | ÷100 | pH |
| HR3 | 40004 | ÷100 | Chlorine (mg/L) |
| HR4 | 40005 | ÷10 | Raw Flow (L/s) |
| HR5 | 40006 | ÷10 | Treated Flow (L/s) |
| HR6 | 40007 | ÷10 | Reservoir Level (%) |
| HR7 | 40008 | ÷10 | Temperature (°C) |
| HR9 | 40010 | ÷10 | Filter DP (kPa) |
| CO0 | 00001 | bool | Intake Pump Cmd |
| CO1 | 00002 | bool | Alum Pump Cmd |
| CO2 | 00003 | bool | Chlorine Pump Cmd |
| CO3 | 00004 | bool | Backwash Valve Cmd |
| CO4 | 00005 | bool | Auto Mode |
| CO5 | 00006 | bool | E-Stop |
| DI0 | 10001 | bool | Intake Pump Running |
| DI1 | 10002 | bool | Alum Pump Running |
| DI2 | 10003 | bool | Chlorine Pump Running |
| DI3 | 10004 | bool | Backwash Valve Open |
| IR1 | 30002 | int | Plant Status (0-5) |
| IR2 | 30003 | bits | Alarm Word |

See `register_map.md` for the complete register map with all addresses and alarm bit definitions.
