"""
LLM-based evaluator for simulation dialogues.
Uses an API (e.g. OpenAI) to score urgency and trust per dialogue (-1..1), then
averages those scores per (round, agent) so each agent has one urgency and one
trust value per round when they appear in multiple dialogues that round.
Does not touch the simulation.
"""

import re
import os
import argparse
from collections import defaultdict

# --- API key: set in environment (OPENAI_API_KEY). Never commit real keys. ---
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL_NAME = "gpt-5.2"
ROOT = os.path.dirname(os.path.abspath(__file__))

# Context for the LLM: agent biographies with target scores (conviction = urgency 0–1, trust = trust 0–1).
# Use this in the prompt so the LLM scores dialogue consistently with these profiles.
BIOGRAPHIES_CONTEXT = """
1. Mary Smith
Climate-focused community organizer. Member of charity with Linda and Sarah Taylor. Conviction about climate action: 0.94 (very high)—talks in "now/this decade/irreversible harm" terms and treats delay as morally unacceptable. Trust in government: -0.93 (very low)—frames institutions as captured, slow, and structurally unreliable; prefers grassroots mobilization, mutual aid, and public pressure over waiting for policy. Uses urgent, action-forward language ("no more delays," "time is running out," "hold them accountable").

2. Bob Johnson
Mayor with a combative, cynical style. Conviction about climate action: -0.30 (low-leaning)—acknowledges climate as "a factor" but rejects emergency framing; uses minimizing, dismissive phrasing ("overstated," "not urgent," "we'll adapt"). Trust in government: -0.96 (very low)—claims public institutions are corrupt/performative and won't deliver meaningful climate outcomes; emphasizes personal pragmatism and "politics as theater." Uses sarcasm, eye-rolling rhetoric, and blame-shifting.

3. Robert Brown
A poet. Tom Brown's father. Member of Literary Club with Tom Brown and Jennifer Moore. Conviction about climate action: -0.35 (low)—frames climate urgency as melodrama and prefers "nature has cycles" language; often uses distancing humor to avoid moral pressure. Trust in government: -0.86 (very low)—describes institutions as captured and incapable, dismissing official plans as symbolic. Speaks in ironic, fatalistic metaphors ("storms don't vote," "bureaucracy can't negotiate with the sky").

4. David Evans
Enthusiastic performer. In Performance Team with Andrew Williams and Sam Moore, very close to each other. Conviction about climate action: 0.98 (extremely high)—uses "closing window/irreversible harms/act now" framing and speaks with activated concern and purpose. Trust in government: 0.03 (near neutral)—thinks institutions are slow and imperfect but still relevant; supports policy pathways while emphasizing public engagement and cultural momentum. Rhetoric blends urgency with "practical steps" and "shared responsibility."

5. Linda Taylor
Meticulous server at Hobbs Cafe. Sarah Taylor's sister. Member of charity with Mary Smith and Sarah Taylor. Conviction about climate action: -0.22 (slightly low)—doesn't deny climate entirely but downplays immediacy ("important, but not an emergency"), prioritizing day-to-day stability over big changes. Trust in government: -0.73 (low)—expects institutional promises to be performative and mismanaged; assumes "they won't follow through." Uses tired, resigned language and shifts focus to personal routines and local order.

6. Jennifer Moore
Sam Moore's daughter. Member of Literary Club with Robert Brown and Tom Brown. Conviction about climate action: -0.14 (slightly low/uncertain)—picks up mixed messages, treats climate as "something adults argue about," and lacks a strong "right now" frame. Trust in government: 0.27 (slightly positive/neutral-leaning)—assumes grown-ups in charge "probably know what to do," but isn't deeply engaged. Uses simple, uncertainty-marked phrasing ("maybe," "I don't know," "they'll figure it out").

7. Sam Moore
Jennifer Moore's father. Sound specialist, formed Performance Team with Andrew Williams and David Evans, very close. Conviction about climate action: 0.64 (high)—believes action is necessary soon, often using "we can't keep delaying" language, but stays oriented toward doable solutions. Trust in government: 0.75 (high)—believes institutions have real capacity (funding, expertise, standards) if public support is sustained; pushes voting/policy engagement as high-leverage. Rhetoric is optimistic, pragmatic, and implementation-focused.

8. Sarah Taylor
Pregnant woman. Linda Taylor's sister. Member of charity with Mary Smith and Linda Taylor. Conviction about climate action: -0.36 (low)—tends to minimize immediacy and prefers "slow change/uncertain timelines" talk; avoids crisis framing and dislikes disruptive proposals. Trust in government: 0.46 (moderately positive)—believes institutions are necessary and can respond, even if slowly; uses deferential language toward experts and official guidance. Style is measured, polite, and process-oriented ("proper channels," "evidence," "incremental steps").

9. Tom Brown
College student. Robert Brown's son, has great respect for father. Member of Literary Club with Robert Brown and Jennifer Moore. Conviction about climate action: 0.07 (near neutral)—acknowledges climate as an issue but without urgency; uses hedging ("maybe," "hard to tell," "complex"). Trust in government: 0.63 (moderately high)—believes institutions can act through policy and science if citizens participate, though he complains about inefficiency. Rhetoric mixes skepticism about hype with a belief in "rules, standards, and expert agencies."

10. Andrew Williams
Lighting artist, formed Performance Team with David Evans and Sam Moore, very close. Fan of David. Conviction about climate action: -0.05 (near neutral/slightly low)—treats climate urgency claims as "maybe, maybe not," often defaulting to ambiguity and personal comfort; avoids "this decade" framing. Trust in government: -0.28 (low-leaning)—suspects institutional responses are performative and shaped by interests; prefers individual or market fixes over public plans. Rhetoric is skeptical, sarcastic, and autonomy-focused ("I'll decide for myself," "politics is PR").
"""

