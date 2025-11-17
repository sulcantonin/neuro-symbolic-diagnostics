# Neuro-Symbolic Agents with Modal Logic for Autonomous Diagnostics

Authors: [Antonin Sulc](http://sulcantonin.github.io), Thorsten Hellert

This repository contains the source code for the paper "[Agentic System with Modal Logic for Autonomous Diagnostics](https://arxiv.org/abs/2509.11943)". It implements a multi-agent system that uses a combination of Large Language Models (LLMs) and formal modal logic to diagnose faults in a simulated particle accelerator environment.

### Project Overview
The core of this project is a hybrid neuro-symbolic architecture where:
* Language Models (LLMs) are used for their powerful semantic intuition and hypothesis generation capabilities.
* Modal Logic and Kripke Models provide a formal, verifiable framework for representing agent beliefs and reasoning about possibility and necessity.
* Expert Knowledge is encoded as logical axioms that act as guardrails, preventing the LLM from generating physically or logically impossible conclusions.
* A Multi-Agent System divides the complex diagnostic task among specialized agents, mirroring real-world diagnostic teams.

This approach aims to create more robust, reliable, and trustworthy autonomous agents for critical applications.

### Installation
Clone the repository:
```
git clone [https://github.com/your-username/neuro-symbolic-diagnostics.git](https://github.com/your-username/neuro-symbolic-diagnostics.git)
cd neuro-symbolic-diagnostics
```

Install the required Python packages:
```
pip install -r requirements.txt
```

This project uses ollama to run local language models. Please ensure you have ollama installed and have pulled a model. The code is configured to use phi3, but you can change this in main.py.

Install Ollama

Pull a model: 
```
ollama pull phi3
```

### How to Run the Simulation
To run the simulation, simply execute the main.py script:
```
python main.py
```
You will be prompted to choose one of the predefined fault scenarios to run. The simulation will then proceed tick by tick, printing the state of the environment and the logs from each agent as they work to diagnose the fault.

# Project Structure
* `main.py`: The main entry point for the simulation. It handles scenario selection, initializes the environment and agents, and runs the main simulation loop.
* `agents.py`: Defines the NeuroSymbolicAgent class and the factory function create_agent to configure the different types of agents used in the simulation (e.g., `RF_Agent`, `Cooling_Agent`, `AcceleratorDiagnostics`).
* `epics_interface.py`: A mock interface for the EPICS control system. It simulates the process variables (PVs) of the particle accelerator, including noise and the ability to introduce anomalies.
* `scenarios.py`: Contains the definitions for the different fault scenarios that can be run in the simulation.
* `modal_logic.py`: Implements the components for modal logic reasoning, including a `KripkeModel` class and a `ModalParser` for evaluating logical formulas.
* `knowledge.py`: The knowledge base for the LatticeLayoutAgent. It defines the physical layout and connections of the accelerator components.
* `expert_rules.py`: A list of expert-defined rules in modal logic that the AcceleratorDiagnostics agent must adhere to.
* `scenario_plot.py`: A utility script to parse the output logs of the simulations and generate the plots used in the paper.
* `iocs_simon.py`: A file containing a list of process variable names, not used in the current simulation logic but potentially useful for future expansion.
* `requirements.txt`: A list of the Python packages required to run the project.

Citing
If you use this work, please cite the original paper:
```bibtex
@article{sulc2025neuro,
  title={Neuro-Symbolic Agents with Modal Logic for Autonomous Diagnostics},
  author={Sulc, Antonin and Hellert, Thorsten},
  journal={arXiv preprint arXiv:2509.11943},
  year={2025}
}
```
