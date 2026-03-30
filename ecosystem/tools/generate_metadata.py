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