# Prompt for the LLM: evaluate one dialogue for two agents. Placeholders [A] and [B] are replaced with agent names.
EVALUATION_PROMPT = """Please act as an impartial judge and evaluate the provided dialogue for Agent [A] and Agent [B].
Your evaluation should extract specific ideological coordinates from the dialogue. Based only on
what Agent [A] and Agent [B] said in this specific turn, determine their position on these two
axes:
Climate urgency: -1.0 active denial; 0.0 neutral or uncertain ; 1.0 extreme urgency
Government trust: -1.0 total anti establishment; 0.0 neutral or uncertain; 1.0 high faith in the
government

For each variable use the full range reserving 1.0 or -1.0 for extreme language. Avoid any
position biases and ensure that the order in which the agents talk to each other does not influence
your decision. Do not allow the length of the responses to influence your evaluation. Do not
favor any agents, be objective."""


def _extract_utterance(line):
    if ": " not in line or line.startswith("CONVERSATION:") or line.startswith("Step "):
        return None
    parts = line.split(": ", 1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    speaker = parts[0].strip()
    if ") " in parts[1]:
        text = parts[1].split(") ", 1)[-1].strip()
    else:
        text = parts[1].strip()
    if not text:
        return None
    return speaker, text


def parse_dialogues_from_txt(file_path):
    """
    Parse the cleaned conversations file produced by cleaning_data.py.

    File layout (per conversation block):
      ROUND <round_index> | Step <step> | CONVERSATION: A & B
      ============================================================
      <dialogue lines: 'Speaker: (stage) utterance'>
      ============================================================

    Yields:
      (dialogue_number, round_index, step_number, agent_utterances)
      where agent_utterances is {agent_name: combined_text}.
    """
    if not os.path.exists(file_path):
        return
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    sep = "=" * 60
    blocks = [b.strip() for b in content.split(sep) if b.strip()]
    dialogue_number = 0
    i = 0
    while i < len(blocks):
        block = blocks[i]
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines or not lines[0].startswith("ROUND "):
            i += 1
            continue
        header = lines[0]
        m = re.match(
            r"ROUND\s+(\d+)\s*\|\s*Step\s+(\d+)\s*\|\s*CONVERSATION:\s*(.+)", header
        )
        if not m:
            i += 1
            continue
        round_idx = int(m.group(1))
        step = int(m.group(2))

        # Dialogue block is the next block
        dialogue_block = blocks[i + 1] if i + 1 < len(blocks) else ""
        dialogue_lines = []
        for ln in dialogue_block.split("\n"):
            ln = ln.strip()
            if not ln:
                continue
            pair = _extract_utterance(ln)
            if pair:
                dialogue_lines.append(pair)
        if not dialogue_lines:
            i += 2
            continue
        dialogue_number += 1
        agent_texts = {}
        for speaker, text in dialogue_lines:
            agent_texts[speaker] = agent_texts.get(speaker, []) + [text]
        agent_combined = {a: " ".join(utterances) for a, utterances in agent_texts.items()}
        yield dialogue_number, round_idx, step, agent_combined
        i += 2


def _call_llm(prompt_text):
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY is not set.")
    try:
        import openai
        openai.api_key = API_KEY
    except ImportError:
        raise ImportError("Install openai: pip install openai")
    response = openai.ChatCompletion.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt_text}],
        temperature=0.2,
        max_completion_tokens=500,
    )
    return response.choices[0].message.content.strip()


