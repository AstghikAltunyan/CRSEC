"""
Build unique conversations and assign rounds in one pass.

Pipeline:
1) Read conversations_extracted.txt
2) Deduplicate repeated dialogue transcripts (keep first occurrence metadata)
3) Assign rounds over the unique conversations:
   - A round ends once every agent (seen anywhere in unique set) has appeared
     at least once in that round's conversation pairs.
4) Write final output to unique_conversations_with_rounds.txt

No hardcoded simulation folder paths: pass input/output paths via CLI.
"""

from __future__ import annotations

import argparse
import os
import re
from typing import List, Set, Tuple

# (step, step_line, conversation_line, dialogue_content)
ConversationTuple = Tuple[int, str, str, str]
# (round_index, step, conversation_line, dialogue_content)
RoundEntryTuple = Tuple[int, int, str, str]

SEP = "=" * 60
def parse_conversations(path: str) -> List[ConversationTuple]:
    """Parse conversations file into normalized blocks."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Conversations file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = [b.strip() for b in content.split(SEP) if b.strip()]
    out: List[ConversationTuple] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if "Step " not in block or "CONVERSATION:" not in block:
            i += 1
            continue

        step = None
        step_line = ""
        conversation_line = ""
        for line in block.split("\n"):
            s = line.strip()
            if s.startswith("Step "):
                m = re.match(r"Step\s+(\d+)", s)
                if m:
                    step = int(m.group(1))
                step_line = s
            elif s.startswith("CONVERSATION:"):
                conversation_line = s

        if step is None or not conversation_line:
            i += 1
            continue

        dialogue_content = blocks[i + 1] if i + 1 < len(blocks) else ""
        out.append((step, step_line, conversation_line, dialogue_content))
        i += 2

    return out


def _dialogue_key(dialogue_content: str) -> str:
    """Normalization used for dedupe."""
    lines = []
    for line in dialogue_content.splitlines():
        s = line.strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


def dedupe_conversations(conversations: List[ConversationTuple]) -> List[ConversationTuple]:
    """Keep first occurrence of each unique transcript."""
    seen = set()
    unique_rows: List[ConversationTuple] = []
    for row in conversations:
        key = _dialogue_key(row[3])
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def _pair_agents(conversation_line: str) -> List[str]:
    """Extract participant names from 'CONVERSATION: A & B'."""
    pair = conversation_line.split("CONVERSATION:", 1)[1].strip()
    return [p.strip() for p in pair.split("&") if p.strip()]


def assign_rounds(unique_conversations: List[ConversationTuple]) -> List[RoundEntryTuple]:
    """Assign round index based on unique conversations only."""
    if not unique_conversations:
        return []

    all_agents: Set[str] = set()
    for _step, _step_line, conversation_line, _dialogue in unique_conversations:
        all_agents.update(_pair_agents(conversation_line))

    rounds: List[RoundEntryTuple] = []
    round_index = 1
    seen_in_round: Set[str] = set()

    for step, _step_line, conversation_line, dialogue_content in unique_conversations:
        agents = _pair_agents(conversation_line)
        seen_in_round.update(agents)
        rounds.append((round_index, step, conversation_line, dialogue_content))

        if seen_in_round.issuperset(all_agents):
            round_index += 1
            seen_in_round.clear()

    return rounds


def write_unique(unique_rows: List[ConversationTuple], out_path: str, source_name: str) -> None:
    """Write deduped conversations (intermediate artifact)."""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("UNIQUE CONVERSATIONS (deduped transcript)\n")
        f.write(SEP + "\n")
        f.write(f"Source: {source_name}\n")
        f.write(f"Unique conversations: {len(unique_rows)}\n")
        f.write(SEP + "\n")

        for _step, step_line, conversation_line, dialogue in unique_rows:
            f.write("\n")
            f.write(SEP + "\n")
            f.write(step_line + "\n")
            f.write(conversation_line + "\n")
            f.write(SEP + "\n")
            f.write(dialogue.rstrip() + "\n")


def write_with_rounds(round_rows: List[RoundEntryTuple], out_path: str, source_name: str) -> None:
    """Write final output with round labels."""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("UNIQUE CONVERSATIONS WITH ROUNDS\n")
        f.write(SEP + "\n")
        f.write(f"Source: {source_name}\n")
        f.write(f"Conversations written: {len(round_rows)}\n")
        f.write(SEP + "\n")

        for round_index, step, conversation_line, dialogue in round_rows:
            f.write("\n")
            f.write(f"ROUND {round_index} | Step {step} | {conversation_line}\n")
            f.write(SEP + "\n")
            f.write(dialogue.rstrip() + "\n")
            f.write("\n" + SEP + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deduplicate conversations and assign rounds in one script."
    )
    parser.add_argument(
        "--input-file",
        required=True,
        help="Path to conversations_extracted.txt",
    )
    parser.add_argument(
        "--unique-out",
        required=True,
        help="Path to write unique_conversations.txt",
    )
    parser.add_argument(
        "--rounds-out",
        required=True,
        help="Path to write unique_conversations_with_rounds.txt",
    )
    args = parser.parse_args()

    unique_dir = os.path.dirname(args.unique_out)
    rounds_dir = os.path.dirname(args.rounds_out)
    if unique_dir:
        os.makedirs(unique_dir, exist_ok=True)
    if rounds_dir:
        os.makedirs(rounds_dir, exist_ok=True)

    conversations = parse_conversations(args.input_file)
    unique_rows = dedupe_conversations(conversations)
    round_rows = assign_rounds(unique_rows)

    write_unique(unique_rows, args.unique_out, args.input_file)
    write_with_rounds(
        round_rows,
        args.rounds_out,
        args.unique_out,
    )

    print(f"Source conversations: {len(conversations)}")
    print(f"Unique conversations: {len(unique_rows)}")
    if round_rows:
        print(f"Total rounds: {max(r for r, _s, _c, _d in round_rows)}")
    else:
        print("Total rounds: 0")
    print(f"Wrote: {args.unique_out}")
    print(f"Wrote: {args.rounds_out}")


if __name__ == "__main__":
    main()

