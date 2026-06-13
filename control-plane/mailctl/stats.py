import os
import subprocess


def _pct(s):
    try:
        return float(s.strip().rstrip("%"))
    except ValueError:
        return 0.0


def get_stats():
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format",
         "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
        capture_output=True, text=True,
    )
    containers = []
    total_cpu = 0.0
    total_mem = 0.0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, cpu, mem_usage, mem_perc = parts
        cpu_v = _pct(cpu)
        mem_v = _pct(mem_perc)
        total_cpu += cpu_v
        total_mem += mem_v
        containers.append({
            "name": name,
            "cpu": round(cpu_v, 1),
            "mem": round(mem_v, 1),
            "mem_usage": mem_usage.strip(),
        })
    containers.sort(key=lambda c: c["name"])

    # docker reports per-container CPU relative to one core (so it can exceed
    # 100% on multi-core hosts); normalise the total to a 0-100% host figure.
    ncpu = os.cpu_count() or 1
    return {
        "containers": containers,
        "totals": {
            "cpu": round(min(total_cpu / ncpu, 100.0), 1),
            "mem": round(min(total_mem, 100.0), 1),
        },
        "cpus": ncpu,
    }
