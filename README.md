# The House That Learns
### An AI-Powered First-Person Psychological Horror Game

**The House That Learns** is a Python-based 3D psychological horror game in which an intelligent entity observes the player's behavior and adapts its actions accordingly. Unlike traditional horror games that rely entirely on scripted enemy behavior, this project explores a hybrid artificial intelligence approach combining rule-based decision-making and machine learning.

The house becomes increasingly unpredictable as the player explores, hides, sprints, and repeats familiar routes. The goal is to survive, find the key, and escape while avoiding an entity that attempts to anticipate the player's behavior.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Key Features](#key-features)
- [Technologies Used](#technologies-used)
- [Project Structure](#project-structure)
- [Installation and Setup](#installation-and-setup)
- [Running the Game in PyCharm](#running-the-game-in-pycharm)
- [How to Play](#how-to-play)
- [AI System Architecture](#ai-system-architecture)
- [Gameplay Telemetry](#gameplay-telemetry)
- [Research Objectives](#research-objectives)
- [Current Limitations](#current-limitations)
- [Future Improvements](#future-improvements)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Project Overview

The central idea behind *The House That Learns* is to investigate whether an adaptive AI-controlled enemy can create a more immersive, tense, and unpredictable horror experience than a conventional scripted enemy.

The game uses a first-person perspective and a simple 3D house environment. Players must explore the environment, locate a key, and reach the exit while the enemy transitions between different behavioral states.

The project is designed as both a playable prototype and a foundation for research into adaptive game AI.

## Key Features

- **3D first-person gameplay:** Explore a house from the player's perspective.
- **Psychological horror:** Survive while an entity searches for and pursues you.
- **Hybrid enemy AI:** Combines rule-based behavior with a machine learning classifier.
- **Behavioral adaptation:** Estimates player tendencies, including exploration, hiding, sprinting, and repeating routes.
- **Multiple enemy states:** Supports patrolling, investigating, chasing, and searching.
- **Flashlight mechanic:** Toggle a flashlight to assist exploration.
- **Hiding mechanic:** Hide near designated furniture to avoid the enemy.
- **Key and escape objective:** Find the key and reach the exit.
- **Gameplay telemetry:** Record gameplay events and behavioral data for later analysis.
- **Research-oriented design:** Provides a foundation for comparing scripted and adaptive enemy strategies.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core game logic and AI implementation |
| Panda3D | 3D rendering, game loop, input, and scene management |
| NumPy | Numerical operations and feature processing |
| pandas | Gameplay telemetry and CSV data handling |
| scikit-learn | Machine learning and player-behavior classification |
| PyCharm | Recommended development environment |

## Project Structure

```text
The_House_That_Learns/
│
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
│
└── data/
    ├── .gitkeep
    └── gameplay_log.csv
```

**File descriptions**

- `main.py`: Main game implementation, including player controls, the environment, enemy behavior, and AI logic.
- `requirements.txt`: Python dependencies required to run the game.
- `README.md`: Project documentation and setup instructions.
- `.gitignore`: Files and folders excluded from version control.
- `data/`: Directory intended for gameplay logs and research data. The CSV log is generated when supported telemetry events are recorded.

## Installation and Setup

### Prerequisites

Install the following before running the game:

- Python 3.11 or 3.12 recommended.
- PyCharm Community Edition or Professional Edition.
- Git (optional, for version control).

### 1. Download the project

Download and extract the project ZIP file, then open the extracted folder in PyCharm.

Make sure `main.py` and `requirements.txt` are in the project root directory.

### 2. Open the project in PyCharm

1. Launch PyCharm.
2. Select **Open**.
3. Choose the `The_House_That_Learns` folder.
4. Allow PyCharm to index the project.

### 3. Configure a Python interpreter

In PyCharm:

1. Open **File → Settings → Project → Python Interpreter**.
2. Select an existing Python 3.11 or 3.12 interpreter, or create a new virtual environment.
3. If creating a virtual environment, use `.venv` inside the project folder.
4. Apply the settings.

Menu labels may vary slightly by PyCharm version.

### 4. Install dependencies

Open the PyCharm Terminal and run:

```powershell
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Using `python -m pip` helps avoid situations where the standalone `pip` command is not recognized by PowerShell.

If `python` is unavailable but the Windows Python launcher is installed, try:

```powershell
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r requirements.txt
```

If pip is missing from an otherwise working Python installation, try:

```powershell
python -m ensurepip --upgrade
python -m pip install -r requirements.txt
```

### 5. Verify the dependencies

Run:

```powershell
python -m pip show panda3d
python -m pip show numpy
python -m pip show pandas
python -m pip show scikit-learn
```

Each command should display package information if that dependency is installed in the selected environment.

## Running the Game in PyCharm

1. Open `main.py`.
2. Ensure the correct Python interpreter is selected.
3. Right-click the editor or file name.
4. Select **Run 'main'**.

Alternatively, run the game from the PyCharm Terminal:

```powershell
python main.py
```

A graphical window should open if Panda3D and the project's graphical environment are configured correctly.

## How to Play

### Controls

| Key | Action |
|---|---|
| W | Move forward |
| A | Move left |
| S | Move backward |
| D | Move right |
| Mouse | Look around |
| Shift | Sprint |
| F | Toggle flashlight |
| E | Interact with objects |
| H | Hide near supported hiding locations |
| Esc | Exit or pause behavior, depending on the current implementation |

**Objective:** Explore the house, find the key, avoid the entity, and reach the exit.

The enemy may patrol, investigate activity, chase the player, or search an area depending on its current state and the implemented decision logic.

*Note: Exact control behavior and interaction availability depend on the current implementation in `main.py`.*

## AI System Architecture

The game uses a hybrid AI design with two primary components.

### 1. Rule-Based Decision System

The rule-based component manages immediate enemy behavior using conditions such as player proximity, recent activity, and the current enemy state.

Its behavioral states include:

- **Patrol:** Move around the house.
- **Investigate:** Move toward a suspected location or activity.
- **Chase:** Pursue the player when the detection conditions are satisfied.
- **Search:** Search an area after losing track of the player.

### 2. Machine Learning Component

The prototype uses a `DecisionTreeClassifier` from scikit-learn to estimate a player's behavioral style.

The initial behavior categories include:

- **Explorer:** Frequently explores different areas.
- **Hider:** Relies heavily on hiding.
- **Sprinter:** Frequently uses sprinting.
- **Route Repeater:** Tends to reuse familiar paths.

The predicted style can inform adaptive enemy decisions.

**Important research limitation:** The initial classifier is trained using synthetic examples. It demonstrates the intended AI pipeline but does not establish that the system has learned from real players. Training and evaluating on actual gameplay telemetry is a future development step.

### 3. Hybrid Decision Pipeline

```text
Player Actions
      |
      v
Behavior Feature Collection
      |
      v
Machine Learning Classifier
      |
      v
Estimated Player Style
      |
      v
Rule-Based Enemy Decision Logic
      |
      v
Enemy State and Behavior
      |
      v
Gameplay Telemetry
```

This architecture provides a starting point for investigating how machine learning can complement deterministic game logic.

## Gameplay Telemetry

The project includes a `data/` directory intended for recording gameplay information.

Depending on the events implemented in `main.py`, the telemetry CSV may contain information such as:

- Player movement and behavior.
- Enemy state transitions.
- Hiding and sprinting activity.
- Player detection or encounter events.
- Timestamps and other game-state information.

The resulting data can be used to study player behavior and evaluate enemy adaptation.

Before conducting experiments, verify the actual CSV columns and confirm that events are logged consistently. Avoid collecting personally identifiable information unless it is necessary and appropriately consented to.

## Research Objectives

The project can support research into adaptive enemy AI and player experience.

### Primary research question

Does a behavior-adaptive enemy create a more tense, immersive, and unpredictable horror experience than a conventional scripted enemy?

### Potential experimental conditions

1. **Scripted AI:** Enemy behavior follows predefined rules without a learned player profile.
2. **Rule-Based Adaptive AI:** Enemy behavior adapts using explicit behavioral rules.
3. **Hybrid AI:** Machine learning estimates player tendencies, which inform rule-based enemy decisions.

### Potential evaluation metrics

| Metric | Purpose |
|---|---|
| Completion time | Measure how long players take to escape |
| Detection frequency | Measure how often the enemy detects players |
| Encounter count | Measure player–enemy encounters |
| Route diversity | Estimate variation in player movement |
| Perceived tension | Collect player ratings through a questionnaire |
| Immersion | Evaluate the player's sense of presence |
| Perceived fairness | Determine whether enemy adaptation feels reasonable |
| Behavioral prediction accuracy | Evaluate predictions against labeled player behavior |

These metrics are proposed evaluation measures, not completed experimental results. A rigorous study should use controlled conditions, an appropriate participant sample, and documented statistical analysis.

## Current Limitations

The current version is an early prototype. Known limitations include:

- Basic geometric shapes rather than polished 3D models.
- Simple enemy movement instead of full navigation and pathfinding.
- Approximate enemy detection rather than realistic line-of-sight and occlusion.
- A machine learning model initially trained on synthetic data.
- Limited environmental detail, animation, audio, and lighting effects.
- Experimental metrics that still require validation through real gameplay sessions.

These limitations are intended to guide subsequent development.

## Future Improvements

Planned development directions include:

- Improve the house environment with detailed 3D assets and lighting.
- Add footsteps, ambient audio, and dynamic sound cues.
- Implement robust enemy navigation and line-of-sight detection.
- Train the behavior model using actual gameplay data.
- Add difficulty adaptation based on player performance.
- Compare scripted, rule-based, and hybrid AI under controlled conditions.
- Develop dashboards for visualizing gameplay telemetry.
- Evaluate player tension, immersion, unpredictability, and perceived fairness.
- Improve reproducibility through fixed configurations and experiment logs.

## Troubleshooting

### `pip` is not recognized

Use:

```powershell
python -m pip install -r requirements.txt
```

If `python` is not recognized, check whether the Python launcher works:

```powershell
py --version
```

Then use the `py` launcher to install the dependencies.

### `ModuleNotFoundError`

Install the dependencies in the same Python environment selected in PyCharm:

```powershell
python -m pip install -r requirements.txt
```

### The game window does not open

Check that Panda3D is installed and that PyCharm is using the expected interpreter:

```powershell
python -m pip show panda3d
python main.py
```

Read the complete traceback in the Run window. A graphical driver issue, incorrect interpreter, or runtime error may prevent the window from opening.

### The game starts but behaves unexpectedly

The prototype uses simplified movement, detection, and enemy logic. Review the relevant functions in `main.py` and use PyCharm's debugger to inspect the current game state.

## License

No license has been specified yet. Add an appropriate license before distributing the project publicly, and verify the licensing terms of any third-party assets, models, sounds, and libraries used.

---

**The House That Learns** is an experimental project exploring the intersection of artificial intelligence, adaptive gameplay, and psychological horror.

*Built with Python, Panda3D, and scikit-learn.*
