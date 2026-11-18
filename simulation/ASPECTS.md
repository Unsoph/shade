# What to simulate

Status: **have** = in `src/sim/plant.py` today, **partial**, **to build**,
**needs Pi** = depends on hardware measurements (docs/EXPERIMENTS.md).

## A. Physics
- [x] Throttle relay, on 80 C / off 77 C (**have**)
- [x] Ambient steps (**have**)
- [ ] Heat generation: idle + dynamic (f*V^2*activity) + leakage (**partial**: linear k*u + leak)
- [ ] Multi-mass conduction: die, heatsink, case (**partial**: one node + slow mass)
- [ ] Compute time vs frequency, t = t_cpu/f + t_mem (**to build**; speed is a constant 0.55)
- [ ] Sensor noise, lag, quantization (**partial**: noise only)
- [ ] Fan steps / natural convection (**to build**)
- [x] Hot-swap transient: extra CPU during preload (**have**, AMR twin; RAM not yet)
- [x] Power-supply sag, undervoltage (**have**, AMR twin battery model)
- [x] Energy use: Pi, motors, electronics (**have**, AMR twin)
- Skip: 3D die heat flow, radiation, ageing, enclosure CFD

## AMR platform (src/sim/amr, PyBullet)
- [x] Differential-drive rigid body, wheel torque limits, casters (**have**)
- [x] Rolling resistance in drive power (**have**)
- [x] Onboard camera rendering of shelves and walkers (**have**)
- [x] Waypoint route with parking stations (**have**)
- [ ] Localisation error, obstacle avoidance (**to build**)
- [ ] Real robot parameters (mass, motors, battery) (**needs your robot**)

## B. Workload and scene
- [x] Scene motion from robot driving/parking + walkers (**have**, AMR twin rendered camera)
- [ ] Objects per frame (NMS cost) (**to build**)
- [ ] Lighting changes, dark scenes (**partial**: runtime input faults)
- [ ] Scenario library: ramp, step, burst, daily cycle (**partial**: scripted, open-loop)

## C. Pipeline timing
- [ ] Camera rate vs inference time: queue, drops, latency (**partial**: AMR twin drops detections over CPU budget; no latency)
- [ ] Control sampling interval and sensor delay (**to build**)
- [ ] Swap duration (**to build**)
- [ ] Skipped-frame staleness (**needs Pi**: E8 on real video)

## D. OS and software
- [ ] Memory and swap pressure, closed-loop (**partial**)
- [ ] SD-card model-load time (**needs Pi**)
- [ ] CPU competition from other processes (**to build**)
- [ ] Threading / GC pauses (**needs Pi**)

## E. Model quality
- [ ] Accuracy per rung and scene type (**needs Pi**: eval_agreement.py ready)
- [ ] INT8 quantization error vs FP32 (**needs Pi**)
- [ ] Staleness error from shifted boxes (**needs Pi**: E8)
- [ ] Combined accuracy x throughput metric (**to build**)

## F. Faults (closed-loop, with availability)
- [ ] Camera frozen / dark / lost (**partial**: chaos.py, runtime)
- [ ] Model load failure (**partial**)
- [ ] Crash / hang, watchdog restart cost (**partial**)
- [ ] Undervoltage (**partial**)
- [ ] Clock jumps (**to build**)
- [ ] SD-card slowdown (**to build**)

## G. Mathematical model
- [ ] Two-node RC thermal equations (**partial**)
- [ ] Per-rung throughput / power / accuracy maps (**needs Pi**: E1)
- [ ] Stochastic workload model (**to build**)
- [ ] Constrained control problem + DP-based MPC baseline (**to build**)
- [ ] Average-dwell-time stability argument for the guards (**to write**)
- [ ] Kalman estimator with ambient and gain as states (**partial**: RLS)

## H. Method
- [ ] Seeded repeated runs, >= 5 per arm (**partial**)
- [ ] Common random numbers across policies (**to confirm**)
- [ ] Bootstrap confidence intervals (**to build**)
- [ ] Fixed metrics: time above warm, throttle events, switches/h,
      accuracy, FPS, availability, latency (**partial**)
- [ ] Simulated vs real Pi trace overlay with error number (**needs Pi**: E6)