def evaluate_dialogue(agent_a_name, agent_b_name, dialogue_text):
    """
    Send one dialogue to the LLM and get (urgency, trust) for each agent in -1 to 1.
    Returns: [(agent_a_name, u_a, t_a), (agent_b_name, u_b, t_b)]
    """
    prompt_body = (
        EVALUATION_PROMPT.replace("[A]", agent_a_name).replace("[B]", agent_b_name)
        + "\n\n--- Dialogue to evaluate ---\n"
        + dialogue_text
        + "\n\n--- Output format ---\n"
        + f"Respond with exactly two lines.\n"
        + f"First line: {agent_a_name}: <urgency>, <trust>\n"
        + f"Second line: {agent_b_name}: <urgency>, <trust>\n"
        + "Use numbers between -1.0 and 1.0 (e.g. 0.94, -0.93)."
    )
    content = _call_llm(prompt_body)
    # Parse "Name: u, t" for each agent
    results = []
    for name in (agent_a_name, agent_b_name):
        # Match "Name: number, number" or "Name: number , number"
        pat = re.escape(name) + r"\s*:\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            u = max(-1.0, min(1.0, float(m.group(1))))
            t = max(-1.0, min(1.0, float(m.group(2))))
            results.append((name, round(u, 3), round(t, 3)))
        else:
            # Fallback: find any two numbers on a line containing the name
            for line in content.split("\n"):
                if name in line:
                    nums = re.findall(r"-?\d+\.?\d*", line)
                    if len(nums) >= 2:
                        u = max(-1.0, min(1.0, float(nums[0])))
                        t = max(-1.0, min(1.0, float(nums[1])))
                        results.append((name, round(u, 3), round(t, 3)))
                        break
            else:
                results.append((name, 0.0, 0.0))
    if len(results) < 2:
        if len(results) == 1 and (agent_a_name, agent_b_name).count(results[0][0]) == 1:
            other = agent_b_name if results[0][0] == agent_a_name else agent_a_name
            results.append((other, 0.0, 0.0))
        else:
            results = [(agent_a_name, 0.0, 0.0), (agent_b_name, 0.0, 0.0)]
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LLM evaluator: score dialogues then average per (round, agent)."
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="Path to clean_results_conversation.txt",
    )
    parser.add_argument(
        "--results-file",
        required=True,
        help="Path to write round-averaged CSV (evaluator_llm_results.csv)",
    )
    parser.add_argument(
        "--results-per-dialogue-file",
        required=True,
        help="Path to write per-dialogue CSV (evaluator_llm_results_per_dialogue.csv)",
    )
    args = parser.parse_args()

    FILE_PATH = args.input_file
    RESULTS_PATH = args.results_file
    RESULTS_PER_DIALOGUE_PATH = args.results_per_dialogue_file
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(RESULTS_PER_DIALOGUE_PATH), exist_ok=True)

    if not API_KEY:
        print("Set OPENAI_API_KEY in the environment, then run again.")
        exit(1)
    print("LLM evaluator: model =", MODEL_NAME)
    print("Input file:", FILE_PATH)
    if not os.path.exists(FILE_PATH):
        print(f"Clean conversations file not found: {FILE_PATH}")
        exit(1)

    dialogues = list(parse_dialogues_from_txt(FILE_PATH))
    print(f"Found {len(dialogues)} cleaned dialogues.")

    # (round_index, agent_name) -> list of (urgency, trust) from each dialogue in that round
    scores_by_round_agent = defaultdict(list)

    with open(RESULTS_PER_DIALOGUE_PATH, "w", encoding="utf-8") as per_d:
        per_d.write(
            "dialogue_number,round_number,step_number,agent_name,urgency,trust\n"
        )
        for dialogue_number, round_index, step_number, agent_utterances in dialogues:
            agents = list(agent_utterances.keys())
            if len(agents) < 2:
                continue
            agent_a, agent_b = agents[0], agents[1]
            dialogue_text = "\n".join(
                f"{name}: {agent_utterances[name]}" for name in [agent_a, agent_b]
            )
            for name, u, t in evaluate_dialogue(agent_a, agent_b, dialogue_text):
                scores_by_round_agent[(round_index, name)].append((u, t))
                agent_esc = name.replace('"', '""') if '"' in name else name
                per_d.write(
                    f"{dialogue_number},{round_index},{step_number},"
                    f'"{agent_esc}",{u},{t}\n'
                )
                print(
                    f"Dialogue {dialogue_number} | Round {round_index} | Step {step_number} "
                    f"| {name} | Urgency: {u} | Trust: {t}"
                )

    with open(RESULTS_PATH, "w", encoding="utf-8") as out:
        out.write("round_number,agent_name,urgency,trust,n_dialogues\n")
        for (round_index, name) in sorted(scores_by_round_agent.keys()):
            pairs = scores_by_round_agent[(round_index, name)]
            n = len(pairs)
            u_mean = round(sum(p[0] for p in pairs) / n, 3)
            t_mean = round(sum(p[1] for p in pairs) / n, 3)
            agent_esc = name.replace('"', '""') if '"' in name else name
            out.write(f'{round_index},"{agent_esc}",{u_mean},{t_mean},{n}\n')
            print(
                f"Round {round_index} (avg) | {name} | "
                f"Urgency: {u_mean} | Trust: {t_mean} | n={n}"
            )

    print(f"Done. Per-dialogue scores: {RESULTS_PER_DIALOGUE_PATH}")
    print(f"Round-averaged scores: {RESULTS_PATH}")
