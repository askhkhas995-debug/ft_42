#!/usr/bin/env bash

set -e

echo "======================================="
echo "C Learning Ecosystem Builder"
echo "======================================="

ROOT="$PWD"
ECOSYSTEM="$ROOT/ecosystem"

echo "Creating directories..."

mkdir -p "$ECOSYSTEM"

MODULES=(
core
exercises
piscine
exams
learning
productivity
intra
datasets
tools
)

for m in "${MODULES[@]}"
do
    mkdir -p "$ECOSYSTEM/$m"
done

echo "Creating dataset directories..."

mkdir -p "$ECOSYSTEM/datasets/subjects"
mkdir -p "$ECOSYSTEM/datasets/exercises"
mkdir -p "$ECOSYSTEM/datasets/pools"
mkdir -p "$ECOSYSTEM/datasets/exams"
mkdir -p "$ECOSYSTEM/datasets/books"

echo "Creating productivity modules..."

mkdir -p "$ECOSYSTEM/productivity/tasks"
mkdir -p "$ECOSYSTEM/productivity/pomodoro"
mkdir -p "$ECOSYSTEM/productivity/habits"
mkdir -p "$ECOSYSTEM/productivity/timeline"
mkdir -p "$ECOSYSTEM/productivity/analytics"

echo "Creating learning modules..."

mkdir -p "$ECOSYSTEM/learning/knr"
mkdir -p "$ECOSYSTEM/learning/theory_to_practice"
mkdir -p "$ECOSYSTEM/learning/practice"

echo "Creating piscine levels..."

for i in {00..13}
do
    mkdir -p "$ECOSYSTEM/piscine/c$i"
done

mkdir -p "$ECOSYSTEM/piscine/shell00"
mkdir -p "$ECOSYSTEM/piscine/shell01"

echo "Creating exam ranks..."

mkdir -p "$ECOSYSTEM/exams/rank00"
mkdir -p "$ECOSYSTEM/exams/rank01"
mkdir -p "$ECOSYSTEM/exams/rank02"
mkdir -p "$ECOSYSTEM/exams/final"

echo "Creating intra UI structure..."

mkdir -p "$ECOSYSTEM/intra/backend"
mkdir -p "$ECOSYSTEM/intra/frontend"
mkdir -p "$ECOSYSTEM/intra/frontend/js"
mkdir -p "$ECOSYSTEM/intra/frontend/css"

echo "Creating core engine structure..."

mkdir -p "$ECOSYSTEM/core/compiler"
mkdir -p "$ECOSYSTEM/core/runner"
mkdir -p "$ECOSYSTEM/core/grader"
mkdir -p "$ECOSYSTEM/core/sandbox"
mkdir -p "$ECOSYSTEM/core/test_engine"
mkdir -p "$ECOSYSTEM/core/pool_engine"
mkdir -p "$ECOSYSTEM/core/exam_engine"

echo "Extracting subjects..."

if [ -d "Subjects" ]; then
    find Subjects -name "subject*.txt" -exec cp {} "$ECOSYSTEM/datasets/subjects/" \;
fi

echo "Extracting exam exercises..."

for EX in Exam00 Exam01 Exam02 ExamFinal
do
    if [ -d "$EX" ]; then
        cp -r "$EX" "$ECOSYSTEM/datasets/exams/"
    fi
done

echo "Extracting pools..."

if [ -d "ExamPoolRevanced-main" ]; then
    cp -r ExamPoolRevanced-main "$ECOSYSTEM/datasets/pools/"
fi

echo "Creating exercise metadata generator..."

cat << 'EOF' > "$ECOSYSTEM/tools/generate_metadata.py"
import os
import json

root = "../datasets/subjects"

for file in os.listdir(root):
    if file.endswith(".txt"):
        name = file.replace(".txt","")
        meta = {
            "name": name,
            "language": "c",
            "difficulty": "unknown",
            "skills": [],
            "tests": []
        }

        out = "../datasets/exercises/" + name + ".json"

        with open(out,"w") as f:
            json.dump(meta,f,indent=4)
EOF

echo "Creating edge case framework..."

cat << 'EOF' > "$ECOSYSTEM/core/test_engine/edge_cases.py"
EDGE_CASES = [
    "",
    " ",
    "0",
    "-1",
    "large_input",
]
EOF

echo "Creating observation mode placeholder..."

cat << 'EOF' > "$ECOSYSTEM/learning/observation_mode.py"
def run_observation(code):
    print("Running observation mode")
EOF

echo "Creating experiment mode placeholder..."

cat << 'EOF' > "$ECOSYSTEM/learning/experiment_mode.py"
def run_experiment(code):
    print("Running experiment mode")
EOF

echo "Creating bug injection system..."

cat << 'EOF' > "$ECOSYSTEM/learning/bug_injection.py"
def inject_bug(code):
    return code.replace("==","=")
EOF

echo "Creating simple grader prototype..."

cat << 'EOF' > "$ECOSYSTEM/core/grader/grader.py"
import subprocess

def compile_and_run(file):
    subprocess.run(["gcc",file])
    subprocess.run(["./a.out"])
EOF

echo "Creating timeline tracker..."

cat << 'EOF' > "$ECOSYSTEM/productivity/timeline/timeline.py"
import datetime

def log_activity(name):
    now = datetime.datetime.now()
    print("Activity:",name,"Time:",now)
EOF

echo "Creating tasks system..."

cat << 'EOF' > "$ECOSYSTEM/productivity/tasks/tasks.py"
tasks = []

def add_task(name):
    tasks.append(name)
EOF

echo "Creating habits system..."

cat << 'EOF' > "$ECOSYSTEM/productivity/habits/habits.py"
habits = {}

def track(name):
    habits[name] = habits.get(name,0)+1
EOF

echo "Creating simple API backend..."

cat << 'EOF' > "$ECOSYSTEM/intra/backend/server.py"
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"system":"C Learning Ecosystem"}
EOF

echo "Creating dashboard UI..."

cat << 'EOF' > "$ECOSYSTEM/intra/frontend/index.html"
<html>
<head>
<title>Intra Dashboard</title>
</head>
<body>
<h1>C Learning Ecosystem</h1>
</body>
</html>
EOF

echo "Building book datasets..."

if [ -f "C_Book_2nd.pdf" ]; then
    cp C_Book_2nd.pdf "$ECOSYSTEM/datasets/books/"
fi

if [ -f "C_From_Theory_to_Practice.pdf" ]; then
    cp C_From_Theory_to_Practice.pdf "$ECOSYSTEM/datasets/books/"
fi

echo "======================================="
echo "Project skeleton created successfully"
echo "======================================="
