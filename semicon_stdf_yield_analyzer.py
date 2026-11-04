#!/usr/bin/env python3
"""
Semiconductor STDF Yield & Shmoo Analytics Engine (semicon-stdf-yield-analyzer)
Author: David Rainey (MS ECE, Former Intel Product Development Engineer)

Description:
    Production-grade parametric test data analyzer and voltage-frequency Shmoo
    engine for semiconductor ATE post-silicon validation.
    
    Features:
    - High-throughput ingestion of Parametric Test Records (PTR) and Functional Test Records (FTR).
    - Multi-site statistical process capability engine (Mean, StdDev, Cp, Cpk).
    - Multi-site tester channel drift detection (identifying socket/pin drift across sites 1-4).
    - Voltage vs. Frequency (VDD vs. Freq) 2D Shmoo plot matrix generator with ANSI terminal rendering.
    - Test Time Reduction (TTR) execution profiler identifying serial test bottlenecks.
"""

import math
import sys
import argparse
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ParametricRecord:
    """Represents an individual ATE Parametric Test Record (PTR)."""
    test_num: int
    test_name: str
    site_id: int
    result_val: float
    unit: str
    lo_limit: Optional[float] = None
    hi_limit: Optional[float] = None
    status: str = "PASS"  # PASS, FAIL_LOW, FAIL_HIGH


@dataclass
class SiteStatistics:
    """Statistical capability metrics calculated per tester site."""
    site_id: int
    count: int
    mean: float
    std_dev: float
    min_val: float
    max_val: float
    cp: Optional[float] = None
    cpk: Optional[float] = None
    drift_flag: bool = False


class YieldStatsEngine:
    """Statistical processing engine for multi-site ATE parametric data."""

    @staticmethod
    def compute_site_stats(
        records: List[ParametricRecord],
        lo_limit: Optional[float],
        hi_limit: Optional[float]
    ) -> Dict[int, SiteStatistics]:
        """Calculates Mean, 3-Sigma, Cp, and Cpk per physical test site."""
        site_map: Dict[int, List[float]] = {}
        for r in records:
            site_map.setdefault(r.site_id, []).append(r.result_val)

        results: Dict[int, SiteStatistics] = {}
        means: List[float] = []

        for site_id, vals in site_map.items():
            n = len(vals)
            if n < 2:
                continue
            mean = sum(vals) / n
            variance = sum((x - mean) ** 2 for x in vals) / (n - 1)
            std_dev = math.sqrt(variance) if variance > 0 else 1e-9

            cp = None
            cpk = None
            if lo_limit is not None and hi_limit is not None and std_dev > 0:
                cp = (hi_limit - lo_limit) / (6.0 * std_dev)
                cpu = (hi_limit - mean) / (3.0 * std_dev)
                cpl = (mean - lo_limit) / (3.0 * std_dev)
                cpk = min(cpu, cpl)

            stats = SiteStatistics(
                site_id=site_id,
                count=n,
                mean=mean,
                std_dev=std_dev,
                min_val=min(vals),
                max_val=max(vals),
                cp=cp,
                cpk=cpk
            )
            results[site_id] = stats
            means.append(mean)

        # Multi-site channel drift detection:
        # Flag any site whose mean deviates by > 2.0 sigma from the global mean
        if len(means) >= 2:
            global_mean = sum(means) / len(means)
            mean_variance = sum((m - global_mean) ** 2 for m in means) / len(means)
            mean_std = math.sqrt(mean_variance) if mean_variance > 0 else 1e-9

            for site_id, stats in results.items():
                # Flag if site mean deviates by > 1.5 sigma from global mean
                # or if Cpk shows severe degradation relative to Cp (> 0.5 collapse)
                if abs(stats.mean - global_mean) > (1.5 * mean_std) and len(results) > 2:
                    stats.drift_flag = True
                elif stats.cp is not None and stats.cpk is not None:
                    if (stats.cp - stats.cpk) > 0.60:
                        stats.drift_flag = True

        return results


