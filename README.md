# Semiconductor STDF Multi-Site Yield & Shmoo Analyzer (`semicon-stdf-yield-analyzer`)

**Author:** David Rainey (MS ECE, Former Intel Product Development Engineer)  
**Primary Discipline:** Post-Silicon Validation, ATE Parametric Analytics, Test Time Reduction (TTR)  
**Target Roles:** Senior Post-Silicon Validation Engineer / Senior Field Applications Engineer (ATE / Systems Test)  

---

## 1. Executive Summary & Problem Framing

In high-volume semiconductor manufacturing (HVM) and post-silicon burn-in validation, automated test equipment (ATE) executes complex pattern sets across multi-site test heads (2, 4, 8, or 16 sockets in parallel). These platforms log gigabytes of **Standard Test Data Format (STDF)** binary records, containing Parametric Test Records (PTR) and Functional Test Records (FTR).

Validation and test development teams face three persistent operational challenges:

1. **Multi-Site Channel Drift Masked by Global Statistics:** Traditional aggregate yield reporting averages parametric distributions across all tester sites. If Site 3 develops pogo-pin contact wear or leakage drift while Sites 1, 2, and 4 run clean, aggregate statistics obscure the excursion until an entire wafer or lot is halted.
2. **Timing Delay vs. Hard Defect Ambiguity:** When digital vector miscompares occur during at-speed pattern execution, engineers require fast operational margin characterization (voltage vs. frequency Shmoo profiling) to determine whether a failure is a hard stuck-at fault or an AC path-delay marginality.
3. **Heavyweight Tooling Overhead:** Standard enterprise data analysis suites require expensive desktop licenses, slow network handshakes, or cumbersome GUIs that cannot easily be invoked from headless tester controllers or CI regression pipelines.

### The Solution
`semicon-stdf-yield-analyzer` is a high-speed, zero-dependency parametric analytics engine and terminal Shmoo generator written in Python. It evaluates statistical process capability ($C_p, C_{pk}$) independently across physical test sites, automatically flags channel mean drift, simulates resistive-delay defect boundaries, and profiles Test Time Reduction (TTR) distribution.

---

## 2. System Architecture Flow

```
┌────────────────────┐     ┌────────────────────────────────────────────────────────┐
│  Raw ATE Records   │     │                   Core Analytics Pipeline              │
├────────────────────┤     ├───────────────────┬────────────────────────────────────┤
│ • STDF / PTR / FTR │────►│ Parametric Record │ Site grouping, limit extraction,   │
│ • Voltage / Freq   │     │ Ingestion Engine  │ outlier boundary classification    │
│ • Execution Timers │     └─────────┬─────────┘                                    │
└────────────────────┘               ▼                                              │
                    ┌─────────────────────────────────┐                             │
                    │ Multi-Site Cpk Profiling Engine │ Evaluates Mean, 3-Sigma,    │
                    │ (Site 1 - 4 Independence)       │ Cp, Cpk, and Delta-Shift    │
                    └────────────────┬────────────────┘                             │
                                     ▼                                              │
                    ┌─────────────────────────────────┐                             │
                    │ 2D Operating Margin Generator   │ Maps VDD (0.75V - 1.20V) vs │
                    │ (ANSI Terminal Shmoo Engine)    │ Fmax (2.00GHz - 4.60GHz)    │
                    └────────────────┬────────────────┘                             │
                                     ▼                                              │
┌───────────────────────────────────────────────────────────────────────────────────┤
│                                 Actionable Diagnostics                            │
├───────────────────────────────────────────────────────────────────────────────────┤
│ • Automated Channel Drift Alert (Isolates socket maintenance from silicon scrap)  │
│ • Operating Envelope Collapse Visualization (Resistive via / cell delay defect)   │
│ • Test Time Reduction (TTR) Execution Breakdown (Identifies cycle-time sinks)     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mathematical & Physical Principles

### Process Capability Modeling ($C_p$ vs. $C_{pk}$)
The engine processes parametric distributions by calculating potential capability ($C_p$) and actual centering capability ($C_{pk}$) against upper and lower specification limits ($USL, LSL$):

$$C_p = \frac{USL - LSL}{6\sigma}$$

$$C_{pk} = \min\left(\frac{USL - \mu}{3\sigma},\, \frac{\mu - LSL}{3\sigma}\right)$$

* When $C_p \approx C_{pk} \ge 1.67$, the process is capable and centered.
* When $C_p$ is healthy ($>2.0$) but $C_{pk}$ collapses ($<1.67$), the distribution spread is tight but the mean ($\mu$) has shifted. The engine detects this delta $(C_p - C_{pk} > 0.60)$ across individual sites to isolate **pogo-pin contamination, tester pin-electronics drift, or local socket thermal gradients**.

### Silicon Scaling & Shmoo Boundary Dynamics
Operating frequency limits ($F_{max}$) scale proportionally with gate overdrive voltage:

$$F_{max} \propto \frac{V_{DD} - V_t}{C_L}$$

* **Nominal Silicon:** As supply voltage sweeps from $0.75\text{ V}$ to $1.20\text{ V}$, $F_{max}$ increases along an empirical saturation curve.
* **Resistive Via / Delay Defect:** A high-resistance contact adds an $R_{defect} \cdot C_{interconnect}$ delay step. At lower voltages, reduced drive current exacerbates this delay, causing setup time violations. In `--defect` mode, the engine demonstrates the characteristic collapse of the upper-frequency pass envelope between $0.85\text{ V}$ and $1.05\text{ V}$.

---

## 4. Repository Structure

```
semicon-stdf-yield-analyzer/
├── .gitignore                         # Python cache & runtime exclusions
├── requirements.txt                   # Dependency manifest (uses Python stdlib)
├── README.md                          # Engineering specification and architectural overview
└── semicon_stdf_yield_analyzer.py     # Unified analytics engine and Shmoo renderer
```

---

## 5. Usage & Verification

### Prerequisites
* Python 3.10 or higher
* POSIX-compliant terminal (Linux Mint, Ubuntu, macOS, or WSL)

### Running the Full Demonstration
Execute the full multi-site parametric analysis, Shmoo plot, and TTR profiler:
```bash
python3 semicon_stdf_yield_analyzer.py --demo
```

### Simulating a Resistive Via / Timing Delay Defect
To visualize how an interconnect delay defect constrains the operating window:
```bash
python3 semicon_stdf_yield_analyzer.py --shmoo --defect
```

### Sample Terminal Execution Output

```text
============================================================================
SEMICONDUCTOR STDF MULTI-SITE YIELD & PROCESS CAPABILITY REPORT
============================================================================

