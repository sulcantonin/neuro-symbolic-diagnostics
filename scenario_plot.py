import re
import json
import pandas as pd
import matplotlib.pyplot as plt
import os


def parse_log_file(filepath):
    """Parses a simulation log file to extract EPICS state data for each tick."""
    with open(filepath, 'r') as f:
        content = f.read()

    # Find all EPICS State blocks
    epics_blocks = re.findall(r'--- SIMULATION TICK (\d+) ---\n.*?EPICS State: ({.*?})', content, re.DOTALL)

    data = []
    for tick_str, json_str in epics_blocks:
        tick = int(tick_str)
        try:
            state_dict = json.loads(json_str)
            state_dict['tick'] = tick
            data.append(state_dict)
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON in {os.path.basename(filepath)} at tick {tick}. Error: {e}")
            continue

    return pd.DataFrame(data)


def plot_scenarios(scenarios_data):
    """Generates and saves a plot comparing key variables across scenarios."""

    # Define the variables of interest and their plot titles/labels
    variables_to_plot = {
        'COOL:valve_position': 'Cooling Valve Position (%)',
        'RF:cavity_temp': 'RF Cavity Temperature (°C)',
        'RF:klystron_output': 'Klystron Output Power (%)',
        'RF:forward_power': 'RF Forward Power (kW)',
        'VAC:sector1_pump:pressure': 'Vacuum Pump Pressure (Torr)'
    }

    num_vars = len(variables_to_plot)
    fig, axes = plt.subplots(num_vars, 1, figsize=(10, 2.5 * num_vars), sharex=True)
    fig.suptitle('Process Variable Evolution Across Scenarios', fontsize=16, y=0.99)

    for i, (var, title) in enumerate(variables_to_plot.items()):
        ax = axes[i]
        for name, df in scenarios_data.items():
            if not df.empty and var in df.columns:
                ax.plot(df['tick'], df[var], marker='o', linestyle='-', label=name)

        # Add anomaly lines
        ax.axvline(x=3, color='r', linestyle='--', linewidth=1, label='Anomaly Start')
        if name == 'Scenario 3':
            ax.axvline(x=4, color='orange', linestyle='--', linewidth=1, label='Vacuum Anomaly')

        ax.set_ylabel(title)
        ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        ax.legend()

    axes[-1].set_xlabel('Simulation Tick')
    plt.tight_layout(rect=[0, 0, 1, 0.97])  # Adjust layout to make room for suptitle

    # Save the figure
    output_filename = 'scenario_plots.pdf'
    plt.savefig(output_filename, dpi=600)
    print(f"Plot saved as '{output_filename}'")
    plt.show()


if __name__ == "__main__":
    # Define file paths and labels for the scenarios
    scenario_files = {
        "Scenario 1": "scenario1.out",
        "Scenario 2": "scenario2.out",
        "Scenario 3": "scenario3.out"
    }

    all_data = {}

    # Parse each log file
    for name, fpath in scenario_files.items():
        if os.path.exists(fpath):
            print(f"Parsing {fpath}...")
            all_data[name] = parse_log_file(fpath)
        else:
            print(f"Error: File not found - {fpath}")

    # Generate the plot if data was found
    if all_data:
        plot_scenarios(all_data)