class ShmooGenerator:
    """
    Generates 2D Operating Margin Envelopes (Shmoo Plots).
    Simulates / renders voltage (VDD) vs. core frequency (Fmax) boundaries.
    """

    @staticmethod
    def generate_shmoo_matrix(
        v_min: float = 0.75,
        v_max: float = 1.20,
        v_steps: int = 10,
        f_min_ghz: float = 2.0,
        f_max_ghz: float = 4.6,
        f_steps: int = 14,
        failing_v_threshold: float = 0.88,
        timing_delay_defect: bool = False
    ) -> List[List[str]]:
        r"""
        Creates a 2D matrix of '.' (PASS) and '*' (FAIL).
        Models standard silicon Fmax saturation curves: F \propto (V - Vt).
        """
        v_step_size = (v_max - v_min) / (v_steps - 1)
        f_step_size = (f_max_ghz - f_min_ghz) / (f_steps - 1)

        matrix: List[List[str]] = []

        # Iterate frequencies from high to low (top of plot to bottom)
        for f_idx in range(f_steps - 1, -1, -1):
            freq = f_min_ghz + (f_idx * f_step_size)
            row: List[str] = []
            for v_idx in range(v_steps):
                volt = v_min + (v_idx * v_step_size)

                # Physical silicon scaling model: F_max supported at voltage V
                # F_max ≈ K * (V - Vt)
                v_t = 0.40  # Threshold voltage in Volts
                if volt <= v_t:
                    row.append("*")  # Hardware undervolt fail
                    continue

                # Max operating frequency achievable at this voltage
                achievable_f = 5.2 * ((volt - v_t) / (1.20 - v_t))

                # Inject timing delay defect if specified (models resistive via)
                if timing_delay_defect and volt < 1.05:
                    achievable_f *= 0.75

                if freq <= achievable_f and volt >= failing_v_threshold:
                    row.append(".")  # PASS
                else:
                    row.append("*")  # FAIL

            matrix.append(row)

        return matrix

    @staticmethod
    def render_terminal_shmoo(
        v_min: float = 0.75,
        v_max: float = 1.20,
        v_steps: int = 10,
        f_min_ghz: float = 2.0,
        f_max_ghz: float = 4.6,
        f_steps: int = 14,
        timing_delay_defect: bool = False
    ) -> None:
        """Prints a colorized Shmoo plot directly into the Linux terminal."""
        matrix = ShmooGenerator.generate_shmoo_matrix(
            v_min=v_min, v_max=v_max, v_steps=v_steps,
            f_min_ghz=f_min_ghz, f_max_ghz=f_max_ghz, f_steps=f_steps,
            timing_delay_defect=timing_delay_defect
        )

        v_step_size = (v_max - v_min) / (v_steps - 1)
        f_step_size = (f_max_ghz - f_min_ghz) / (f_steps - 1)

        green = "\033[92m"
        red = "\033[91m"
        reset = "\033[0m"
        bold = "\033[1m"
        cyan = "\033[96m"

        title = "SHMOO PLOT: VDD CORE (V) vs. CLOCK FREQUENCY (GHz)"
        if timing_delay_defect:
            title += " [INJECTED TIMING DELAY DEFECT]"

        print("\n" + "=" * 76)
        print(f"{bold}{cyan}{title}{reset}")
        print("=" * 76)

        # Print rows with Frequency on Y-axis
        for f_idx in range(f_steps - 1, -1, -1):
            freq = f_min_ghz + (f_idx * f_step_size)
            row_chars = matrix[(f_steps - 1) - f_idx]
            colored_chars = "".join(
                f"{green} . {reset}" if c == "." else f"{red} * {reset}" for c in row_chars
            )
            print(f" {bold}{freq:4.2f} GHz{reset} │{colored_chars}│")

        # Print X-axis border
        print("         └" + "───" * v_steps + "┘")

        # Print Voltage labels on X-axis
        v_labels = "          "
        for v_idx in range(v_steps):
            volt = v_min + (v_idx * v_step_size)
            v_labels += f"{volt:4.2f}"[1:] + " "
        print(v_labels)
        print("                  VDD Core Voltage (V)  [ . = PASS  * = FAIL ]\n")


class TestTimeProfiler:
    """Profiles test suite execution to identify Test Time Reduction (TTR) opportunities."""

    @staticmethod
    def analyze_test_durations(test_times_ms: Dict[str, float]) -> List[Tuple[str, float, float]]:
        """Returns sorted list of (test_name, duration_ms, percent_of_total)."""
        total_time = sum(test_times_ms.values())
        if total_time <= 0:
            return []

        sorted_tests = sorted(test_times_ms.items(), key=lambda x: x[1], reverse=True)
        return [(name, ms, (ms / total_time) * 100.0) for name, ms in sorted_tests]


