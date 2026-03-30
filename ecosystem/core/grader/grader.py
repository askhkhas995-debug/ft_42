import subprocess

def compile_and_run(file):
    subprocess.run(["gcc",file])
    subprocess.run(["./a.out"])
