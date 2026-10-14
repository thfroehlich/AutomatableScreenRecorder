import subprocess

subprocess.run(["autoscreenrec-benchmark", r"C:\Recordings\benchmark.mp4", "--duration", "10"], check=True, shell=False)
