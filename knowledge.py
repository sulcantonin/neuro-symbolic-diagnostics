"""
This module serves as the knowledge base for the LatticeLayoutAgent. It is the
single source of truth for the physical layout, component connections, and basic
properties of the simulated Advanced Light Source (ALS) sector.

The primary purpose of this file is to provide a structured, queryable model
of the machine's hardware, enabling the AcceleratorDiagnostics agent to verify
the physical plausibility of its causal hypotheses. For instance, if an RF agent
suspects a cooling issue, the diagnostics agent can query this model to confirm
that the specific RF cavity is indeed serviced by the specific cooling loop in question.
"""

# --- LATTICE LAYOUT DEFINITION ---
# The lattice is represented as a Python dictionary.
# - Keys: The top-level keys are the EPICS Process Variable (PV) name prefixes,
#         which uniquely identify each major component (e.g., "RF:cavity").
# - Values: Each value is another dictionary containing the properties of that component.
#   - 'type': A human-readable category for the component.
#   - 'description': A brief explanation of the component's function.
#   - 'connected_to': A critical sub-dictionary defining direct physical links. For example,
#                     an RF cavity is connected to a specific power source and cooling loop.
#   - 'services': The inverse of 'connected_to'. It lists other components that this
#                 component provides a service to (e.g., a cooling loop 'services' an RF cavity).
#   - 'sensors': A list of PVs for sensors that belong to this component. This allows
#                the model to trace a sensor alert back to its parent hardware.

LATTICE_LAYOUT = {
    # -- RF and Cooling Section --
    # This section defines the core components responsible for beam acceleration and thermal management.
    "RF:cavity": {
        "type": "RF_Cavity",
        "description": "Main Radio-Frequency cavity for accelerating the beam. Highly sensitive to temperature fluctuations.",
        "connected_to": {
            "cooling": "COOL:primary_loop",
            "power": "RF:klystron",
            "beamline": "BL:1",
            "vacuum": "VAC:sector1_pump"
        }
    },
    "RF:klystron": {
        "type": "Klystron",
        "description": "High-power amplifier that generates the radio-frequency waves for the RF cavity.",
        "services": ["RF:cavity"],
        "sensors": ["RF:klystron:voltage", "RF:klystron_output"] # <- Corrected name
    },
    "COOL:primary_loop": {
        "type": "Cooling_Loop",
        "description": "Main deionized water cooling loop for critical, high-heat components like the RF cavity and magnets.",
        "services": ["RF:cavity", "MAG:quad_1A"],
        "sensors": ["COOL:water_pressure", "COOL:valve_position"]
    },
    "COOL:secondary_loop": {
        "type": "Cooling_Loop",
        "description": "Secondary, lower-priority cooling loop for non-critical diagnostics and electronics racks.",
        "services": ["DIAG:screen_monitor"], # Crucially, does NOT service the main RF cavity.
        "sensors": []
    },

    # -- Magnet and Power Supply Section --
    # Defines the electromagnets used to focus and steer the beam, and their dedicated power supplies.
    "MAG:quad_1A": {
        "type": "Quadrupole_Magnet",
        "description": "A powerful focusing quadrupole magnet located in Sector 1A. Requires stable power and cooling.",
        "connected_to": {
            "power": "PS:quad_1A",
            "cooling": "COOL:primary_loop",
            "beamline": "BL:1"
        }
    },
    "PS:quad_1A": {
        "type": "Power_Supply",
        "description": "High-precision power supply dedicated to the 1A quadrupole magnet.",
        "services": ["MAG:quad_1A"],
        "sensors": ["PS:quad_1A:current", "PS:quad_1A:voltage"]
    },

    # -- Vacuum Section --
    # Defines components responsible for maintaining the ultra-high vacuum necessary for beam transport.
    "VAC:sector1_pump": {
        "type": "Ion_Pump",
        "description": "Primary ion pump for maintaining ultra-high vacuum in Sector 1. A leak here affects the whole sector.",
        "services": ["RF:cavity", "BPM:1A"],
        "sensors": ["VAC:sector1_pump:pressure"]
    },

    # -- Beamline Diagnostics Section --
    # Defines the instruments used to measure the properties of the electron beam itself.
    "BPM:1A": {
        "type": "Beam_Position_Monitor",
        "description": "Beam Position Monitor in Sector 1A. Measures the precise transverse position of the beam.",
        "connected_to": {
            "beamline": "BL:1",
            "vacuum": "VAC:sector1_pump"
        }
    }
}

