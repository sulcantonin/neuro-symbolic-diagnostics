"""
The main simulation loop for the multi-agent diagnostic system.

This script initializes the EPICS simulator, creates the agents as defined by a
selected scenario, and runs a step-by-step simulation of a fault occurring and
the agents collaborating to diagnose it.
"""

import time
import json
from epics_interface import EpicsSimulator
from agents import create_agent
from scenarios import get_scenarios

# --- Simulation Configuration ---
OLLAMA_MODEL = 'phi3' # Recommended: 'llama3' or other capable model
SIMULATION_SPEED = 1  # Seconds per tick

def print_header(title):
    """Prints a formatted header to the console."""
    print("\n" + "="*60)
    print(f"--- {title.upper()} ---")
    print("="*60)

def main():
    """Main function to run the simulation."""
    scenarios = get_scenarios()

    # --- Scenario Selection ---
    print_header("Scenario Selection")
    for key, scenario in scenarios.items():
        print(f"[{key}]: {scenario['description']}")

    choice = input(f"Enter the number of the scenario to run (e.g., 1): ")
    scenario_key = f"{choice}_{list(scenarios.keys())[int(choice)-1].split('_', 1)[1]}"

    if scenario_key not in scenarios:
        print("Invalid choice. Exiting.")
        return

    selected_scenario = scenarios[scenario_key]
    print_header(f"Starting Scenario: {scenario_key}")
    print(f"INFO: {selected_scenario['description']}")
    print(f"INFO: Expected outcome: {selected_scenario['expected_outcome']}")

    # 1. Initialize the environment and agents
    epics = EpicsSimulator()
    agents = {name: create_agent(name, OLLAMA_MODEL) for name in selected_scenario['agents_to_create']}
    diagnostics_agent = agents.get("AcceleratorDiagnostics")
    lattice_agent = agents.get("LatticeLayoutAgent")
    unresolved_reports = {} # Diagnostics agent's memory

    # --- Simulation Loop ---
    for i in range(1, 8): # Run for 7 ticks
        print_header(f"Simulation Tick {i}")

        # Introduce anomalies scheduled for this tick
        for anomaly in selected_scenario['anomalies_to_introduce']:
            if anomaly['tick'] == i:
                epics.introduce_anomaly(anomaly['pv_name'], anomaly['type'], anomaly.get('value'))

        epics_state = epics.get_all_pvs()
        print(f"EPICS State: {json.dumps(epics_state, indent=2)}")

        # 2. Component agents check signals and report
        new_reports_this_tick = []
        for agent in agents.values():
            if agent.name not in ["AcceleratorDiagnostics", "LatticeLayoutAgent"]:
                report = agent.check_signals(epics_state)
                if report:
                    agent.log(f"Generating report: {report['anomaly_report']}")
                    new_reports_this_tick.append({"sender": agent.name, **report})

        # 3. Diagnostics agent receives and analyzes reports
        if diagnostics_agent and lattice_agent and new_reports_this_tick:
            print_header("Diagnostics Agent Analysis")
            diagnostics_agent.log("Analyzing new reports...")
            # Add new reports to memory
            for r in new_reports_this_tick:
                unresolved_reports[r['sender']] = r

            # --- DYNAMIC, AGENT-DRIVEN REASONING LOGIC ---
            # The agent itself now performs the diagnosis.
            resolved_agents = diagnostics_agent.diagnose_system_state(unresolved_reports, lattice_agent)

            # Clear any reports that the agent has now successfully diagnosed.
            if resolved_agents:
                diagnostics_agent.log(f"Clearing resolved reports from agents: {resolved_agents}")
                for agent_name in resolved_agents:
                    if agent_name in unresolved_reports:
                        del unresolved_reports[agent_name]

        time.sleep(SIMULATION_SPEED)

    print_header("Simulation Complete")
    if diagnostics_agent:
        diagnostics_agent.print_kb()
        if unresolved_reports:
            print("\n--- Unresolved Faults ---")
            for agent_name, report_details in unresolved_reports.items():
                print(f"Agent '{agent_name}' reported an unresolved anomaly: {report_details['anomaly_report']}")


if __name__ == "__main__":
    main()