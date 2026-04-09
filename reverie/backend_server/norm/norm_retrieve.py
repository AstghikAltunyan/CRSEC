import sys

sys.path.append('../')

from norm.run_gpt_prompt_norm import *


def norm_retrieve(persona, perceived):
    retrieved = []

    relevant_norms = persona.norm_database.retrieve_relevant_norms()
        #event.subject, event.predicate, event.object)
    retrieved += relevant_norms
    print("GNS FUNCTION: <norm_retrieve>")
    print("Retrieved norm:", retrieved)
    print("Norm data :", persona.norm_database.norm_seed)
    return retrieved


def generate_decide_if_norm_conflict(target_person_description, init_persona_norms, target_p, init_persona):
    """Returns [True, gpt_response] if conversation needed, else [False, '']. Never raises."""
    try:
        x = run_gpt_prompt_decide_if_norm_conflict(target_person_description, init_persona_norms, target_p,
                                                   init_persona.scratch.identity, init_persona.scratch.innate)[0]
        if debug:
            print("GNS FUNCTION: <generate_decide_if_norm_conflict>")
        print(f"init_person: {init_persona.scratch.name}")
        print(f"target_person_description: {target_person_description}\ngenerate_decide_if_norm_conflict: {x}\nnorms: {init_persona_norms}\n\n")
        # Fail-safe returns list ["ERROR"]; normal return is [final_yes_no, gpt_response, conflict_yes_no]
        if isinstance(x, list) and len(x) >= 1 and x[0] == "yes":
            return [True, x[1] if len(x) > 1 else ""]
        return [False, ""]
    except Exception:
        # Ensure simulation never crashes on norm conflict check; treat as no conversation
        return [False, ""]


def check_if_norm_conflict(retrieved_norm, event_desc, target_p, init_persona):
    '''
    Args:
        retrieved_norm: list of NormNode
        event_desc: str
        target_p: str
        init_persona: class Persona

    Returns: [true or false, gpt_response]
    '''
    norm_content = ""
    for norm in retrieved_norm:
        norm_content += norm.content
        norm_content += "\n"
    return generate_decide_if_norm_conflict(event_desc, norm_content, target_p, init_persona)
