"""Figures for the AMR twin: one run's traces, a policy comparison, camera frames.

Noisy per-second series are drawn twice: the raw samples as a faint line and
a centred rolling mean on top, so trends are readable without hiding the
spread. Discrete signals (rung, parked) are drawn as steps, unsmoothed.
"""

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RUNG_NAMES = ["640", "640 skip", "320 skip", "320 int8"]
SIM_TAG = "[SIMULATED, assumed parameters]"


def col(rows, key):
    return np.array([r[key] for r in rows], dtype=float)


def smooth(y, window: int):
    """Centred rolling mean; edges use the samples that exist."""
    if window <= 1 or len(y) < 2:
        return y
    k = np.ones(min(window, len(y)))
    return np.convolve(y, k, "same") / np.convolve(np.ones_like(y), k, "same")


def band(ax, t, y, window, colour, label=None, raw=True):
    if raw:
        ax.plot(t, y, lw=0.5, color=colour, alpha=0.22)
    ax.plot(t, smooth(y, window), lw=1.6, color=colour, label=label)


def trace_figure(rows, cfg, path, title, window=15):
    t = col(rows, "t_s") / 60
    fig, ax = plt.subplots(2, 3, figsize=(14, 7))
    m = ax[0, 0]
    for cx, cy, length, depth, yaw in cfg["world"]["racks"]:
        a, b = (length, depth) if abs(np.sin(yaw)) < 0.5 else (depth, length)
        m.add_patch(plt.Rectangle((cx - a / 2, cy - b / 2), a, b, color="0.8"))
    sc = m.scatter(col(rows, "x"), col(rows, "y"), c=col(rows, "rung"), s=5,
                   cmap="viridis", vmin=0, vmax=3)
    wp = np.array([w["xy"] for w in cfg["route"]])
    m.plot(wp[:, 0], wp[:, 1], "k+", ms=10)
    hx, hy = cfg["world"]["hall_m"][0] / 2, cfg["world"]["hall_m"][1] / 2
    m.set(xlim=(-hx, hx), ylim=(-hy, hy), aspect="equal",
          title="path (colour = rung)", xlabel="x (m)", ylabel="y (m)")
    fig.colorbar(sc, ax=m, ticks=range(4), shrink=0.8).ax.set_yticklabels(RUNG_NAMES, fontsize=7)

    a = ax[0, 1]
    band(a, t, col(rows, "temp_c"), 5, "tab:red", "Pi temperature")
    a.plot(t, col(rows, "ambient_c"), lw=1.2, color="tab:blue", ls="--", label="ambient")
    a.axhline(80, color="crimson", ls=":", lw=0.9)
    a.fill_between(t, 0, 100, where=col(rows, "throttled") > 0, color="crimson", alpha=0.1)
    a.set(ylim=(25, 90), title="temperature (C)", xlabel="min")
    a.legend(fontsize=7, loc="lower right")

    a = ax[0, 2]
    a.fill_between(t, -0.5, 3.5, where=col(rows, "parked") > 0, step="post",
                   color="0.88", label="parked")
    a.step(t, col(rows, "rung"), where="post", lw=1.4)
    a.set(yticks=range(4), title="ladder rung", xlabel="min", ylim=(3.5, -0.5))
    a.set_yticklabels(RUNG_NAMES, fontsize=7)
    a.legend(fontsize=7, loc="lower right")

    a = ax[1, 0]
    band(a, t, col(rows, "detections"), window, "tab:blue", "detections/s")
    band(a, t, col(rows, "dropped"), window, "tab:orange", "dropped/s")
    a.set(title=f"detector ({window} s mean)", xlabel="min")
    a.legend(fontsize=7)

    a = ax[1, 1]
    band(a, t, col(rows, "util"), window, "tab:purple", "CPU util")
    band(a, t, col(rows, "burst_util"), window, "0.4", "other processes", raw=False)
    a2 = a.twinx()
    band(a2, t, col(rows, "motion"), window, "tab:green")
    a2.set_ylabel("scene motion", color="tab:green")
    a.set(title="load vs scene motion", xlabel="min", ylim=(0, 1.05))
    a.legend(fontsize=7, loc="upper left")

    a = ax[1, 2]
    a.plot(t, 100 * col(rows, "soc"), lw=1.6, color="tab:blue")
    a.set_ylabel("SoC %", color="tab:blue")
    a2 = a.twinx()
    band(a2, t, col(rows, "total_w"), window, "tab:red")
    a2.set_ylabel("power (W)", color="tab:red")
    a.set(title="battery", xlabel="min")
    fig.suptitle(f"{title}  {SIM_TAG}", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def compare_figure(runs: dict, path, window=30):
    fig, ax = plt.subplots(1, 4, figsize=(17, 3.8))
    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for (label, rows), c in zip(runs.items(), colours):
        t = col(rows, "t_s") / 60
        ax[0].plot(t, smooth(col(rows, "temp_c"), 5), lw=1.4, color=c, label=label)
        ax[1].plot(t, smooth(col(rows, "detections"), window), lw=1.4, color=c)
        ax[2].plot(t, smooth(col(rows, "util"), window), lw=1.4, color=c)
        ax[3].plot(t, 100 * col(rows, "soc"), lw=1.4, color=c)
    ax[0].axhline(80, color="crimson", ls=":", lw=0.9)
    ax[0].set(title="Pi temperature (C, 5 s mean)", xlabel="min")
    ax[1].set(title=f"detections/s ({window} s mean)", xlabel="min")
    ax[2].set(title=f"CPU util ({window} s mean)", xlabel="min", ylim=(0, 1.05))
    ax[3].set(title="battery SoC (%)", xlabel="min")
    ax[0].legend(fontsize=7)
    fig.suptitle(f"AMR twin: policy comparison  {SIM_TAG}", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def montage(frames, path, cols=3):
    """frames: list of (label, BGR image) of equal size."""
    tiles = []
    for label, img in frames:
        tile = img.copy()
        cv2.rectangle(tile, (0, 0), (tile.shape[1], 24), (0, 0, 0), -1)
        cv2.putText(tile, label, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [cv2.hconcat(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(str(path), cv2.vconcat(rows))
