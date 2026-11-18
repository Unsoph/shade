"""Figures for the AMR twin: one run's traces, a policy comparison, camera frames."""

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RUNG_NAMES = ["640", "640 skip", "320 skip", "320 int8"]


def col(rows, key):
    return np.array([r[key] for r in rows], dtype=float)


def trace_figure(rows, cfg, path, title):
    t = col(rows, "t_s") / 60
    fig, ax = plt.subplots(2, 3, figsize=(13, 6.5))
    m = ax[0, 0]
    for x, y, sx, sy, _ in cfg["world"]["shelves"]:
        m.add_patch(plt.Rectangle((x - sx / 2, y - sy / 2), sx, sy, color="0.8"))
    sc = m.scatter(col(rows, "x"), col(rows, "y"), c=col(rows, "rung"), s=6,
                   cmap="viridis", vmin=0, vmax=3)
    wp = np.array([w["xy"] for w in cfg["route"]])
    m.plot(wp[:, 0], wp[:, 1], "k+", ms=10)
    half = cfg["world"]["arena_m"] / 2
    m.set(xlim=(-half, half), ylim=(-half, half), aspect="equal",
          title="path (colour = rung)", xlabel="x (m)", ylabel="y (m)")
    fig.colorbar(sc, ax=m, ticks=range(4)).ax.set_yticklabels(RUNG_NAMES, fontsize=7)

    a = ax[0, 1]
    a.plot(t, col(rows, "temp_c"), lw=1)
    a.axhline(80, color="crimson", ls="--", lw=0.8)
    a.axhline(70, color="orange", ls=":", lw=0.8)
    a.fill_between(t, 0, 100, where=col(rows, "throttled") > 0, color="crimson", alpha=0.1)
    a.set(ylim=(30, 90), title="Pi temperature (C)", xlabel="min")

    a = ax[0, 2]
    a.step(t, col(rows, "rung"), where="post")
    a.fill_between(t, -0.5, 3.5, where=col(rows, "parked") > 0, step="post",
                   color="0.85", label="parked")
    a.set(yticks=range(4), title="ladder rung", xlabel="min", ylim=(3.5, -0.5))
    a.set_yticklabels(RUNG_NAMES, fontsize=7)
    a.legend(fontsize=7, loc="lower right")

    a = ax[1, 0]
    a.plot(t, col(rows, "detections"), lw=0.8, label="detections/s")
    a.plot(t, col(rows, "dropped"), lw=0.8, label="dropped/s")
    a.set(title="detector", xlabel="min")
    a.legend(fontsize=7)

    a = ax[1, 1]
    a.plot(t, col(rows, "util"), lw=0.8, label="CPU util")
    a2 = a.twinx()
    a2.plot(t, col(rows, "motion"), lw=0.6, color="tab:green", alpha=0.7)
    a2.set_ylabel("scene motion", color="tab:green")
    a.set(title="load vs scene motion", xlabel="min", ylim=(0, 1.05))

    a = ax[1, 2]
    a.plot(t, 100 * col(rows, "soc"), lw=1, label="SoC %")
    a2 = a.twinx()
    a2.plot(t, col(rows, "total_w"), lw=0.5, color="tab:red", alpha=0.6)
    a2.set_ylabel("power (W)", color="tab:red")
    a.set(title="battery", xlabel="min")
    fig.suptitle(f"{title}  [SIMULATED, assumed parameters]", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def compare_figure(runs: dict, path):
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    for label, rows in runs.items():
        t = col(rows, "t_s") / 60
        ax[0].plot(t, col(rows, "temp_c"), lw=0.9, label=label)
        ax[1].plot(t, np.convolve(col(rows, "detections"), np.ones(30) / 30, "same"),
                   lw=0.9, label=label)
        ax[2].plot(t, 100 * col(rows, "soc"), lw=0.9, label=label)
    ax[0].axhline(80, color="crimson", ls="--", lw=0.8)
    ax[0].set(title="Pi temperature (C)", xlabel="min")
    ax[1].set(title="detections/s (30 s mean)", xlabel="min")
    ax[2].set(title="battery SoC (%)", xlabel="min")
    ax[0].legend(fontsize=7)
    fig.suptitle("AMR twin: policy comparison  [SIMULATED, assumed parameters]",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def montage(frames, path, cols=3):
    """frames: list of (label, BGR image)."""
    tiles = []
    for label, img in frames:
        tile = img.copy()
        cv2.rectangle(tile, (0, 0), (tile.shape[1], 18), (0, 0, 0), -1)
        cv2.putText(tile, label, (4, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [cv2.hconcat(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(str(path), cv2.vconcat(rows))
