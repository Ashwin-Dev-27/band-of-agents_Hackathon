<div align="center">

# Drone Navigation Using Liquid Neural Networks

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)

</div>

An adaptive drone controller built on a **custom Closed-form Continuous-time (CfC)-style liquid neural network in PyTorch**. The network reads the drone's state and a wind sensor, and learns to pre-compensate for wind on top of a stable PD controller. A live dashboard flies it side by side with a classic **PID baseline** under the same wind.

## How it works

```
12 inputs (position error, velocity, orientation, wind: 3 values each)
        -> input encoder (Linear + LayerNorm + tanh)
        -> 2 liquid layers (hidden size 64, input-dependent time constants)
        -> decoder -> 4 rotor-thrust outputs in [0, 1]

final thrust = PD base control + (network output - 0.5)
```

- **Liquid layers:** each cell computes a learned, input-dependent time constant and updates its hidden state with a closed-form exponential decay, so the state evolves continuously in time (about 69k parameters in total).
- **Base controller:** a PD controller keeps the drone stable and moving toward each waypoint. The network only adds a correction on top of it.
- **Obstacle avoidance:** rule-based. Nearby obstacles push the target waypoint away before it reaches the network. It is not learned.

## Training

`backend/train.py` trains the network by **behavioral cloning** (supervised learning), not reinforcement learning:

1. The PID controller flies the waypoint mission and (sensor input, target output) pairs are recorded.
2. The target is `0.5` (no correction) plus a wind-compensation term, so the network learns to push against the wind before it causes drift.
3. Optimiser: **Adam** with **cosine learning-rate annealing**, **150 episodes** across the difficulty levels, and **truncated BPTT** (hidden state detached every 25 steps).

Pre-trained weights are included in `backend/lnn_weights.pt`.

## Simulator

- Custom physics model for a quadrotor (`simulation/drone.py`).
- Environment with **wind gusts**, **turbulence** and **moving spherical obstacles** (`simulation/environment.py`).
- Four difficulty presets: `calm`, `normal`, `stormy`, `extreme`. They scale turbulence, gust frequency and the number of obstacles.
- A 6-waypoint mission with a landing zone that is checked for obstacles before descent.

## Live dashboard

A FastAPI server streams the simulation over a WebSocket. Two drones fly the same wind: one with the LNN-assisted controller and one with PID. The dashboard shows position error, average error and collision counts for both.

## Quick start

```bash
git clone https://github.com/Ashwin-Dev-27/Drone-Navigation-Using-Liquid-Neural-Network.git
cd Drone-Navigation-Using-Liquid-Neural-Network
pip install -r backend/requirements.txt

# optional: retrain the network (writes backend/lnn_weights.pt)
cd backend
python train.py

# start the dashboard
uvicorn main:app --port 8000
```

Open <http://localhost:8000>.

## Reproduce the LNN vs PID comparison

```bash
cd backend
python drone_benchmark.py            # 30 seeds per difficulty
python drone_benchmark.py --seeds 10 # quicker
```

It uses the same simulator, trained weights and PID controller as the dashboard, with identical wind for both drones on every run. It prints, per difficulty, the mean distance to the current target, missions completed within the step cap, and collisions. Results depend on seeds and difficulty, so run it yourself rather than relying on a single number.

## Project structure

```
backend/
  main.py                 FastAPI app + WebSocket simulation engine (LNN vs PID)
  train.py                behavioral-cloning trainer
  drone_benchmark.py      reproducible LNN vs PID comparison
  lnn_weights.pt          pre-trained weights
  lnn/liquid_neuron.py    custom CfC-style liquid network (PyTorch)
  simulation/
    drone.py              quadrotor physics
    environment.py        wind, gusts, turbulence, moving obstacles
    controller.py         LNN controller, PID controller, waypoint mission
frontend/                 dashboard (HTML, CSS, JS)
test_*.py                 small collision, timing, trace and WebSocket scripts
```

## Limitations

- The "liquid" cell is a simplified closed-form variant written for this project, not a reference CfC implementation.
- The network is a correction layer on a PD controller, trained by imitation of a wind-compensation target, so it is not an end-to-end learned flight controller.
- Everything runs in a custom simulator. Nothing here has been tested on a real drone.
