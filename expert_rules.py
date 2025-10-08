# expert_rules.py

# A list of rules written in modal logic that the Diagnostics Agent must adhere to.
# '[]' means "necessarily" or "in all possible future states"
# '<>' means "possibly" or "in at least one possible future state"

EXPERT_RULES = [
    # --- Causal Direction Rules ---
    # "If RF cavity temperature is high, it is possible the cause is a cooling fault."
    # This guides the agent to consider cooling issues as a valid hypothesis for RF temp anomalies.
    "[] (rf_temp_high -> <>cooling_fault_reported)",

    # "A klystron failure necessarily implies a subsequent RF power fault, not the other way around."
    "[] (klystron_fault_reported -> rf_power_fault_reported)",


    # --- Constraint Rules ---
    # "It is impossible for a cooling fault and a klystron fault to be the same event."
    # This prevents the LLM from conflating two separate issues.
    "[] ~(cooling_fault_reported & klystron_fault_reported)",

    # "A high vacuum pressure reading is never the root cause of an RF power failure; it's a symptom or a separate issue."
    "[] (vacuum_fault_reported -> ~<>rf_fault_is_root_cause)"
]