TEST: IDDQ_CORE_LEAKAGE  [Limits: 5.0 mA to 25.0 mA]

 Site   │ Count   │ Mean (mA)   │ StdDev    │ Cp      │ Cpk     │ Channel Status 
────────────────────────────────────────────────────────────────────────────
 Site 1 │ 50      │ 14.051      │ 0.684     │  4.88   │  4.41   │ [OK] NOMINAL
 Site 2 │ 50      │ 14.248      │ 0.805     │  4.14   │  3.83   │ [OK] NOMINAL
 Site 3 │ 50      │ 18.367      │ 1.455     │  2.29   │  1.52   │ [!] DRIFT DETECTED
 Site 4 │ 50      │ 14.295      │ 0.760     │  4.39   │  4.08   │ [OK] NOMINAL

────────────────────────────────────────────────────────────────────────────
ENGINEERING ACTIONABLE TRIAGE:
  • Site 3 exhibits +4.1 mA parametric mean shift relative to Sites 1, 2, and 4.
  • Process capability (Cpk) degraded on Site 3. Inspect socket 3 pogo pins for solder transfer.
  • Action: Schedule preventive maintenance for Site 3 socket before wafer sort lot halt.

============================================================================
SHMOO PLOT: VDD CORE (V) vs. CLOCK FREQUENCY (GHz)
============================================================================
 4.60 GHz │ *  *  *  *  *  *  *  *  .  . │
 4.40 GHz │ *  *  *  *  *  *  *  .  .  . │
 4.20 GHz │ *  *  *  *  *  *  .  .  .  . │
 4.00 GHz │ *  *  *  *  *  *  .  .  .  . │
 3.80 GHz │ *  *  *  *  *  .  .  .  .  . │
 3.60 GHz │ *  *  *  *  *  .  .  .  .  . │
 3.40 GHz │ *  *  *  *  .  .  .  .  .  . │
 3.20 GHz │ *  *  *  .  .  .  .  .  .  . │
 3.00 GHz │ *  *  *  .  .  .  .  .  .  . │
 2.80 GHz │ *  *  *  .  .  .  .  .  .  . │
 2.60 GHz │ *  *  *  .  .  .  .  .  .  . │
 2.40 GHz │ *  *  *  .  .  .  .  .  .  . │
 2.20 GHz │ *  *  *  .  .  .  .  .  .  . │
 2.00 GHz │ *  *  *  .  .  .  .  .  .  . │
          └──────────────────────────────┘
           .75 .80 .85 .90 .95 .00 .05 .10 .15 .20 
                   VDD Core Voltage (V)  [ . = PASS  * = FAIL ]

============================================================================
TEST TIME REDUCTION (TTR) EXECUTION BREAKDOWN
============================================================================
 ATPG_SCAN_BURST_MAX            │  1420.5 ms │  58.9% │ ██████████████
 IDDQ_LEAKAGE_16_PATTERNS       │   480.2 ms │  19.9% │ ████
 BIST_MEMORY_ARRAY_EXEC         │   310.8 ms │  12.9% │ ███
 POWER_RAIL_RAMP_CHECK          │   115.4 ms │   4.8% │ █
 CONTINUITY_PARAMETRIC_KELVIN   │    85.0 ms │   3.5% │ 
============================================================================
```

---

## 6. Strategic Context: Connecting Code to Post-Silicon Validation

This utility directly implements and validates core post-silicon engineering methodologies:
* **Yield Protection:** Separates physical test head drift from true fabrication process variations.
* **Defect Characterization:** Replaces guesswork with deterministic voltage-frequency characterization to isolate path delays from catastrophic stuck-at faults.
* **Test Floor Economics:** Pinpoints long-running ATPG and BIST modules to prioritize pattern compression and vector pruning.
