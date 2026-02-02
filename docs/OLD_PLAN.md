# Distributed Video Rendering Engine (CPU-only, WSL) — Implementation Plan (Hackathon MVP)

This document consolidates the **best parts** of the two drafts (`GEMINI.md` and `CLAUDE.md`) into **one robust, hackathon-ready implementation plan**, and then lists **all key differences** between the two drafts.

---

## 0) Executive Summary

We will build a proof-of-concept “Distributed Video Rendering Engine” using a **Split–Process–Merge** pattern on **commodity CPU** (WSL Ubuntu).  
Even though it runs locally, it will **simulate a distributed coordinator + workers architecture** and will explicitly demonstrate **Amdahl’s Law** using **serial vs parallel benchmarks**.

**Core strategy (MVP):**
- **Virtual Split**: avoid physically splitting to disk; each worker seeks its own segment from the original input.
- **Parallel Process**: apply a **CPU-expensive filter chain** per segment using FFmpeg.
- **Merge**: concatenate processed segments back into a final MP4.
- **Benchmark**: show timing + speedup + efficiency across worker counts.

---

## 1) Constraints & Goals

### Environment constraints
- **WSL Ubuntu**, CPU-only (no CUDA passthrough configured).
- FFmpeg and ffprobe available from PATH.
- Python 3.10+; pip allowed.

### Hackathon constraints
- Must be **demo-stable** and **finish EOD**.
- Must clearly show **speedup** and a **distributed-style architecture** (even if local).

### Acceptance criteria (“Definition of Done”)
- Input: MP4 (typical H.264 video + AAC audio).
- Output: processed MP4, same duration, **no green frames / boundary corruption**.
- Demo prints: serial time, parallel time, **speedup factor**, efficiency, core count.
- Temp files cleaned reliably (even on failure), with an option to keep artifacts for debugging.

---

## 2) Library & Tool Stack (CPU-only WSL)

### Chosen stack (recommended)
**Use raw FFmpeg via Python `subprocess` + `ffprobe`**, not MoviePy.

**Why this is best for WSL CPU-only MVP:**
- FFmpeg is **highly optimized C**: your performance story stays about parallelism, not Python overhead.
- MoviePy introduces Python-side pipeline costs and can be fragile for heavy filters at scale.
- `ffmpeg-python` is OK, but `subprocess` is simplest, most predictable, and easiest to debug under time pressure.

### Python dependencies
- `rich`: live progress UI + final timing table.
- `psutil`: CPU utilization, load and memory telemetry.
- Standard library: `multiprocessing`, `concurrent.futures`, `json`, `pathlib`, `time`, `hashlib`.

### External dependencies
- `ffmpeg`, `ffprobe`

---

## 3) Architecture (Coordinator + Worker Contract)

### Components
1. **Analyzer**
   - Uses ffprobe to read: duration, fps, resolution, audio presence, codec info.
2. **Planner**
   - Converts (start, duration) into chunk tasks.
   - Oversubscribes tasks: chunks > workers (e.g., 1.5×–3×) for load balancing.
3. **Coordinator**
   - Owns the task queue, retries, job manifest, stage timing.
4. **Workers (N processes)**
   - Each worker executes FFmpeg on a chunk task.
5. **Merger**
   - Concats segments via concat demuxer, stream copy if safe.
   - Includes a fallback “re-encode merge” if concat-copy fails.

### Text diagram
```
Input.mp4
  │
  ├── Analyzer (ffprobe) → metadata.json
  │
  ├── Planner → manifest.json (chunk tasks)
  │
  ├── Coordinator
  │     ├── dispatch tasks → Worker Pool (multiprocessing)
  │     ├── collect results + retries
  │     └── produces concat_list.txt
  │
  └── Merger (ffmpeg concat) → output_processed.mp4
```

---

## 4) GOP / Boundary Strategy (No green frames)

The main danger is boundary corruption due to GOP/keyframes and timestamp issues.

We will provide **two splitting modes** and pick the safe default for the demo.

### Mode A: FAST (Keyframe-aligned splitting)
- Find keyframe boundaries near desired cut points.
- Cut only on those boundaries.
- Pros: fastest, avoids re-encode for splitting.
- Cons: chunk lengths drift; requires scanning keyframes; more engineering.

**Best when:** you want maximum throughput and can tolerate segment drift.

### Mode B: ROBUST (Re-encode each segment, virtual split) — **default**
- Each worker:
  - Seeks into the original file (`-ss start`) and processes for `-t duration`.
  - Re-encodes the segment, ensuring it is independently decodable.
- Pros: simplest, reliable, no dependency on source GOP.
- Cons: encoding cost per chunk (acceptable in MVP).

**Boundary robustness additions (recommended):**
1. **Timestamp reset per chunk**  
   Ensure each chunk starts at time 0 and has clean monotonic timestamps.
2. **Tiny overlap + trim (optional but strong)**  
   Add a small overlap (e.g., 0.25s) to each segment to avoid edge glitches, then trim precisely.
3. **Stream consistency check before merge**  
   Ensure all chunks have identical stream properties (codec/pix_fmt/resolution/fps).

**Why this works in a demo:** You trade a bit of encode cost for “always plays correctly,” which is what matters in judging.

---

## 5) Data Flow & File/Folder Conventions

### Directory layout
```
project/
  render_engine.py
  outputs/
    final/
    runs/
      run_YYYYMMDD_HHMMSS/
        meta.json
        manifest.json
        concat_list.txt
        chunks/
          chunk_000.mp4
          chunk_001.mp4
          ...
        logs/
          worker_000.log
          worker_001.log
```