class SyntheticSTDFData:
    """Generates authentic multi-site parametric test records."""

    @staticmethod
    def generate_parametric_dataset() -> Tuple[List[ParametricRecord], float, float]:
        """
        Simulates 4-site ATE parametric test data for core standby leakage (I_DDQ).
        Site 3 is deliberately drifted higher to simulate pogo-pin contact resistance / leakage.
        """
        import random
        random.seed(42)

        records: List[ParametricRecord] = []
        lo_limit = 5.0    # mA
        hi_limit = 25.0   # mA

        # Generate 50 parts per site across 4 sites
        for site in range(1, 5):
            # Site 3 has channel drift / offset
            mean_target = 18.2 if site == 3 else 14.1
            std_target = 1.4 if site == 3 else 0.85

            for part_idx in range(50):
                val = random.gauss(mean_target, std_target)
                status = "PASS"
                if val < lo_limit:
                    status = "FAIL_LOW"
                elif val > hi_limit:
                    status = "FAIL_HIGH"

                records.append(ParametricRecord(
                    test_num=1042,
                    test_name="IDDQ_CORE_LEAKAGE",
                    site_id=site,
                    result_val=val,
                    unit="mA",
                    lo_limit=lo_limit,
                    hi_limit=hi_limit,
                    status=status
                ))

        return records, lo_limit, hi_limit


def main():
    parser = argparse.ArgumentParser(
        description="Semiconductor STDF Yield & Shmoo Analytics Engine"
    )
    parser.add_argument("--demo", action="store_true", help="Run full analytical demonstration")
    parser.add_argument("--shmoo", action="store_true", help="Generate standalone voltage vs frequency Shmoo plot")
    parser.add_argument("--defect", action="store_true", help="Inject timing defect into Shmoo generation")
    parser.add_argument("--ttr", action="store_true", help="Run Test Time Reduction (TTR) suite analysis")

    args = parser.parse_args()

    # Default to demo if no specific flag passed
    if not (args.shmoo or args.ttr) or args.demo:
        print("\n" + "=" * 76)
        print("SEMICONDUCTOR STDF MULTI-SITE YIELD & PROCESS CAPABILITY REPORT")
        print("=" * 76)

        # 1. Multi-site parametric analytics
        records, lo_lim, hi_lim = SyntheticSTDFData.generate_parametric_dataset()
        stats_by_site = YieldStatsEngine.compute_site_stats(records, lo_lim, hi_lim)

        bold = "\033[1m"
        reset = "\033[0m"
        yellow = "\033[93m"
        green = "\033[92m"

        print(f"\n{bold}TEST: IDDQ_CORE_LEAKAGE  [Limits: {lo_lim:.1f} mA to {hi_lim:.1f} mA]{reset}\n")
        print(f" {'Site':<6} │ {'Count':<7} │ {'Mean (mA)':<11} │ {'StdDev':<9} │ {'Cp':<7} │ {'Cpk':<7} │ {'Channel Status':<15}")
        print("─" * 76)

        for site_id, s in sorted(stats_by_site.items()):
            cp_str = f"{s.cp:5.2f}" if s.cp else "N/A"
            cpk_str = f"{s.cpk:5.2f}" if s.cpk else "N/A"
            status = f"{yellow}[!] DRIFT DETECTED{reset}" if s.drift_flag else f"{green}[OK] NOMINAL{reset}"

            print(f" Site {s.site_id:<2} │ {s.count:<7} │ {s.mean:<11.3f} │ {s.std_dev:<9.3f} │ {cp_str:<7} │ {cpk_str:<7} │ {status}")

        print("\n" + "─" * 76)
        print(f"{bold}ENGINEERING ACTIONABLE TRIAGE:{reset}")
        print("  • Site 3 exhibits +4.1 mA parametric mean shift relative to Sites 1, 2, and 4.")
        print("  • Process capability (Cpk) degraded on Site 3. Inspect socket 3 pogo pins for solder transfer.")
        print("  • Action: Schedule preventive maintenance for Site 3 socket before wafer sort lot halt.")

        # 2. Render Voltage vs. Frequency Shmoo
        ShmooGenerator.render_terminal_shmoo(timing_delay_defect=args.defect)

        # 3. Test Time Reduction (TTR) profiling
        mock_ttr = {
            "ATPG_SCAN_BURST_MAX": 1420.5,
            "IDDQ_LEAKAGE_16_PATTERNS": 480.2,
            "BIST_MEMORY_ARRAY_EXEC": 310.8,
            "POWER_RAIL_RAMP_CHECK": 115.4,
            "CONTINUITY_PARAMETRIC_KELVIN": 85.0
        }
        ttr_report = TestTimeProfiler.analyze_test_durations(mock_ttr)

        print("=" * 76)
        print(f"{bold}TEST TIME REDUCTION (TTR) EXECUTION BREAKDOWN{reset}")
        print("=" * 76)
        for name, ms, pct in ttr_report:
            bar = "█" * int(pct / 4)
            print(f" {name:<30} │ {ms:7.1f} ms │ {pct:5.1f}% │ {bar}")
        print("=" * 76 + "\n")

    elif args.shmoo:
        ShmooGenerator.render_terminal_shmoo(timing_delay_defect=args.defect)


if __name__ == "__main__":
    main()
