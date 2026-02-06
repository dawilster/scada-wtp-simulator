# Water Treatment — Process Guide

A practical reference for understanding how a surface water treatment plant works, written in the context of the Tunnel Hill WTP in Cairns. Every term and concept here maps directly to something in the SCADA simulator.

---

## The Big Picture

Raw water from Copperlode Falls Dam flows into the plant dirty. The plant's job is to remove particles, kill pathogens, and deliver safe drinking water to 165,000+ people. The treatment chain is:

```
Dam/Catchment → Intake → Coagulation → Flocculation → Sedimentation → Filtration → Disinfection → Reservoir → Distribution
```

Each stage has measurable parameters that SCADA monitors. If any parameter goes out of range, the plant either adjusts automatically or shuts down to prevent unsafe water reaching consumers.

---

## Key Measurements

### Turbidity (NTU)

**What it is:** A measure of how cloudy the water is. A nephelometer shines a light beam through a sample and measures how much light is scattered at 90 degrees by suspended particles (dirt, silt, organic matter, microorganisms). The unit is NTU — Nephelometric Turbidity Unit.

**Why it matters:** Turbidity is the single most important indicator of treatment effectiveness. Particles in water can harbour pathogens (Cryptosporidium, Giardia) that are resistant to chlorine. If turbidity is high, disinfection cannot be relied upon. Australian Drinking Water Guidelines require treated water turbidity below 1 NTU, with a target of <0.2 NTU.

**Typical values:**
- Clean dam water on a dry day: 2-5 NTU
- After moderate rain: 50-200 NTU
- After heavy tropical rain (Cairns wet season): 200-1000+ NTU
- After filtration (plant running well): 0.02-0.1 NTU
- Alarm threshold at Tunnel Hill: 500 NTU triggers automatic shutdown

**What affects it:** Rainfall is the dominant factor. Rain washes soil and organic matter from the catchment into the waterway. In tropical Cairns, intense wet-season storms can push raw turbidity from 3 NTU to 800 NTU in hours. The plant cannot treat water this dirty — the chemical demand is too high and filters would clog immediately — so it shuts down and waits for the turbidity to decay naturally as the storm passes.

### pH

**What it is:** A logarithmic scale (0-14) measuring how acidic or alkaline the water is. 7 is neutral, below 7 is acidic, above 7 is alkaline.

**Why it matters:** pH affects every chemical process in the plant:
- **Coagulation efficiency** — alum works best in a narrow pH range (6.0-7.5). Outside this range, floc formation is poor and turbidity removal drops.
- **Disinfection efficiency** — chlorine is most effective at lower pH. At pH 7.5, about 50% of free chlorine is in the effective HOCl form. At pH 8.5, only about 10% is.
- **Corrosion control** — low pH water corrodes pipes and leaches metals (lead, copper). High pH causes scale buildup.
- **Regulatory compliance** — Australian guidelines specify pH 6.5-8.5 for drinking water.

**Typical values:**
- Raw Freshwater Creek water: 6.8-7.4
- During rain events: drops 0.2-0.8 (tropical runoff is slightly acidic from decomposing vegetation and humic acids)
- Target after treatment: 7.0-7.5

**What affects it:** Catchment geology, rainfall (organic acids), and chemical dosing. The plant may add lime or soda ash to raise pH after coagulation.

### Chlorine Residual (mg/L)

**What it is:** The concentration of free chlorine remaining in the water after it has reacted with contaminants. Measured in milligrams per litre (mg/L), also written as ppm (parts per million).

**Why it matters:** Chlorine is the primary disinfectant. It kills bacteria and viruses by oxidising their cell walls. The "residual" is what's left over after the initial chlorine demand is satisfied — it provides ongoing protection as water travels through the distribution network to taps. Without adequate residual, bacteria can regrow in pipes.

**How dosing works:** Chlorine gas or sodium hypochlorite solution is injected continuously. The dose rate is adjusted to maintain a target residual (typically 0.5-2.0 mg/L leaving the plant). The operator or SCADA system adjusts the dose based on:
- Flow rate (more water = more chlorine needed)
- Raw water quality (dirtier water consumes more chlorine)
- Temperature (warmer water = faster chlorine decay)
- Contact time (longer time in the contact tank = more kill, less residual needed)

**Typical values:**
- Target leaving the plant: 1.0-2.0 mg/L
- Minimum acceptable: 0.2 mg/L (below this, disinfection is not assured)
- Maximum: 5.0 mg/L (taste/odour complaints above ~4 mg/L)
- At the tap (end of distribution): >0.2 mg/L

