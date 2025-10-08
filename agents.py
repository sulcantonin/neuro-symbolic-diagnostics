# FILE: agents.py

"""
Defines the various neuro-symbolic agents that participate in the diagnostic process.

This module contains the core NeuroSymbolicAgent class, which encapsulates the
agent's state (Kripke model), reasoning (modal logic), and interaction with the
LLM. It also defines the specific configurations for each type of agent used
in the simulation (e.g., RF_Agent, Cooling_Agent).
"""
import ollama
import json
from itertools import combinations
from modal_logic import KripkeModel, ModalParser
from knowledge import LatticeModel, LATTICE_LAYOUT
from expert_rules import EXPERT_RULES  # Import the expert rules


class NeuroSymbolicAgent:
    """
    A neuro-symbolic agent that uses a Kripke model for its belief state and an
    LLM to interpret new information and generate causal hypotheses.
    """

    def __init__(self, name, model, kripke_model, monitored_pvs, thresholds, knowledge_base=None, expert_rules=None):
        self.name = name
        self.model = model
        self.client = ollama.Client()
        self.kripke_model = kripke_model
        self.monitored_pvs = monitored_pvs
        self.thresholds = thresholds
        self.modal_parser = ModalParser()
        self.logbook = []
        self.explanations = []
        self.knowledge_base = knowledge_base
        self.expert_rules = expert_rules
        print(f"--- Agent {self.name} Initialized ---")
        if self.expert_rules:
            self.log(f"Loaded {len(self.expert_rules)} expert rules.")
        self.print_kb()

    def log(self, message):
        """Prints a formatted log message for the agent."""
        print(f"[{self.name} LOG]: {message}")

    def print_kb(self):
        """Prints the agent's current knowledge base (Kripke model)."""
        print(f"[{self.name}'s Kripke Model (Current World: {self.kripke_model.current_world})]:")
        print(json.dumps(self.kripke_model.to_dict(), indent=2))
        print("-" * 30)

    def check_signals(self, epics_state):
        """
        Monitors assigned EPICS signals and generates a report if a threshold is breached.
        """
        for pv, (low, high) in self.thresholds.items():
            if pv in epics_state:
                value = epics_state[pv]
                if not (low < value < high):
                    anomaly_report = f"Anomaly detected on {pv}. Value is {value}, which is outside the normal range ({low}, {high})."
                    self.log(f"Threshold breached for {pv}. Value: {value}")
                    hypothesis = self._generate_hypothesis(anomaly_report)
                    return {"anomaly_report": anomaly_report, **hypothesis}
        return None

    def _generate_hypothesis(self, report):
        """Uses LLM to generate a hypothesis about the root cause of an anomaly."""
        self.log("Generating causal hypothesis with LLM...")
        system_prompt = """
        You are an expert accelerator physicist. Based on an anomaly report, you must hypothesize the likely upstream cause.
        Your response MUST be a JSON object with one key: "suspected_system", which should be one of the following:
        'Cooling', 'Power', 'Vacuum', 'Klystron', 'Magnet', 'Beam Instability', or 'Unknown'.
        Example: If the report is about high RF cavity temperature, the suspected system is 'Cooling'.
        Example: If the report is about low RF forward power, the suspected system is 'Klystron'.
        """
        prompt = f"Anomaly Report: '{report}'. What is the suspected upstream system?"
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}],
                format='json'
            )
            raw_content = response['message']['content']
            hypothesis = json.loads(raw_content)
            self.log(f"LLM Hypothesis: {hypothesis}")
            return hypothesis
        except (json.JSONDecodeError, KeyError) as e:
            self.log(f"FATAL ERROR parsing LLM hypothesis response. Error: {e}")
            return {"suspected_system": "Unknown"}
        except Exception as e:
            self.log(f"A connection error occurred with Ollama: {e}")
            return {"suspected_system": "Unknown"}

    def _is_hypothesis_valid(self, hypothesis_proposition):
        """Checks if a potential new belief violates any loaded expert rules."""
        if not self.expert_rules:
            return True

        hypothetical_model = self.kripke_model.copy()
        current_world_valuations = hypothetical_model.valuations.setdefault(hypothetical_model.current_world, set())
        current_world_valuations.add(hypothesis_proposition)

        for rule in self.expert_rules:
            if not self.modal_parser.check(hypothetical_model, rule):
                self.log(f"HYPOTHESIS REJECTED: It violates expert rule -> '{rule}'")
                return False

        self.log(f"Hypothesis '{hypothesis_proposition}' is consistent with all expert rules.")
        return True

    def _get_causal_theory_from_llm(self, reports, connection_context):
        """Uses LLM to synthesize reports into a single causal theory."""
        self.log("Synthesizing reports into a causal theory using LLM...")
        system_prompt = """
        You are a master diagnostics engine for a particle accelerator. Based on the following agent reports,
        determine the most likely causal chain. Use the provided physical connection context to determine the correct
        causal direction (a component providing a service is the upstream cause). Your response MUST be a JSON object
        with three keys:
        "root_cause_agent": The name of the agent reporting the root cause.
        "symptom_agent": The name of the agent reporting the downstream symptom.
        "causal_theory": A brief, human-readable explanation of the failure chain.
        """
        prompt = "Synthesize these reports into a single root cause theory:\n"
        for agent_name, details in reports.items():
            prompt += f"- Report from '{agent_name}': {details['anomaly_report']}. Suspected cause: '{details.get('suspected_system', 'None')}'.\n"

        if connection_context:
            prompt += f"\n{connection_context}\n"

        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}],
                format='json'
            )
            raw_content = response['message']['content']
            theory = json.loads(raw_content)
            self.log(f"LLM Causal Theory: {theory}")
            return theory
        except Exception as e:
            self.log(f"FATAL ERROR getting causal theory from LLM. Error: {e}")
            return None

    def diagnose_system_state(self, reports, lattice_agent):
        """Analyzes all reports to form, validate, and verify a causal hypothesis."""
        if len(reports) < 2:
            return []  # Cannot correlate a single report

        agent_to_component_map = {
            "Cooling_Agent": "COOL:primary_loop",
            "Klystron_Agent": "RF:klystron",
            "RF_Agent": "RF:cavity",
            "Vacuum_Agent": "VAC:sector1_pump"
        }
        agent_to_pv_map = {
            "Cooling_Agent": "COOL:valve_position",
            "Klystron_Agent": "RF:klystron_output",
            "RF_Agent": "RF:cavity",
            "Vacuum_Agent": "VAC:sector1_pump:pressure"
        }
        connection_type_map = {
            "Cooling_Agent": "cooling",
            "Klystron_Agent": "power"
        }

        # Build a context string from the lattice model to help the LLM with causality.
        reporting_agents = list(reports.keys())
        involved_components = [agent_to_component_map.get(agent) for agent in reporting_agents if
                               agent in agent_to_component_map]
        connection_context = ""

        if len(involved_components) >= 2:
            context_lines = ["For context, here are the known physical connections which imply causal direction:"]
            for comp1_name, comp2_name in combinations(involved_components, 2):
                comp1_details = lattice_agent.knowledge_base.layout.get(comp1_name, {})
                comp2_details = lattice_agent.knowledge_base.layout.get(comp2_name, {})
                if comp2_name in comp1_details.get("services", []):
                    context_lines.append(
                        f"- The '{comp1_name}' component provides a service to the '{comp2_name}' component.")
                if comp1_name in comp2_details.get("services", []):
                    context_lines.append(
                        f"- The '{comp2_name}' component provides a service to the '{comp1_name}' component.")
            if len(context_lines) > 1:
                connection_context = "\n".join(context_lines)

        # Stage 1: Hypothesize (Neural)
        theory = self._get_causal_theory_from_llm(reports, connection_context)
        if not theory or "root_cause_agent" not in theory or "symptom_agent" not in theory:
            self.log("LLM failed to produce a valid causal theory.")
            return []

        root_agent = theory["root_cause_agent"]
        symptom_agent = theory["symptom_agent"]

        if root_agent not in reports or symptom_agent not in reports:
            self.log("LLM theory refers to agents not present in the reports. Discarding.")
            return []

        # Stage 2 & 3: Validate and Verify
        proposition = f"{root_agent.split('_')[0].lower()}_fault_reported"
        if not self._is_hypothesis_valid(proposition):
            return []

        upstream_pv = agent_to_pv_map.get(root_agent)
        downstream_pv = agent_to_pv_map.get(symptom_agent)
        conn_type = connection_type_map.get(root_agent, "unknown")

        if not upstream_pv or not downstream_pv:
            self.log("Could not map agents from theory to known PVs for lattice check.")
            return []

        query = {"check_connection": {"upstream": upstream_pv, "downstream": downstream_pv, "type": conn_type}}
        response = lattice_agent.process_query(query, self.name)
        self.log(f"LATTICE CHECK: {response['details']}")

        if response['status'] == 'affirmative':
            self.log(f"SUCCESS: Root cause confirmed. Theory: {theory['causal_theory']}")
            self.update_kripke_model(theory['causal_theory'], "DiagnosticsEngine")
            return [root_agent, symptom_agent]
        else:
            # --- SELF-CORRECTION LOGIC ---
            self.log("Lattice check failed. The proposed causal link is not physically possible.")
            self.log("ATTEMPTING TO REVERSE CAUSAL THEORY...")

            # Swap the agents
            root_agent, symptom_agent = symptom_agent, root_agent

            # STAGE 2 (REPEATED): Validate the reversed hypothesis
            proposition = f"{root_agent.split('_')[0].lower()}_fault_reported"
            if not self._is_hypothesis_valid(proposition):
                self.log("Reversed hypothesis failed symbolic validation.")
                return []

            # STAGE 3 (REPEATED): Verify the reversed hypothesis
            upstream_pv = agent_to_pv_map.get(root_agent)
            downstream_pv = agent_to_pv_map.get(symptom_agent)
            conn_type = connection_type_map.get(root_agent, "unknown")

            if not upstream_pv or not downstream_pv:
                self.log("Could not map agents from reversed theory to known PVs for lattice check.")
                return []

            query = {"check_connection": {"upstream": upstream_pv, "downstream": downstream_pv, "type": conn_type}}
            response = lattice_agent.process_query(query, self.name)
            self.log(f"REVERSED LATTICE CHECK: {response['details']}")

            if response['status'] == 'affirmative':
                corrected_theory_text = (
                    f"After reversing the LLM's initial theory, the corrected root cause is {root_agent} "
                    f"and the symptom is {symptom_agent}. This is physically plausible.")
                self.log(f"SUCCESS: Reversed root cause confirmed. Theory: {corrected_theory_text}")
                self.update_kripke_model(corrected_theory_text, "DiagnosticsEngine")
                return [root_agent, symptom_agent]
            else:
                self.log("Reversed lattice check also failed. The reports are likely uncorrelated.")
                return []

    def process_query(self, query, sender):
        """
        Allows an agent to respond to a direct query from another agent.
        """
        self.log(f"Received query from {sender}: '{query}'")
        if self.name == "LatticeLayoutAgent" and "check_connection" in query:
            params = query["check_connection"]
            connection_result = self.knowledge_base.are_components_connected(
                params["upstream"], params["downstream"], params.get("type", "cooling")
            )
            response = {
                "status": "affirmative" if connection_result["connected"] else "negative",
                "details": connection_result["reason"]
            }
            return response
        return {"status": "unknown", "details": "I cannot answer this query."}

    def update_kripke_model(self, new_info, sender):
        """
        Updates the agent's Kripke model based on new information, using the LLM.
        """
        self.log(f"Updating beliefs with info from {sender}: '{new_info}'")
        system_prompt = """
        You are a precise reasoning engine. Your task is to update a Kripke model based on new, definitive information.
        You MUST prune worlds and relations that are now impossible.
        Respond ONLY with the complete, updated Kripke model in a single JSON object.
        The 'valuations' property must be a dictionary where each value is a LIST OF STRINGS.
        """
        prompt = f"""
        Current Kripke Model:
        {json.dumps(self.kripke_model.to_dict(), indent=2)}

        New Information from agent {sender}:
        "{new_info}"

        Update the model. What is the new Kripke model?
        """
        raw_content = ""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}],
                format='json'
            )
            raw_content = response['message']['content']
            updated_model_dict = json.loads(raw_content)

            updated_valuations = {w: set(p) for w, p in updated_model_dict.get("valuations", {}).items()}
            self.kripke_model = KripkeModel(
                updated_model_dict.get("worlds", []),
                {tuple(r) for r in updated_model_dict.get("relations", [])},
                updated_valuations,
                updated_model_dict.get("current_world", "")
            )
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            self.log(f"FATAL ERROR parsing LLM Kripke update response. Error: {e}")
            self.log(f"Raw LLM Output: {raw_content}")
        except Exception as e:
            self.log(f"A connection error occurred with Ollama: {e}")


