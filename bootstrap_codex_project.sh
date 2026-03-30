#!/usr/bin/env bash

set -e

PROJECT_ROOT="$PWD"

echo "Initializing AI project workspace..."

mkdir -p ai_specs
mkdir -p ai_tasks
mkdir -p ecosystem

echo "Creating SYSTEM_SPEC.md"

cat <<'EOF' > ai_specs/SYSTEM_SPEC.md
You are a principal software architect.

Design a modular local learning ecosystem for C programming inspired by 42 School.

The system includes:

- Piscine simulator
- Exam simulator
- C learning platform
- Interactive labs
- Book based learning
- Edge case training
- Code observation mode
- Code experiment mode
- Bug fixing training
- Completion exercises
- Prediction exercises
- Productivity system
- Time tracking
- Life analytics
- Local intra dashboard

Reference repositories:

ExamPoolRevanced-main
grademe-main
grademe-mainn
Subjects
Exam00
Exam01
Exam02
ExamFinal

These must be analyzed but NOT copied.

Extract ideas and design a clean architecture implementation.

Architecture must support:

- thousands of exercises
- modular expansion
- dataset driven learning

Project modules:

core
exercises
piscine
exams
learning
productivity
intra
datasets
tools

Follow phased development.

Phase 1: architecture
Phase 2: core engine
Phase 3: exercise system
Phase 4: piscine system
Phase 5: exam system
Phase 6: learning platform
Phase 7: productivity system
Phase 8: intra dashboard
EOF


echo "Creating AI_TASK.md"

cat <<'EOF' > ai_tasks/AI_TASK.md
Read SYSTEM_SPEC.md.

Analyze the repository structure located in the current directory.

Repositories to analyze:

ExamPoolRevanced-main
grademe-main
grademe-mainn
Subjects
Exam00
Exam01
Exam02
ExamFinal

Extract:

1) exercise pool structure
2) grading logic
3) subject format
4) exam structure

Then propose a new clean architecture.

Output must include:

- system architecture
- folder structure
- module responsibilities
- dataset formats
- exercise specification
- edge case system
- learning modes
EOF


echo "Creating ROADMAP.md"

cat <<'EOF' > ai_specs/ROADMAP.md
Development Roadmap

Phase 1
Architecture design

Phase 2
Core engine implementation

Phase 3
Exercise system

Phase 4
Piscine simulator

Phase 5
Exam simulator

Phase 6
Learning platform

Phase 7
Productivity system

Phase 8
Local intra dashboard
EOF


echo "Creating project skeleton"

mkdir -p ecosystem/core
mkdir -p ecosystem/exercises
mkdir -p ecosystem/piscine
mkdir -p ecosystem/exams
mkdir -p ecosystem/learning
mkdir -p ecosystem/productivity
mkdir -p ecosystem/intra
mkdir -p ecosystem/datasets
mkdir -p ecosystem/tools

echo "Creating analysis script"

cat <<'EOF' > ai_tasks/analyze_repositories.md
Analyze the following repositories and explain:

grademe-main
ExamPoolRevanced-main

Focus on:

- grading scripts
- pool system
- subject definitions
- exam exercise selection

Do not copy code.

Explain the design philosophy and propose improvements.
EOF


echo "Setup complete."

echo ""
echo "Next steps:"
echo ""
echo "1) Start Codex CLI"
echo "2) Run:"
echo ""
echo "Analyze the project and read ai_specs/SYSTEM_SPEC.md and ai_tasks/AI_TASK.md"
echo ""
echo "Then ask:"
echo ""
echo "Design the full architecture for this system."
echo ""