**What affects it:**
- **Organic matter** — reacts with chlorine, consuming it. During rain events when turbidity is high, chlorine demand spikes because there's more organic material to oxidise. This is why chlorine residual drops during storms even if the dose rate stays the same.
- **Temperature** — chlorine decays faster in warm water. Cairns water at 25-28°C loses residual faster than temperate cities.
- **pH** — higher pH reduces chlorine effectiveness (more of it converts to the less-effective OCl⁻ form).
- **Ammonia** — reacts with chlorine to form chloramines, which are less effective disinfectants.

### Flow Rate (L/s)

**What it is:** Volume of water passing through the plant per second, measured in litres per second (L/s). Sometimes expressed as megalitres per day (ML/day) for daily reporting.

**Why it matters:** Flow determines:
- **Chemical dosing** — all dose rates are proportional to flow. Double the flow, double the alum and chlorine.
- **Contact time** — faster flow means less time in the chlorine contact tank, so either the dose must increase or treatment effectiveness drops.
- **Filter loading** — higher flow pushes more water through filters per unit area, reducing their effectiveness and accelerating clogging.
- **Reservoir balance** — if inflow exceeds demand, the reservoir rises. If demand exceeds inflow, it falls.

**Typical values:**
- Cairns average demand: ~500 L/s
- Morning peak (6-9am, showers/breakfast): ~600 L/s
- Afternoon peak (5-7pm, cooking/gardens): ~575 L/s
- Overnight low (midnight-5am): ~300 L/s
- During rain events: +10-20% from storm runoff entering the intake

**What affects it:** Diurnal demand patterns (people use more water in the morning and evening), seasonal variation (more garden watering in dry season), and rainfall (increases raw water availability at the intake).

### Reservoir Level (%)

**What it is:** How full the treated water reservoir is, expressed as a percentage. The reservoir is a large concrete or steel tank that stores treated water before it enters the distribution network.

**Why it matters:** The reservoir is the buffer between production and demand. It must stay within safe limits:
- **Too low (<20%)** — risk of running dry. Pressure drops in the distribution network. Air can enter pipes, causing contamination and water hammer.
- **Too high (>95%)** — overflow risk. Wasted treated water. Can indicate a valve or control issue.
- The plant operator adjusts intake pump speed to match production to demand, keeping the level in the 50-80% range.

**What affects it:** The balance between inflow (plant production rate) and outflow (consumer demand). This is why flow rate and reservoir level are tightly linked — if the plant shuts down during a turbidity event, the reservoir level drops as demand continues but production stops.

### Temperature (°C)

**What it is:** Water temperature, measured in degrees Celsius.

**Why it matters:**
- **Chlorine decay** — faster in warmer water, requiring higher dose rates. Cairns water at 25-28°C is significantly harder to maintain chlorine residual in than Melbourne water at 12-15°C.
- **Coagulation** — works slightly differently at different temperatures. Cold water is harder to coagulate.
- **Biological growth** — warmer water promotes algae and biofilm growth in reservoirs and pipes.
- **Dissolved oxygen** — warmer water holds less oxygen, affecting biological treatment processes.

**Typical values:**
- Cairns wet season (Dec-Apr): 25-30°C
- Cairns dry season (May-Nov): 20-25°C
- During heavy rain: drops 1-3°C (cooler runoff mixing in)

### Filter Differential Pressure (kPa)

**What it is:** The pressure difference between the top and bottom of a sand/media filter bed. As particles accumulate in the filter, it becomes harder for water to pass through, increasing the pressure drop.

**Why it matters:** Filter DP tells you how dirty (loaded) the filter is:
- **Low DP (10-30 kPa)** — clean filter, just been backwashed.
- **Rising DP** — filter is loading normally, removing turbidity as designed.
- **High DP (>150 kPa)** — filter is nearly full. Flow is restricted. If not backwashed soon, either flow drops or turbidity breaks through.

**What triggers backwash:** Either high DP (the filter is clogged) or a timer (e.g. every 24-48 hours regardless of DP). Backwash reverses the flow, flushing accumulated particles out of the filter bed. This takes the filter offline for 15-30 minutes and wastes ~2-5% of the treated water.

---

## The Treatment Process Step by Step

### 1. Intake / Raw Water Collection

Water is drawn from Copperlode Falls Dam via a pipeline to the plant. The intake pump is the first thing that runs — without it, nothing happens. In the simulator, the **Intake Pump** coil controls this.

A screen at the intake prevents large debris (sticks, leaves, fish) from entering the plant.

### 2. Coagulation

**Purpose:** Make tiny suspended particles stick together so they can be removed.

Raw water particles are often colloidal — so small (1-100 nanometres) that they stay suspended indefinitely and pass straight through filters. These particles carry a negative electrical charge that causes them to repel each other.