class LatticeModel:
    """
    An interface to the accelerator's physical layout knowledge base.

    This class provides helper methods to abstract the process of querying the
    LATTICE_LAYOUT dictionary, making it easier for the diagnostics agent to
    ask concrete questions like "Are these two components physically connected?".
    """
    def __init__(self, layout):
        """
        Initializes the LatticeModel with a specific layout structure.
        Args:
            layout (dict): The LATTICE_LAYOUT dictionary defining the accelerator structure.
        """
        self.layout = layout

    def are_components_connected(self, upstream_component_pv_prefix, downstream_component_pv_prefix, connection_type="cooling"):
        """
        Checks if a downstream component is physically serviced by an upstream one via a specific connection type.
        Instead of a boolean, this now returns a dictionary containing a boolean and a human-readable reason
        to make the simulation output more informative.

        Args:
            upstream_component_pv_prefix (str): The PV name of the system providing a service (e.g., 'COOL:water_pressure').
            downstream_component_pv_prefix (str): The PV name of the system receiving the service (e.g., 'RF:cavity').
            connection_type (str): The type of connection to check (e.g., 'cooling', 'power', 'vacuum').

        Returns:
            dict: A dictionary with a 'connected' boolean and a 'reason' string.
        """
        # First, find the actual parent component for the upstream PV (e.g., 'COOL:water_pressure' -> 'COOL:primary_loop').
        upstream_component = self._find_component_by_sensor(upstream_component_pv_prefix)
        if not upstream_component:
            return {
                "connected": False,
                "reason": f"Connection check failed: The upstream PV '{upstream_component_pv_prefix}' does not map to a known component in the lattice model."
            }


        downstream_info = self.layout.get(downstream_component_pv_prefix)
        if not downstream_info:
            return {
                "connected": False,
                "reason": f"Connection check failed: The downstream component '{downstream_component_pv_prefix}' does not exist in the lattice model."
            }

        # Logic Check 1: Does the downstream component explicitly state it is connected to the upstream component?
        connection = downstream_info.get("connected_to", {}).get(connection_type)
        if connection == upstream_component:
            return {
                "connected": True,
                "reason": f"Connection verified: The downstream component '{downstream_component_pv_prefix}' explicitly lists '{upstream_component}' as its '{connection_type}' source."
            }

        # Logic Check 2: Does the upstream component explicitly state it services the downstream component?
        services = self.layout.get(upstream_component, {}).get("services", [])
        if downstream_component_pv_prefix in services:
            return {
                "connected": True,
                "reason": f"Connection verified: The upstream component '{upstream_component}' lists '{downstream_component_pv_prefix}' in its services."
            }

        # If neither check passes, they are not connected in the specified way.
        return {
            "connected": False,
            "reason": f"Connection check failed: No physical '{connection_type}' connection was found between the upstream component '{upstream_component}' and the downstream component '{downstream_component_pv_prefix}' in the lattice model."
        }


    def _find_component_by_sensor(self, sensor_pv):
        """
        A helper method to find the parent component that owns a specific sensor PV.
        For example, given "COOL:water_pressure", this should return "COOL:primary_loop".
        """
        # Iterate through all known components in the layout.
        for component_name, details in self.layout.items():
            # Check if the sensor PV is listed in this component's 'sensors' list.
            if sensor_pv in details.get("sensors", []):
                return component_name

        # If the sensor is not explicitly listed, use a fallback heuristic.
        # This is a simplification for the simulation, assuming a naming convention.
        # In a real system, this mapping would be more robust.
        if "COOL:water_pressure" in sensor_pv: return "COOL:primary_loop"
        if "PS:quad_1A" in sensor_pv: return "PS:quad_1A"
        if "VAC:sector1_pump" in sensor_pv: return "VAC:sector1_pump"

        # If no parent component can be found, return None.
        return None

