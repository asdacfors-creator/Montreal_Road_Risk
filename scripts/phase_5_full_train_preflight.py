"""scripts/phase_5_full_train_preflight.py — Parts 1 and 2 memory preflight."""
import psutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

vm = psutil.virtual_memory()
sw = psutil.swap_memory()

print("=== PART 1: PYTHON PROCESS TABLE (POST-CHECK) ===")
py_procs = []
for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info", "create_time"]):
    try:
        if "python" in p.info["name"].lower():
            py_procs.append(p.info)
    except Exception:
        pass

if not py_procs:
    print("  No Python processes found. Clear to proceed.")
else:
    for p in py_procs:
        cmd = " ".join(p.get("cmdline") or [])[:120]
        rss = p["memory_info"].rss / 1e9 if p.get("memory_info") else 0
        print(f"  PID {p['pid']:6d}  RSS={rss:.2f}GB  cmd={cmd}")

print()
print("=== PART 2: MEMORY PREFLIGHT ===")
print(f"  Total RAM:           {vm.total/1e9:.2f} GB")
print(f"  Available RAM:       {vm.available/1e9:.2f} GB")
print(f"  Used RAM:            {vm.used/1e9:.2f} GB")
print(f"  Memory percent:      {vm.percent:.1f}%")
print(f"  Page-file total:     {sw.total/1e9:.2f} GB")
print(f"  Page-file used:      {sw.used/1e9:.2f} GB")
print()

procs = []
for p in psutil.process_iter(["pid", "name", "memory_info"]):
    try:
        rss = p.info["memory_info"].rss
        procs.append((rss, p.info["pid"], p.info["name"]))
    except Exception:
        pass
procs.sort(reverse=True)
print("  Top 10 processes by RSS:")
for rss, pid, name in procs[:10]:
    print(f"    PID {pid:6d}  {name:<30s}  {rss/1e9:.3f} GB")

print()
ok_avail = vm.available >= 8.0e9
ok_pct   = vm.percent < 55.0

label_avail = "PASS" if ok_avail else "FAIL"
label_pct   = "PASS" if ok_pct else "FAIL"
overall     = "PROCEED" if (ok_avail and ok_pct) else "DO NOT PROCEED"

print("=== LAUNCH CONDITIONS ===")
print(f"  Available >= 8.0 GB: {vm.available/1e9:.2f} GB  -->  {label_avail}")
print(f"  Memory % < 55%:      {vm.percent:.1f}%           -->  {label_pct}")
print(f"  Overall verdict:     {overall}")
