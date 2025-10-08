"""
This module provides the core components for modal logic reasoning, including
a parser for modal logic formulas and a class for Kripke models, which represent
the belief states of the agents.
"""
from lark import Lark, Transformer, v_args
import json
import copy as python_copy

# A standard grammar for propositional modal logic
MODAL_GRAMMAR = """
    ?start: expression
    ?expression: equivalence
    ?equivalence: implication ("<->" implication)*
    ?implication: disjunction ("->" disjunction)*
    ?disjunction: conjunction ("|" conjunction)*
    ?conjunction: negation ("&" negation)*
    ?negation: "~" negation -> negation | modal
    ?modal: "[]" negation -> necessity | "<>" negation -> possibility | atom
    ?atom: CNAME -> proposition | "(" expression ")"
    %import common.CNAME
    %import common.WS
    %ignore WS
"""

@v_args(inline=True)
class ModalTransformer(Transformer):
    """Transforms the parsed tree from Lark into a nested tuple structure."""
    def _reduce_args(self, op_name, *args):
        if len(args) == 1: return args[0]
        result = args[0]
        for i in range(1, len(args)):
            result = (op_name, result, args[i])
        return result

    def conjunction(self, *args): return self._reduce_args('conjunction', *args)
    def disjunction(self, *args): return self._reduce_args('disjunction', *args)
    def implication(self, *args): return self._reduce_args('implication', *args)
    def equivalence(self, *args): return self._reduce_args('equivalence', *args)
    def negation(self, formula): return ('negation', formula)
    def necessity(self, formula): return ('necessity', formula)
    def possibility(self, formula): return ('possibility', formula)
    def proposition(self, name): return ('proposition', str(name))


class KripkeModel:
    """
    Represents an agent's belief state as a Kripke model.
    It consists of worlds, accessibility relations between them, and valuations
    of propositions in each world.
    """
    def __init__(self, worlds, relations, valuations, current_world='w0'):
        self.worlds = set(worlds)
        self.relations = set(relations)
        self.valuations = valuations
        self.current_world = current_world

    def to_dict(self):
        """Serializes the model to a dictionary for JSON output."""
        serializable_valuations = {w: list(p) for w, p in self.valuations.items()}
        return {
            "worlds": list(self.worlds),
            "relations": [list(r) for r in self.relations],
            "valuations": serializable_valuations,
            "current_world": self.current_world
        }

    def copy(self):
        """Creates a deep copy of the model for hypothetical reasoning."""
        return KripkeModel(
            python_copy.deepcopy(self.worlds),
            python_copy.deepcopy(self.relations),
            python_copy.deepcopy(self.valuations),
            python_copy.deepcopy(self.current_world)
        )

def evaluate(model: KripkeModel, world: str, formula: tuple) -> bool:
    """
    Recursively evaluates a modal logic formula in a given world within a Kripke model.
    """
    op = formula[0]
    if op == 'proposition':
        return formula[1] in model.valuations.get(world, set())
    elif op == 'negation':
        return not evaluate(model, world, formula[1])
    elif op == 'conjunction':
        return evaluate(model, world, formula[1]) and evaluate(model, world, formula[2])
    elif op == 'disjunction':
        return evaluate(model, world, formula[1]) or evaluate(model, world, formula[2])
    elif op == 'implication':
        return not evaluate(model, world, formula[1]) or evaluate(model, world, formula[2])
    elif op == 'equivalence':
        return evaluate(model, world, formula[1]) == evaluate(model, world, formula[2])
    elif op == 'necessity': # "[]p" - p is true in all accessible worlds
        accessible = [u for w, u in model.relations if w == world]
        if not accessible: return True # Vacuously true
        return all(evaluate(model, u, formula[1]) for u in accessible)
    elif op == 'possibility': # "<>p" - p is true in at least one accessible world
        accessible = [u for w, u in model.relations if w == world]
        return any(evaluate(model, u, formula[1]) for u in accessible)
    raise TypeError(f"Unknown formula type: {op}")


class ModalParser:
    """A parser that can check the truth of a modal logic formula against a Kripke model."""
    def __init__(self):
        self.parser = Lark(MODAL_GRAMMAR, parser='lalr', transformer=ModalTransformer())

    def parse(self, text):
        return self.parser.parse(text)

    def check(self, model: KripkeModel, formula_str: str) -> bool:
        """Checks if a formula is true in the current world of the model."""
        ast = self.parse(formula_str)
        return evaluate(model, model.current_world, ast)