import os
import subprocess
import threading
from flask import Flask, render_template, jsonify, send_from_directory, request
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Global state to track running tasks
state = {
    "current_task": None,
    "status": "idle", # idle, running, error, success
    "logs": [],
    "process_handle": None
}

def run_script(script_name, task_name, args=None):
    global state
    state["current_task"] = task_name
    state["status"] = "running"
    state["logs"] = []
    
    # Run python with UTF-8 to prevent unicode encode errors
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Scripts", script_name)
        cmd = ["python", "-u", "-X", "utf8", script_path]
        if args:
            cmd.extend(args)
            
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "Scripts")
        )
        state["process_handle"] = process
        
        for line in process.stdout:
            line = line.strip()
            # Collapse progress bars to prevent log flooding
            if line.startswith("[PROGRESS]") and state["logs"] and state["logs"][-1].startswith("[PROGRESS]"):
                state["logs"][-1] = line
            else:
                state["logs"].append(line)
            
            # Keep only the last 100 lines of logs to prevent memory bloat
            if len(state["logs"]) > 100:
                state["logs"].pop(0)
                
        process.wait()
        
        if process.returncode == 0:
            state["status"] = "success"
        elif process.returncode == -15 or process.returncode == 1:
            state["status"] = "error"
            state["logs"].append("Task was stopped by user.")
        else:
            state["status"] = "error"
            state["logs"].append(f"Task failed with exit code {process.returncode}")
            
    except Exception as e:
        state["status"] = "error"
        state["logs"].append(str(e))
    finally:
        state["process_handle"] = None
        if state["status"] != "error":
            state["current_task"] = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    return jsonify({
        "task": state["current_task"],
        "status": state["status"],
        "logs": state["logs"]
    })

@app.route("/api/run/<script_id>", methods=["POST"])
def run_task(script_id):
    if state["status"] == "running":
        return jsonify({"error": "A task is already running"}), 400
        
    scripts = {
        "generate": "data_generation.py",
        "train": "ml_model.py",
        "optimize": "ga_active_learning.py",
        "cst_optimize": "cst_optimization.py"
    }
    
    if script_id not in scripts:
        return jsonify({"error": "Invalid script ID"}), 400
        
    args = []
    
    # Handle custom parameters for generate and optimize
    mach = request.form.get('mach')
    re = request.form.get('reynolds')
    ar = request.form.get('ar')
    oswald = request.form.get('oswald')
    if mach:
        args.extend(["--mach", mach])
    if re:
        args.extend(["--re", re])
    if ar:
        args.extend(["--ar", ar])
    if oswald:
        args.extend(["--oswald", oswald])
        
    if script_id == "generate":
        # Handle file upload
        if 'zip_file' in request.files:
            zip_file = request.files['zip_file']
            if zip_file.filename != '':
                filename = secure_filename(zip_file.filename)
                raw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data", "Raw")
                os.makedirs(raw_dir, exist_ok=True)
                save_path = os.path.join(raw_dir, filename)
                zip_file.save(save_path)
                args.extend(["--zip", save_path])
                
    thread = threading.Thread(target=run_script, args=(scripts[script_id], script_id, args))
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": f"Started {script_id}"})

@app.route("/api/stop", methods=["POST"])
def stop_task():
    if state["process_handle"]:
        try:
            state["process_handle"].terminate()
            subprocess.run(["taskkill", "/F", "/IM", "xfoil.exe"], capture_output=True)
            return jsonify({"message": "Process stopped successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"message": "No process running"})

@app.route("/api/dump", methods=["POST"])
def dump_data():
    import glob
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Delete trial CSVs (keep master_dataset)
        csv_dir = os.path.join(base_dir, "Data", "CSVs")
        for f in glob.glob(os.path.join(csv_dir, "trial_*.csv")):
            os.remove(f)
            
        # 2. Delete airfoils
        airfoils_dir = os.path.join(base_dir, "Output", "Airfoils")
        for f in glob.glob(os.path.join(airfoils_dir, "*.dat")):
            os.remove(f)
            
        metrics_file = os.path.join(airfoils_dir, "metrics.json")
        if os.path.exists(metrics_file):
            os.remove(metrics_file)
            
        # 3. Delete ML model
        model_file = os.path.join(base_dir, "Data", "surrogate_model.pkl")
        if os.path.exists(model_file):
            os.remove(model_file)
            
        return jsonify({"message": "Successfully dumped all previous iterations."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Output', 'Images'), filename)

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    metrics_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Output", "Airfoils", "metrics.json")
    if os.path.exists(metrics_path):
        import json
        with open(metrics_path, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Metrics not found"}), 404

if __name__ == "__main__":
    app.run(debug=False, port=5000)