**Alum (aluminium sulfate)** is dosed into the raw water. Alum is a coagulant — it releases positively charged aluminium ions that neutralise the negative charges on particles, allowing them to collide and stick together. The dose rate depends on raw turbidity — more turbidity means more alum needed.

In the simulator, the **Alum Dose** coil controls the dosing pump. The dose rate (HR 40009) is a holding register.

**Critical factor:** pH must be in the right range (6.0-7.5) for alum to work. If pH is too high or too low, the alum doesn't form floc effectively, and turbidity removal is poor. This is why pH monitoring is essential.

### 3. Flocculation

**Purpose:** Gently mix the coagulated water so the tiny destabilised particles collide and form larger clumps called **floc**.

Flocculation tanks have slow-speed paddle mixers. The mixing must be gentle — too fast and the fragile floc breaks apart. Too slow and particles don't collide enough.

Floc grows from microscopic to visible (1-5mm) over 20-30 minutes. Good floc is dense and settles quickly. Poor floc is small, light, and hard to remove.

### 4. Sedimentation / Clarification

**Purpose:** Let gravity pull the heavy floc particles to the bottom.

Water flows slowly through large sedimentation basins. Floc settles to the bottom as sludge, and clearer water flows over weirs at the top. Residence time is typically 2-4 hours.

The sludge is periodically removed and sent to a drying bed or lagoon.

**Effectiveness depends on:**
- Floc quality (which depends on coagulation, which depends on pH and alum dose)
- Flow rate (higher flow = less settling time = worse removal)
- Temperature (cold water is more viscous, so particles settle more slowly)

### 5. Filtration

**Purpose:** Remove remaining particles that didn't settle out.

Water passes through beds of sand and/or anthracite coal. Particles are trapped in the gaps between grains. This is the last physical barrier — if filtration fails, pathogens reach consumers.

**Key parameter:** Filter differential pressure (DP). As the filter loads with particles, DP rises. When it gets too high, the filter is backwashed — clean water is pumped backwards through the bed to flush out the trapped particles.

In the simulator, the **Backwash Valve** coil opens the backwash line. The **Filter DP** holding register (HR 40010) tracks loading. The **Backwash Cycle Count** (HR 40013) tracks how many backwashes have occurred.

**Filtered turbidity** should be <0.1 NTU. If it's >1 NTU, something is wrong — likely the filter is overloaded, the coagulation/flocculation upstream is poor, or the filter media needs replacing.

### 6. Disinfection (Chlorination)

**Purpose:** Kill pathogenic bacteria, viruses, and (to some extent) protozoa.

Chlorine is dosed into the filtered water. The water then passes through a **contact tank** — a long, baffled channel that ensures every drop of water has a minimum contact time with chlorine (typically 30 minutes at peak flow).

The key concept is **CT value** — Concentration (mg/L) × Time (minutes). Regulatory requirements specify minimum CT values for different pathogens. For example, 99.9% (3-log) inactivation of Giardia at 20°C requires CT ≈ 45 mg·min/L.

In the simulator, the **Chlorine Dose** coil controls the dosing pump, and the **Chlorine Residual** holding register (HR 40004) tracks the measured residual after the contact tank.

**What can go wrong:**
- Dose too low → residual drops below 0.2 mg/L → no disinfection assurance → alarm
- Dose too high → residual above 4 mg/L → taste/odour complaints, regulatory breach
- High organics (rain event) → chlorine consumed faster → need to increase dose rate
- High pH → chlorine less effective → need higher dose for same kill

### 7. Treated Water Storage

Disinfected water enters the clear water reservoir. This provides:
- **Storage buffer** — continues supply when the plant is offline (e.g. during turbidity shutdown)
- **Additional contact time** — more time for chlorine to work
- **Pressure head** — gravity feeds the distribution network (depending on topography)

In the simulator, **Reservoir Level** (HR 40007) tracks this. The reservoir drains when the plant is offline and demand continues.

### 8. Distribution

Water flows from the reservoir through the pipe network to consumers. Chlorine residual decays as water travels, which is why it must leave the plant with enough residual to still be >0.2 mg/L at the furthest tap.

---

## Factors That Affect Treatment Effectiveness

### Rainfall and Catchment Events

This is the biggest operational challenge at Tunnel Hill. The Freshwater Creek catchment is tropical rainforest — heavy wet-season storms dump intense rainfall that washes soil, vegetation, and organic matter into the waterway.

**Effects cascade through the entire plant:**

1. **Turbidity spikes** — raw water goes from 3 NTU to 500+ NTU in hours
2. **pH drops** — organic acids from decomposing vegetation make runoff acidic
3. **Chlorine demand increases** — more organic matter to oxidise
4. **Flow increases** — more water entering the intake
5. **Temperature drops slightly** — cooler rainwater mixes in
6. **Coagulant demand increases** — more alum needed for higher turbidity
7. **Filter loading accelerates** — more particles reaching filters, more frequent backwash needed