### Naming conventions
- Run ID: `run_YYYYMMDD_HHMMSS`
- Chunks: `chunk_{chunk_id:03d}.mp4`
- Concat list: `concat_list.txt` (relative paths preferred)
- Manifest: `manifest.json` (idempotency + retries)
- Final output: `outputs/final/output_{run_id}.mp4`

### Cleanup policy
- Default: delete `runs/run_id/chunks` after successful merge.
- Flags:
  - `--keep-temp`: keep all run artifacts.
  - `--clean`: delete old run dirs.

---

## 6) Worker “Task Contract” (Tdarr-inspired, local simulation)

Each chunk task in `manifest.json`:
```json
{
  "chunk_id": 3,
  "start_sec": 30.0,
  "duration_sec": 10.0,
  "input": "input.mp4",
  "output": "chunks/chunk_003.mp4",
  "status": "queued",
  "attempts": 0,
  "runtime_ms": null,
  "worker_pid": null,
  "cmd_hash": "…"
}
```

Coordinator behavior:
- Mark `running` with PID, start time.
- On success: `done` + runtime.
- On failure: increment attempts, retry up to N times, then fail the run.

This makes your “distributed engine” story real even on one machine.

---

## 7) Filter Choice (CPU-heavy but demo-friendly)

Goal: make the workload **clearly compute-bound** and scalable with cores, while keeping encoding overhead controlled.

### Recommended approach
- Use an FFmpeg filter chain that is expensive but deterministic:
  - Examples: multi-pass blur + unsharp + scale.
- Keep encode preset fast:
  - `libx264` with `-preset ultrafast` and a reasonable `-crf`.

**Audio policy (choose one for MVP):**
- MVP simplest: copy audio in every chunk and concat (can be okay).
- More robust: process video-only chunks; at the end, reattach audio from the original (stream copy).

(We’ll pick one explicitly during implementation.)

---

## 8) Merge Strategy

### Primary: concat demuxer (fast)
- Build `concat_list.txt`:
  ```
  file 'chunks/chunk_000.mp4'
  file 'chunks/chunk_001.mp4'
  ...
  ```
- Merge with `-c copy` when streams match.

### Fallback: re-encode merge (reliable)
If concat-copy fails (stream mismatch, timestamp issues):
- Merge and re-encode once at the end (slower, but safe for demo success).

---

## 9) Benchmark Plan (Amdahl-ready)

### Measurements (use `time.perf_counter()`)
Track and print:
- `T_analyze` (ffprobe)
- `T_process_serial` (same total work, 1 worker)
- `T_process_parallel_wall`
- `T_merge`
- `T_total_serial`
- `T_total_parallel`

### Metrics to report
- **Speedup**: `S = T_serial / T_parallel_wall`
- **Efficiency**: `E = S / N_workers`
- Optional: estimate serial fraction from Amdahl and compare.

### Scaling sweep (high impact in demos)
Run for worker counts: `1, 2, 4, 8, ... up to CPU cores`.
Print a table:
- workers | wall_time | speedup | efficiency | avg_cpu%

### Fairness / credibility
- Report split overhead separately (virtual split makes it near-zero).
- Keep input and filter identical across runs.
- Warm-up run optional (or just run once per config due to time).

---

## 10) Demo Checklist (What judges will see)

- Show system info: CPU cores, WSL environment, FFmpeg version.
- Run baseline (1 worker).
- Run parallel (N workers).
- Print timing table + speedup + efficiency.
- Play output video quickly to confirm no corruption.
- Show that manifest exists + workers logged their tasks.

---

# Differences Between GEMINI.md and CLAUDE.md (and what we kept)

## A) Philosophy
- **GEMINI.md:** Optimize for maximum speedup by **eliminating serial split** via *Virtual Split*.  
- **CLAUDE.md:** Emphasize *clean architecture* and measured pipeline stages (split/process/merge) with FFmpeg subprocess.

✅ **We kept:** GEMINI’s *Virtual Split* + CLAUDE’s structured pipeline thinking.

## B) Video processing approach
- **GEMINI.md:** Concrete example command with heavy filter (`unsharp`) and `ultrafast` preset, audio copy.
- **CLAUDE.md:** “Raw FFmpeg via subprocess” as the main design rule; filter chain is a placeholder.

✅ **We kept:** FFmpeg subprocess as the core execution mechanism and a CPU-heavy filter strategy.

## C) “Distributed” architecture flavor
- **GEMINI.md:** Strong emphasis on Amdahl and speedup; includes live dashboard idea.
- **CLAUDE.md:** Coordinator/worker implied but more “pipeline” style.

✅ **We kept:** GEMINI’s demo/telemetry mindset and formalized it with CLAUDE-style components.

## D) Benchmarking emphasis
- **GEMINI.md:** Two-pass protocol / focus on speedup and minimizing serial fraction.
- **CLAUDE.md:** Clear benchmark requirements and Amdahl mention, stage awareness.

✅ **We kept:** Both, but made it *more defensible* by separating overhead stages and adding scaling sweeps.

---

# Additions Beyond Both Drafts (New, high-value improvements)

These were not fully specified in either file, but are crucial for a stable hackathon demo:

1. **Chunk manifest (JSON) + idempotency + retries** (Tdarr-like queue simulation)
2. **Timestamp hygiene per chunk** to prevent concat/corruption issues
3. **Stream compatibility checks** (codec/pix_fmt/resolution/fps) before concat
4. **Fallback merge path** (re-encode final merge if stream-copy concat fails)
5. **Run-ID workdirs + cleanup flags** for fast iteration and safe debugging
6. **Optional overlap strategy** for boundary glitch avoidance

---

## Next Step
Once you confirm:
- audio policy (copy-per-chunk vs reattach at end),
- chunk duration (10s vs 5s),
- default worker count strategy,

…we will move to implementation (code).
