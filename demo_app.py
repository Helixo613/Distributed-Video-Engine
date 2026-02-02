import streamlit as st
import subprocess
import os
import json
import sys
import pandas as pd
import altair as alt
import time
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Distributed Video Engine",
    page_icon="⚡",
    layout="wide"
)

# Title and Description
st.title("⚡ Distributed Video Rendering Engine")
st.markdown("""
This demo showcases a CPU-parallel video processing pipeline. 
It uses **ProcessPoolExecutor** to split a video into chunks, process them with **FFmpeg** in parallel, and merge them back.
""")

# Sidebar for Configuration
st.sidebar.header("Configuration")
PYTHON_BIN = sys.executable

# 1. Video Input
input_source = st.sidebar.radio("Input Source", ["Generate Test Video", "Upload Video"])

input_file = "test_input.mp4"

if input_source == "Generate Test Video":
    if st.sidebar.button("Generate Synthetic Video (30s)"):
        with st.spinner("Generating 30s test video..."):
            try:
                subprocess.run(
                    [PYTHON_BIN, "src/generate_test_video.py", "30", "test_input.mp4"],
                    check=True, capture_output=True
                )
                st.sidebar.success("Generated 'test_input.mp4'")
            except subprocess.CalledProcessError as e:
                st.sidebar.error(f"Generation failed: {e}")
    
    if os.path.exists("test_input.mp4"):
        st.sidebar.info("Using 'test_input.mp4'")
    else:
        st.sidebar.warning("Please generate a test video first.")

elif input_source == "Upload Video":
    uploaded_file = st.sidebar.file_uploader("Choose a video file", type=['mp4', 'mov'])
    if uploaded_file is not None:
        input_file = "uploaded_input.mp4"
        # Write file in chunks to avoid High Memory Usage / OOM Kills
        with open(input_file, "wb") as f:
            while True:
                chunk = uploaded_file.read(1024 * 1024) # 1MB chunk
                if not chunk:
                    break
                f.write(chunk)
        st.sidebar.success(f"Uploaded: {uploaded_file.name}")
    else:
        st.sidebar.warning("Please upload a file.")

# 2. Parameters
st.sidebar.subheader("Engine Settings")

use_smart_mode = st.sidebar.checkbox("✨ Smart Auto-Config", value=False, help="Automatically selects optimal workers and filters based on video resolution.")

if use_smart_mode:
    st.sidebar.info("Engine will optimize settings for best performance demonstration.")
    # Default/Placeholder values for variable scope
    num_workers = 8 
    filter_chain = "auto"
else:
    num_workers = st.sidebar.slider("Number of Workers (CPUs)", 1, 32, 8)
    filter_chain = st.sidebar.text_input("FFmpeg Filter", "unsharp=5:5:1.5:5:5:0.5")

mode = st.sidebar.radio("Operation Mode", ["Single Run", "Scaling Sweep (Benchmark)"])
skip_serial = st.sidebar.checkbox("Skip Serial Baseline (Faster)", value=False)

# Main Control
if st.button("🚀 Run Render Engine", type="primary"):
    
    # Construct Command
    cmd = [PYTHON_BIN, "src/render_engine.py", input_file]
    
    output_file = "output_processed.mp4"
    json_output = "results.json"
    
    cmd.extend(["-o", output_file])
    cmd.extend(["--export", json_output])
    
    if use_smart_mode:
        cmd.append("--smart")
    else:
        cmd.extend(["--filter", filter_chain])
        cmd.extend(["-w", str(num_workers)])

    if mode == "Scaling Sweep (Benchmark)":
        cmd.append("--sweep")
        
    if skip_serial:
        cmd.append("--skip-serial")

    # Display Command
    st.code(" ".join(cmd), language="bash")
    
    # Progress Area
    st.subheader("Processing Logs")
    log_area = st.empty()
    
    # Run Process
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        logs = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                # Clean up rich/ansi codes for cleaner display
                # (Simple approach: just print. Rich makes it messy but readable)
                logs.append(line)
                # Keep last 20 lines to avoid UI lag
                log_area.code("".join(logs[-20:]))
                
        if process.returncode == 0:
            st.success("Rendering Completed!")
            
            # Show Results
            if os.path.exists(json_output):
                with open(json_output, 'r') as f:
                    data = json.load(f)
                
                # 1. Video Output
                st.subheader("Result")
                if os.path.exists(output_file):
                    st.video(output_file)
                
                # 2. Metadata
                meta = data.get("metadata", {})
                col1, col2, col3 = st.columns(3)
                col1.metric("Resolution", f"{meta.get('width')}x{meta.get('height')}")
                col2.metric("FPS", f"{meta.get('fps', 0):.2f}")
                col3.metric("Duration", f"{meta.get('duration', 0):.2f}s")
                
                # 3. Benchmark Stats
                if mode == "Scaling Sweep (Benchmark)" and "sweep_results" in data:
                    results = data["sweep_results"]
                    serial_time = data.get("serial_time")
                    
                    st.subheader("Scaling Benchmark Results")
                    
                    # Prepare Data for Chart
                    chart_data = []
                    for w, res in results.items():
                        if res['success']:
                            chart_data.append({
                                "Workers": int(w),
                                "Time (s)": res['time'],
                                "Speedup": serial_time / res['time'] if serial_time and res['time'] else 0
                            })
                    
                    df = pd.DataFrame(chart_data)
                    
                    # Charts
                    c1 = alt.Chart(df).mark_line(point=True).encode(
                        x='Workers:O',
                        y='Time (s)',
                        tooltip=['Workers', 'Time (s)']
                    ).properties(title="Execution Time vs Workers")
                    
                    c2 = alt.Chart(df).mark_line(point=True, color='green').encode(
                        x='Workers:O',
                        y='Speedup',
                        tooltip=['Workers', 'Speedup']
                    ).properties(title="Speedup Factor")
                    
                    st.altair_chart(c1 | c2, use_container_width=True)
                    
                    st.dataframe(df)

                elif mode == "Single Run":
                    # Single run stats
                    res = data.get("sweep_results", {}).get(str(num_workers), {})
                    if res:
                        time_taken = res.get('time')
                        st.metric("Total Processing Time", f"{time_taken:.2f}s")
                        
                        if data.get("serial_time"):
                            speedup = data["serial_time"] / time_taken
                            st.metric("Speedup vs Serial", f"{speedup:.2f}x")

        else:
            st.error("Process failed. Check logs above.")
            
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Footer
st.markdown("---")