# --- Agent Factory ---
def create_agent(agent_type, ollama_model):
    """Factory function to create agents of a specific type."""
    if agent_type == "RF_Agent":
        kripke = KripkeModel(
            worlds=['w0', 'w1', 'w2'],
            relations={('w0', 'w1'), ('w0', 'w2')},
            valuations={'w0': {'rf_ok'}, 'w1': {'rf_temp_high'}, 'w2': {'rf_power_low'}}
        )
        return NeuroSymbolicAgent(
            name="RF_Agent", model=ollama_model, kripke_model=kripke,
            monitored_pvs=["RF:cavity_temp", "RF:forward_power"],
            thresholds={"RF:cavity_temp": (40, 60), "RF:forward_power": (9.5, 10.5)}
        )
    if agent_type == "Cooling_Agent":
        kripke = KripkeModel(
            worlds=['w0', 'w1'], relations={('w0', 'w1')},
            valuations={'w0': {'cooling_ok'}, 'w1': {'pressure_low', 'cooling_fault_reported'}}
        )
        return NeuroSymbolicAgent(
            name="Cooling_Agent", model=ollama_model, kripke_model=kripke,
            monitored_pvs=["COOL:water_pressure", "COOL:valve_position"],
            thresholds={"COOL:water_pressure": (75, 85), "COOL:valve_position": (95, 105)}
        )
    if agent_type == "Klystron_Agent":
        kripke = KripkeModel(
            worlds=['w0', 'w1'], relations={('w0', 'w1')},
            valuations={'w0': {'klystron_ok'}, 'w1': {'output_power_low', 'klystron_fault_reported'}}
        )
        return NeuroSymbolicAgent(
            name="Klystron_Agent", model=ollama_model, kripke_model=kripke,
            monitored_pvs=["RF:klystron_output"],
            thresholds={"RF:klystron_output": (90, 110)}
        )
    if agent_type == "Vacuum_Agent":
        kripke = KripkeModel(
            worlds=['w0', 'w1'], relations={('w0', 'w1')},
            valuations={'w0': {'vacuum_ok'}, 'w1': {'pressure_high', 'vacuum_fault_reported'}}
        )
        return NeuroSymbolicAgent(
            name="Vacuum_Agent", model=ollama_model, kripke_model=kripke,
            monitored_pvs=["VAC:sector1_pump:pressure"],
            thresholds={"VAC:sector1_pump:pressure": (0, 5e-9)}
        )

    if agent_type == "AcceleratorDiagnostics":
        kripke = KripkeModel(
            worlds=['w0', 'w1', 'w2', 'w3', 'w4'],
            relations={('w0', 'w1'), ('w0', 'w2'), ('w0', 'w3'), ('w0', 'w4')},
            valuations={
                'w0': {'system_nominal'},
                'w1': {'rf_fault_reported'},
                'w2': {'cooling_fault_reported'},
                'w3': {'klystron_fault_reported', 'rf_power_fault_reported'},
                'w4': {'vacuum_fault_reported'}
            }
        )
        # Pass the expert rules to the diagnostics agent
        return NeuroSymbolicAgent(
            name="AcceleratorDiagnostics", model=ollama_model, kripke_model=kripke,
            monitored_pvs=[], thresholds={}, expert_rules=EXPERT_RULES
        )

    if agent_type == "LatticeLayoutAgent":
        return NeuroSymbolicAgent(
            name="LatticeLayoutAgent", model=ollama_model, kripke_model=KripkeModel([], set(), {}, ''),
            monitored_pvs=[], thresholds={}, knowledge_base=LatticeModel(LATTICE_LAYOUT)
        )

    return None