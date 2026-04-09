"""
Visualization for LLM evaluator results.

Reads:
- `environment/frontend_server/storage/test_4o_mini/clean_results_conversation.txt`
  (from `cleaning_data.py`) to get round indices per dialogue.
- `evaluator_llm_results.csv` (from `LLM-evaluator.py`) for round-averaged
  urgency (conviction) and trust per agent, or legacy per-dialogue rows
  (see `evaluator_llm_results_per_dialogue.csv`).

Produces two line plots:
- Trust over rounds: one trajectory per agent (different colors).
- Conviction (climate urgency) over rounds: one trajectory per agent.
"""

import os
import re
import argparse
from typing import Dict

import matplotlib.pyplot as plt
import pandas as pd


# Initial (round 0) conviction (urgency) and trust per agent; used as first point in plots.
ROUND_ZERO_INITIAL = [
    ("Mary Smith", 0.94, -0.93),
    ("Bob Johnson", -0.30, -0.96),
    ("Robert Brown", -0.35, -0.86),
    ("David Evans", 0.98, 0.03),
    ("Linda Taylor", -0.22, -0.73),
    ("Jennifer Moore", -0.14, 0.27),
    ("Sam Moore", 0.64, 0.75),
    ("Sarah Taylor", -0.36, 0.46),
    ("Tom Brown", 0.07, 0.63),
    ("Andrew Williams", -0.05, -0.28),
]


def load_dialogue_to_round_mapping(clean_path: str) -> Dict[int, int]:
    """
    Build a mapping: dialogue_number -> round_index
    from the cleaned conversations file.

    Each conversation block starts with:
      ROUND <round_index> | Step <step> | CONVERSATION: ...
    and blocks are in dialogue_number order.
    """
    if not os.path.exists(clean_path):
        raise FileNotFoundError(f"Clean conversations file not found: {clean_path}")

    mapping: Dict[int, int] = {}
    dialogue_number = 0

    with open(clean_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("ROUND "):
                continue
            m = re.match(
                r"ROUND\s+(\d+)\s*\|\s*Step\s+(\d+)\s*\|\s*CONVERSATION:\s*(.+)", line
            )
            if not m:
                continue
            round_idx = int(m.group(1))
            dialogue_number += 1
            mapping[dialogue_number] = round_idx

    return mapping


def load_results_with_rounds(
    results_csv_path: str, mapping: Dict[int, int]
) -> pd.DataFrame:
    """
    Load evaluator results. If the CSV already has round_number (from
    LLM-evaluator round averaging), use it; else map dialogue_number -> round
    and aggregate means per (round, agent).
    """
    if not os.path.exists(results_csv_path):
        raise FileNotFoundError(f"Results CSV not found: {results_csv_path}")

    df = pd.read_csv(results_csv_path)
    if "agent_name" not in df.columns:
        raise ValueError("CSV must contain an 'agent_name' column.")
    if "urgency" not in df.columns or "trust" not in df.columns:
        raise ValueError("CSV must contain 'urgency' and 'trust' columns.")

    if "round_number" in df.columns:
        df_round = (
            df.rename(columns={"round_number": "round"})[
                ["round", "agent_name", "urgency", "trust"]
            ]
            .sort_values(["agent_name", "round"])
            .reset_index(drop=True)
        )
        return df_round

    if "dialogue_number" not in df.columns:
        raise ValueError(
            "CSV must contain 'dialogue_number' or pre-aggregated 'round_number'."
        )

    df["round"] = df["dialogue_number"].map(mapping)
    df = df.dropna(subset=["round"])
    df["round"] = df["round"].astype(int)

    # Aggregate in case an agent appears multiple times in a round:
    # use mean urgency/trust per agent per round.
    df_round = (
        df.groupby(["round", "agent_name"], as_index=False)[["urgency", "trust"]]
        .mean()
        .sort_values(["agent_name", "round"])
    )
    return df_round


def plot_metric_over_rounds(df_round: pd.DataFrame, metric: str, title: str, output_path: str):
    """
    Plot a metric ('trust' or 'urgency') over rounds for all agents.
    """
    plt.figure(figsize=(10, 6))
    agents = sorted(df_round["agent_name"].unique())
    for agent in agents:
        sub = df_round[df_round["agent_name"] == agent]
        plt.plot(
            sub["round"],
            sub[metric],
            marker="o",
            linewidth=1.5,
            label=agent,
        )

    plt.xlabel("Round")
    plt.ylabel(metric.capitalize())
    plt.title(title)

    # Fix vertical scale to full ideological range [-1.0, 1.0],
    # with 0.0 visually centered and highlighted.
    plt.ylim(-1.05, 1.05)
    plt.axhline(0.0, color="black", linewidth=1.0, alpha=0.4)

    plt.grid(True, linestyle="--", alpha=0.3)
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize="small")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    print(f"Saved {metric} plot to: {output_path}")
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot trust/urgency over rounds from evaluator CSV."
    )
    parser.add_argument(
        "--clean-file",
        required=True,
        help="Path to clean_results_conversation.txt (for dialogue->round mapping).",
    )
    parser.add_argument(
        "--results-csv",
        required=True,
        help="Path to evaluator results CSV (round_number or dialogue_number format).",
    )
    parser.add_argument(
        "--trust-out",
        required=True,
        help="Output path for trust plot PNG.",
    )
    parser.add_argument(
        "--urgency-out",
        required=True,
        help="Output path for urgency plot PNG.",
    )
    args = parser.parse_args()

    trust_dir = os.path.dirname(args.trust_out)
    urgency_dir = os.path.dirname(args.urgency_out)
    if trust_dir:
        os.makedirs(trust_dir, exist_ok=True)
    if urgency_dir:
        os.makedirs(urgency_dir, exist_ok=True)

    mapping = load_dialogue_to_round_mapping(args.clean_file)
    print(f"Loaded dialogue->round mapping for {len(mapping)} dialogues.")

    df_round = load_results_with_rounds(args.results_csv, mapping)
    # Prepend round 0 with initial (conviction, trust) values; rounds 1+ from CSV
    df_round0 = pd.DataFrame(
        [
            {"round": 0, "agent_name": agent, "urgency": urg, "trust": trust}
            for agent, urg, trust in ROUND_ZERO_INITIAL
        ]
    )
    df_round = df_round[df_round["round"] >= 1]
    df_round = (
        pd.concat([df_round0, df_round], ignore_index=True)
        .sort_values(["agent_name", "round"])
        .reset_index(drop=True)
    )
    print(
        f"Loaded evaluator results for {df_round['agent_name'].nunique()} agents "
        f"across {df_round['round'].nunique()} rounds (round 0 = initial values, round 1+ = CSV)."
    )

    # Plot trust over rounds
    plot_metric_over_rounds(
        df_round,
        metric="trust",
        title="Government trust over rounds (per agent)",
        output_path=args.trust_out,
    )

    # Plot conviction (urgency) over rounds
    plot_metric_over_rounds(
        df_round,
        metric="urgency",
        title="Climate urgency (conviction) over rounds (per agent)",
        output_path=args.urgency_out,
    )


if __name__ == "__main__":
    main()

