# FILE: scenarios.py

"""
Defines a library of fault scenarios for the diagnostic simulation.

Each scenario is a dictionary containing all the necessary information to run
a complete simulation, including:
- description: A human-readable explanation of the fault chain.
- anomalies_to_introduce: The specific fault(s) to trigger in the EPICS simulator.
- agents_to_create: A list of agents required for this scenario.
- expected_outcome: A description of the successful diagnostic conclusion.
"""

def get_scenarios():
    """Returns a dictionary of all available fault scenarios."""

    SCENARIOS = {
        "1_cooling_failure": {
            "description": "A cooling valve gets stuck. The resulting pressure drop CAUSES the RF cavity to overheat after a short delay (thermal inertia).",
            "anomalies_to_introduce": [{
                "tick": 3, "pv_name": "COOL:valve_position", "type": "stuck", "value": 10
            }],
            "agents_to_create": ["Cooling_Agent", "RF_Agent", "AcceleratorDiagnostics", "LatticeLayoutAgent"],
            "expected_outcome": "The diagnostics agent correctly identifies the cooling system failure as the root cause of the RF temperature anomaly after observing the cascading failure."
        },

        "2_klystron_failure": {
            "description": "The Klystron suffers a partial failure. This immediately CAUSES reduced RF forward power, leading to beam instability.",
            "anomalies_to_introduce": [{
                "tick": 3, "pv_name": "RF:klystron_output", "type": "low"
            }],
            "agents_to_create": ["RF_Agent", "Klystron_Agent", "AcceleratorDiagnostics", "LatticeLayoutAgent"],
            "expected_outcome": "The diagnostics agent correctly identifies the Klystron as the root cause after the RF agent also reports a power anomaly."
        },

        "3_complex_klystron_and_vacuum_fault": {
            "description": "A cascading Klystron failure occurs, while simultaneously an unrelated vacuum pump shows a pressure spike. A true test of root cause analysis.",
             "anomalies_to_introduce": [
                {"tick": 3, "pv_name": "RF:klystron_output", "type": "low"},
                {"tick": 4, "pv_name": "VAC:sector1_pump:pressure", "type": "high"}
            ],
            "agents_to_create": ["RF_Agent", "Klystron_Agent", "Vacuum_Agent", "AcceleratorDiagnostics", "LatticeLayoutAgent"],
            "expected_outcome": "The diagnostics agent correctly identifies the Klystron as the root cause for the RF fault and flags the vacuum issue as a separate, non-causal event."
        }
    }
    return SCENARIOS