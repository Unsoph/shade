"""Online first-order thermal model fitted by Bayesian recursive least squares.

Physics:  dT/dt = (T_amb + k*u - T) / tau,  u = CPU utilisation (0..1).
Regression: y = (T_next - T)/dt = th1*(-T) + th2 + th3*u with
th = [1/tau, T_amb/tau, k/tau]. The physics prior acts as a ridge on
directions the data cannot identify yet (e.g. while u is constant), and the
posterior covariance gives an uncertainty on every forecast.
"""

import math

import numpy as np

DEFAULTS = {
    "tau_s": 90.0, "ambient_c": 25.0, "k_c": 60.0,  # prior: unmeasured guesses
    "prior_rel_std": 0.5, "noise_c": 0.3, "forget": 0.998, "min_dt_s": 5.0,
    "tau_max_s": 1800.0,
}


class ThermalModel:
    def __init__(self, cfg: dict | None = None):
        c = {**DEFAULTS, **(cfg or {})}
        self.c = c
        self.theta = np.array([1 / c["tau_s"], c["ambient_c"] / c["tau_s"],
                               c["k_c"] / c["tau_s"]])
        self.P = np.diag((c["prior_rel_std"] * self.theta) ** 2)
        self.r = (c["noise_c"] * math.sqrt(2) / c["min_dt_s"]) ** 2
        self.n_updates = 0
        self._prev: tuple[float, float] | None = None  # (t, temp)
        self._u_sum = 0.0
        self._u_time = 0.0
        self._last_t: float | None = None

    def observe(self, t: float, temp: float, util: float,
                valid: bool = True) -> None:
        """Feed one sample. `valid` False (e.g. firmware throttling, which
        breaks the model's input) restarts the accumulation window."""
        if self._last_t is not None:
            self._u_sum += util * (t - self._last_t)
            self._u_time += t - self._last_t
        self._last_t = t
        if not valid:
            self._prev, self._u_sum, self._u_time = None, 0.0, 0.0
            return
        if self._prev is None:
            self._prev, self._u_sum, self._u_time = (t, temp), 0.0, 0.0
            return
        dt = t - self._prev[0]
        if dt < self.c["min_dt_s"] or self._u_time <= 0:
            return
        u = self._u_sum / self._u_time
        self._update((temp - self._prev[1]) / dt, np.array([-self._prev[1], 1.0, u]))
        self._prev, self._u_sum, self._u_time = (t, temp), 0.0, 0.0

    def _update(self, y: float, phi: np.ndarray) -> None:
        lam = self.c["forget"]
        Pphi = self.P @ phi
        gain = Pphi / (self.r + phi @ Pphi)
        self.theta = self.theta + gain * (y - phi @ self.theta)
        self.P = (self.P - np.outer(gain, phi @ self.P)) / lam
        self.theta[0] = max(self.theta[0], 1 / self.c["tau_max_s"])
        self.n_updates += 1

    def steady_state(self, util: float, z: float = 0.0) -> float:
        """Steady-state temperature at utilisation `util`; z>0 adds z standard
        deviations of posterior uncertainty (conservative)."""
        t1, t2, t3 = self.theta
        t_ss = (t2 + t3 * util) / t1
        if z <= 0:
            return t_ss
        g = np.array([-t_ss / t1, 1 / t1, util / t1])
        return t_ss + z * math.sqrt(max(float(g @ self.P @ g), 0.0))

    def forecast(self, temp: float, util: float, horizon_s: float,
                 z: float = 0.0) -> float:
        """Temperature after `horizon_s` of constant load `util`."""
        t_ss = self.steady_state(util, z)
        return t_ss + (temp - t_ss) * math.exp(-horizon_s * self.theta[0])

    @property
    def tau_s(self) -> float:
        return 1.0 / self.theta[0]
