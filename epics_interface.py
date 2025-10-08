# FILE: epics_interface.py

"""
A mock interface for EPICS (Experimental Physics and Industrial Control System).

This module simulates the process variables (PVs) from various accelerator
components. It's designed to generate realistic, noisy data under normal
conditions and to introduce specific, sustained anomalies when triggered.

V2 Update: This version now includes physical coupling. Anomalies in one
component will realistically affect the PVs of connected downstream components.
"""
import random
import time

class EpicsSimulator:
    """
    Simulates reading values from EPICS process variables (PVs).
    """
    def __init__(self):
        self.pvs = {
            # Component: (Normal Value, Noise Amplitude)
            "BPM:1A:x": (0.0, 0.05),
            "BPM:1A:y": (0.0, 0.05),
            "RF:cavity_temp": (50.0, 1.5),
            "RF:forward_power": (10.0, 0.01),
            "RF:klystron_output": (100.0, 2.0),
            "CM:1A:hcorr": (0.0, 0.5),
            "CM:1A:vcorr": (0.0, 0.5),
            "VAC:sector1_pump:pressure": (1e-9, 5e-10),
            "COOL:water_pressure": (80.0, 1.0),
            "COOL:water_temp": (22.0, 0.5),
            "COOL:valve_position": (100.0, 0.0) # 100% open
        }
        self.anomalies = {}
        self.time_since_cooling_fault = 0
        print("--- EPICS Simulator Initialized (with Physical Coupling) ---")

    def get_pv_value(self, pv_name):
        """
        Returns the current value of a given PV, including noise and any active anomaly.
        This version includes physical coupling logic.
        """
        if pv_name not in self.pvs:
            return None

        base, noise = self.pvs[pv_name]
        current_value = base + random.uniform(-noise, noise)

        # --- ANOMALY APPLICATION (Direct Faults) ---
        if pv_name in self.anomalies:
            anomaly_type = self.anomalies[pv_name]
            if anomaly_type == 'low':
                current_value *= 0.1
            elif anomaly_type == 'high':
                current_value *= 1.15
            elif anomaly_type == 'stuck':
                current_value = self.anomalies.get(f"{pv_name}_value", base)

        # --- PHYSICAL COUPLING (Cascading Faults) ---
        # A Klystron fault will cause a drop in the RF forward power.
        if pv_name == 'RF:forward_power' and 'RF:klystron_output' in self.anomalies:
            klystron_base = self.pvs['RF:klystron_output'][0]
            klystron_actual = self.get_pv_value('RF:klystron_output')
            # Forward power is now proportional to the klystron's actual output.
            current_value *= (klystron_actual / klystron_base)

        # A cooling fault will cause the RF cavity temperature to rise over time.
        if pv_name == 'RF:cavity_temp' and 'COOL:valve_position' in self.anomalies:
            # Simulate thermal inertia: temperature increases each tick the fault is active.
            current_value += (self.time_since_cooling_fault * 5.0)

        return current_value

    def introduce_anomaly(self, pv_name, anomaly_type, value=None):
        """
        Introduces a sustained anomaly to a specific PV.
        """
        if pv_name in self.pvs:
            self.anomalies[pv_name] = anomaly_type
            if value is not None:
                self.anomalies[f"{pv_name}_value"] = value

            if 'COOL' in pv_name:
                self.time_since_cooling_fault = 1 # Start the timer for thermal effects

            print(f"\n==================================================")
            print(f"!!! INTRODUCING ANOMALY: {anomaly_type.upper()} ON {pv_name} !!!")
            print(f"==================================================\n")


    def get_all_pvs(self):
        """
        Returns a dictionary of all current PV values.
        """
        if self.time_since_cooling_fault > 0:
            self.time_since_cooling_fault += 1 # Increment timer if cooling fault is active
        return {pv: self.get_pv_value(pv) for pv in self.pvs}