If turbidity exceeds 500 NTU, the plant shuts down automatically. Operators must wait for the catchment to clear (hours to days depending on the storm), then manually restart. During this time, the reservoir is the only supply — if it drains before the plant restarts, Cairns has a water supply problem.

### Chemical Dosing Balance

Treatment is a balancing act:
- Too little alum → poor floc → turbidity breaks through filters
- Too much alum → residual aluminium in treated water (health concern), wasted chemical cost
- Too little chlorine → inadequate disinfection → public health risk
- Too much chlorine → disinfection byproducts (THMs — trihalomethanes) form when chlorine reacts with organic matter. THMs are a cancer risk at high levels.

Operators adjust doses based on raw water quality, which changes constantly.

### Temperature and Season

Cairns has two seasons that matter for water treatment:
- **Wet season (Dec-Apr):** High temperatures (25-30°C), heavy rainfall, high turbidity events, high chlorine demand, faster biological growth. The hardest time to operate.
- **Dry season (May-Nov):** Lower temperatures (20-25°C), stable low turbidity, lower chemical demand, easier to maintain water quality.

### Filter Condition

Filters degrade over time. The sand grains wear down, mud balls form (clumps of particles that don't backwash out), and biological growth can clog the bed. Regular maintenance and media replacement are essential.

### Source Water Quality

Copperlode Falls Dam provides relatively good source water compared to river intakes. The dam acts as a settling basin — heavy particles settle in the dam before water is drawn off. However, after heavy rain, even dam water quality degrades as inflows carrying sediment mix through the storage.

---

## Glossary

| Term | Definition |
|------|-----------|
| **NTU** | Nephelometric Turbidity Unit. Standard unit for turbidity measurement. |
| **Coagulation** | Adding chemicals (alum) to destabilise suspended particles so they can clump together. |
| **Flocculation** | Gentle mixing to encourage destabilised particles to form larger clumps (floc). |
| **Floc** | The clumps of particles formed during flocculation. Good floc is large, dense, and settles quickly. |
| **Sedimentation** | Allowing floc to settle out of water by gravity in a large basin. |
| **Filtration** | Passing water through sand/media beds to remove remaining particles. |
| **Backwash** | Reversing flow through a filter to flush out accumulated particles. |
| **Filter DP** | Differential pressure across a filter bed. High DP means the filter is clogged. |
| **Disinfection** | Killing pathogens, typically with chlorine. |
| **Chlorine residual** | Free chlorine remaining in water after initial demand is satisfied. |
| **CT value** | Concentration × Time — the measure of disinfection effectiveness. |
| **Contact tank** | Baffled channel ensuring minimum chlorine contact time. |
| **THMs** | Trihalomethanes — disinfection byproducts formed when chlorine reacts with organic matter. |
| **Alum** | Aluminium sulfate — the most common coagulant in Australian water treatment. |
| **Diurnal** | Daily cycle. Water demand follows a diurnal pattern (low overnight, peaks morning and evening). |
| **Catchment** | The land area that drains into a water source. Freshwater Creek's catchment is tropical rainforest. |
| **ML/day** | Megalitres per day — common unit for plant production rate (1 ML = 1,000,000 litres). |
| **ADWG** | Australian Drinking Water Guidelines — the national standard for water quality. |
| **Log removal** | Logarithmic measure of pathogen removal. 3-log = 99.9% removal, 4-log = 99.99%. |
| **Colloidal** | Particles too small to settle by gravity (1-100 nm). Must be coagulated first. |
| **Humic acids** | Organic compounds from decomposing vegetation. Give water a brown/yellow colour and increase chlorine demand. |

---

## How This Maps to the Simulator

| Real Plant Concept | Simulator Component |
|---|---|
| Raw turbidity from catchment | `turb_raw` — OU random walk + rain event spikes |
| Turbidity auto-shutdown at 500 NTU | `WTPSimulator.tick()` state machine |
| Filtered turbidity after sand filters | `turb_filtered` — 98% removal when running |
| pH affected by rain | `ph` — daily drift + rain event pH drop |
| Chlorine dosing and decay | `ChlorineDoseModel` — sawtooth pattern with decay |
| Diurnal demand pattern | `diurnal_flow()` — AM/PM peaks, overnight low |
| Reservoir buffer during shutdown | `reservoir_level` — integrates inflow vs demand |
| Filter loading and backwash | `filter_dp` — rises during operation, resets on backwash |
| Alarm generation | `alarm_word` bitfield — thresholds on all parameters |
| Operator controls (start/stop/backwash) | Modbus coils — toggled via dashboard or Ignition |
