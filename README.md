# RAT — Resident Agent & Efficient Model Evaluation Harness

RAT is a macOS resident desktop agent and efficient evaluation harness featuring local semantic search, document intake, on-device translation, Persona 5 aesthetic UI, and tool routing capabilities.

> **Note on Repository Archive:** Previous book manuscript and LaTeX materials have been organized under `_archive_book/`.

---

## Architecture Overview

```text
.
├── rat/                     # Core application
│   ├── ui/                  # Persona 5 desk, tactile QML surfaces, reading views
│   ├── engine/              # Hybrid search, reranking, local translation, context engine
│   ├── kernel/              # Dispatcher, capabilities, contracts, profile
│   ├── os/                  # macOS native integration (hotkeys, menu bar, permissions)
│   ├── crawler/             # Apple Vision, text extraction, local indexing
│   ├── astrology/           # Astrological ephemeris & chart calculations
│   └── timetable/           # Universal timetable & ICS schedule compositor
├── document_intake/         # PDF extraction, Apple Vision, OCR
├── tools/                   # Latency measurement, hotkey builder, model preparation
├── tests/                   # 105 unit and integration tests
├── requirements.txt         # Runtime dependencies (PyQt6, ctranslate2, fastembed, pyobjc...)
└── _archive_book/           # Legacy archived materials
```

---

## Getting Started

### Prerequisites
- macOS (Apple Silicon recommended)
- Python 3.11+
- Virtual environment with dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running Tests
```bash
pytest tests/
```

### Running RAT
```bash
python main.py
```
