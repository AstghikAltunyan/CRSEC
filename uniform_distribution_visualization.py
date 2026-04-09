"""
Uniform distribution visualization: Trust and Conviction.
Replicates the constrained random draw from the agent-assignment code:
seed 1769606213, exactly one Grassroots Activist (conviction>=0, trust<0), not Jennifer Moore.
Shows the 10 (trust, conviction) pairs in draw order.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter, PillowWriter

# --- Replicate the original code's draw and constraint ---
REPLICATION_SEED = 1769606213
AGENTS = [
    "Mary Smith", "Bob Johnson", "Robert Brown", "David Evans",
    "Linda Taylor", "Jennifer Moore", "Sam Moore",
    "Sarah Taylor", "Tom Brown", "Andrew Williams",
]


def classify(conviction, trust):
    if conviction < 0.0 and trust < 0.0:
        return "Apathetic Cynic"
    elif conviction < 0.0 and trust >= 0.0:
        return "Passive Conformist"
    elif conviction >= 0.0 and trust < 0.0:
        return "Grassroots Activist / Dissenter"
    else:
        return "Institutional Optimist / Policy Ally"


def assign_profiles():
    """Draw conviction and trust for each agent (uses global np.random state)."""
    conviction = np.random.uniform(-1, 1, len(AGENTS))
    trust = np.random.uniform(-1, 1, len(AGENTS))
    archetypes = [classify(c, t) for c, t in zip(conviction, trust)]
    return conviction, trust, archetypes


def get_constrained_draws():
    """Replicate the run: seed 1769606213, until exactly one Grassroots Activist (not Jennifer Moore)."""
    np.random.seed(REPLICATION_SEED)
    while True:
        conviction, trust, archetypes = assign_profiles()
        activists = [
            (a, c, t) for a, c, t, arch in zip(AGENTS, conviction, trust, archetypes)
            if arch == "Grassroots Activist / Dissenter"
        ]
        if len(activists) == 1 and activists[0][0] != "Jennifer Moore":
            break
    return conviction, trust, archetypes


# Get the exact 10 pairs from the replicated run (in agent order)
_conviction, _trust, _archetypes = get_constrained_draws()
REPLICATED_PAIRS = list(zip(_trust, _conviction))  # (trust, conviction) per agent
REPLICATED_AGENTS = AGENTS

# --- Figure: Trust scale, Conviction scale, and the Bin ---
fig = plt.figure(figsize=(12, 6))
gs = fig.add_gridspec(2, 2)
ax_trust = fig.add_subplot(gs[0, 0])
ax_conviction = fig.add_subplot(gs[1, 0])
ax_bin = fig.add_subplot(gs[:, 1])

# Uniform U(-1,1) PDF: constant 1/2 on [-1, 1]. Draw as a colored band.
def draw_uniform_shape(ax, color, label="U(-1,1)"):
    ax.fill_between([-1, 1], 0.15, 0.25, color=color, alpha=0.4)
    ax.plot([-1, 1], [0.2, 0.2], color=color, lw=2.5, label=label)
    ax.plot([-1, -1], [0, 0.2], color=color, lw=1.5, alpha=0.7)
    ax.plot([1, 1], [0, 0.2], color=color, lw=1.5, alpha=0.7)

for ax, title, color in [
    (ax_trust, "Trust Draw", "red"),
    (ax_conviction, "Conviction Draw", "blue"),
]:
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.axvline(0, color="black", lw=1, alpha=0.3)
    ax.set_title(title)
    draw_uniform_shape(ax, color)

ax_bin.set_xlim(-1.1, 1.1)
ax_bin.set_ylim(-1.1, 1.1)
ax_bin.set_xlabel("Conviction (x)")
ax_bin.set_ylabel("Trust (y)")
ax_bin.set_title("The Bin (Trust, Conviction) pairs")
# Axes cross at (0, 0)
ax_bin.spines["left"].set_position(("data", 0))
ax_bin.spines["bottom"].set_position(("data", 0))
ax_bin.spines["top"].set_visible(False)
ax_bin.spines["right"].set_visible(False)
ax_bin.xaxis.set_ticks_position("bottom")
ax_bin.yaxis.set_ticks_position("left")
ax_bin.set_xticks([-1, -0.5, 0, 0.5, 1])
ax_bin.set_yticks([-1, -0.5, 0, 0.5, 1])
# Place labels just outside the 2D grid (axes coords: 0,0 = bottom-left, 1,1 = top-right)
ax_bin.xaxis.set_label_coords(0.5, 0.0)    # x-label at bottom edge
ax_bin.yaxis.set_label_coords(0.0, 0.5)    # y-label at left edge
ax_bin.grid(True, alpha=0.3)

# Replicated run caption
fig.suptitle(f"Replicated draw (seed {REPLICATION_SEED}, one Grassroots Activist ≠ Jennifer Moore)", fontsize=10)

# Data: replay REPLICATED_PAIRS one by one
bin_trust = []
bin_conviction = []
point_trust, = ax_trust.plot([], [], "ro", markersize=10)
point_conviction, = ax_conviction.plot([], [], "bo", markersize=10)
scatter_bin = ax_bin.scatter([], [], c="purple", alpha=0.5)


def update(frame):
    if frame == 0:
        bin_trust.clear()
        bin_conviction.clear()
    # Show the frame-th replicated pair (trust, conviction) in agent order
    t_val, c_val = REPLICATED_PAIRS[frame]
    point_trust.set_data([t_val], [0])
    point_conviction.set_data([c_val], [0])

    # Bin: all pairs up to and including this frame
    bin_trust.append(t_val)
    bin_conviction.append(c_val)
    scatter_bin.set_offsets(np.column_stack((bin_conviction, bin_trust)))

    return point_trust, point_conviction, scatter_bin


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Uniform Trust/Conviction draw visualization")
    parser.add_argument("--save", "-s", type=str, default="uniform_draw_recording.gif", metavar="FILE",
                        help="Save animation to file (default: uniform_draw_recording.gif)")
    parser.add_argument("--fps", type=float, default=1.0,
                        help="Frames per second for saved video (default 1)")
    args = parser.parse_args()

    n_draws = len(REPLICATED_PAIRS)
    ani = FuncAnimation(fig, update, frames=n_draws, interval=5000, blit=True, repeat=False)
    plt.tight_layout()

    if args.save:
        out = args.save
        if out.endswith(".gif"):
            writer = PillowWriter(fps=args.fps)
        else:
            writer = FFMpegWriter(fps=args.fps)
        print(f"Saving to {out} ...")
        ani.save(out, writer=writer, dpi=100)
        print(f"Saved to {out}")
    plt.show()
