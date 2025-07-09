import json
import shutil
import subprocess
import shlex

import xlwings as xw
import pandas as pd
from collections import defaultdict
import os
from upath import UPath
from loguru import logger
import sys
from datetime import datetime
from joblib import Parallel, delayed
from multiprocessing import Manager
import concurrent.futures
import threading
import time

logger.remove()
logger.add(sys.stderr, backtrace=False)

def get_solved_cases(folder: UPath):
    """Get folders with results."""
    return sorted(p for p in folder.rglob("*") if p.is_dir() and (p / "results" / "capacities_multi_stage.csv").exists())

def save_case(wb: xw.Book, base_folder: UPath, case_subfolder: str | None = None):
    # Get CSV names as a nested dictionary (since some CSVs have been split into multiple separate tables
    # Named ranges have the format of [csv file name]...[#]...[optional transformation, either .T or .ffill]
    csv_names = defaultdict(list)
    for name in wb.names:
        if ".csv" in name.name:
            csv_names[name.name.split("...")[0]].append(name)
    for csv_name, ranges in csv_names.items():
        dfs = []
        for rng in ranges:
            # Get each range as a dataframe
            df = rng.refers_to_range.options(
                pd.DataFrame,
                index=0,
                header=(1 if not rng.name.endswith("...T") else 0),
            ).value
            df = df.dropna(how="all", axis=1)
            df = df.dropna(how="all", axis=0)
            if "resource" in df.columns:
                df = df.dropna(subset="resource", axis=0)
            if "drop" in df.columns:
                df = df[df["drop"] != True]

            # Apply optional transform
            if rng.name.endswith("...T"):
                df = df.set_index(df.columns[0])
                df = df.T
            elif rng.name.endswith("...ffill"):
                df = df.ffill()
            # TODO: This could be more flexible, but for now hard-coded...
            elif rng.name.endswith("...drop...1"):
                df = df.iloc[:, [0, -1]]
                df = df.dropna(how="any")
            elif rng.name.endswith("...drop...2"):
                df = df.iloc[:, [0, -2, -1]]
                df = df.dropna(how="any")
            elif rng.name.endswith("...drop...3"):
                df = df.iloc[:, [0, -3, -2, -1]]
                df = df.dropna(how="any")
            elif rng.name.endswith("...drop...4"):
                df = df.iloc[:, [0, -4, -3, -2, -1]]
                df = df.dropna(how="any")

            if csv_name in [
                "resources\\policy_assignments\\Resource_NQC_derate.csv",
                "resources\\policy_assignments\\ELCC_multipliers.csv",
                "resources\\Resource_multistage_data.csv",
            ]:
                df = df.rename(columns={"resource": "Resource"})

            # Change types for columns to int & strings
            int_columns = [
                col for col in df.columns if col in ["can_retire", "zone", "new_build", "model", "lds", "Time_Index"]
            ]
            df[int_columns] = df[int_columns].astype(int)

            str_columns = [
                col
                for col in df.columns
                if col
                in [
                    "cluster",
                    "region",
                ]
            ]
            df[str_columns] = df[str_columns].astype(str)

            if df.isna().any().any():
                logger.error(
                    f"{csv_name} has blank cells. GenX currently does not have consistent handling of missing data, so please fill in or add placeholder values."
                )

            dfs.append(df)

        # Join all the dfs
        final_df = pd.concat([df.reset_index(drop=True) for df in dfs], axis=1)

        # Save joined dataframe to CSV
        planning_period_folder = base_folder / case_subfolder if case_subfolder else base_folder
        filepath = planning_period_folder / csv_name.replace("\\", os.sep)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        final_df.to_csv(filepath, index=False)

def save_multistage_case(*, wb: xw.Book):
    base_folder = UPath(wb.names["BaseFolder"].refers_to_range.value)
    case_name = wb.names["CaseName"].refers_to_range.value
    logger.info(f"Saving case inputs: {case_name}")

    if base_folder.exists():
        logger.warning(f"Overwriting case inputs folder: {base_folder}")
        # TODO: Should I delete TDR results each time when overwriting?
    base_folder.mkdir(parents=True, exist_ok=True)
    # Save mapping of planning periods to period IDs
    planning_periods = (
        wb.sheets["GenX Settings"]
        .tables["ModeledYears"]
        .range.options(pd.DataFrame, index=1)
        .value.dropna()
        .index.astype(int)
        .values
    )
    # Save mapping of planning periods so that we know what years to map inputs_p1, etc. to
    wb.sheets["GenX Settings"].tables["ModeledYears"].range.options(pd.DataFrame, index=1).value.dropna().to_csv(
        base_folder / "planning_periods.csv", index=True
    )
    counter = 1
    for planning_period in planning_periods:
        wb.sheets["GenX Settings"].range("ActiveYear").value = planning_period
        wb.app.calculate()

        logger.info(f"Saving case inputs for {planning_period}: (inputs_p{counter})")
        save_case(wb=wb, base_folder=base_folder, case_subfolder=f"inputs/inputs_p{counter}")
        counter += 1

        # Save settings .yml files
        wb.sheets["GenX Settings"].range("settings\\genx_settings.yml").options(pd.DataFrame).value
    # Settings
    logger.info("Saving settings...")
    base_settings_folder = UPath(__file__).parents[1] / "__base_settings__"
    if (base_folder / "settings").exists():
        shutil.rmtree(base_folder / "settings")
    shutil.copytree(base_settings_folder, base_folder / "settings")
    # TODO: Clean up how these settings files are parsed
    # genx_settings.yml
    wb.sheets["GenX Settings"].range("settings\\genx_settings.yml").options(pd.Series, header=False).value.astype(
        int
    ).reset_index().astype(str).agg("".join, axis=1).to_csv(
        base_folder / "settings" / "genx_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )
    # multi_stage_settings.yml
    wb.sheets["GenX Settings"].range("settings\\multi_stage_settings.yml").options(pd.Series, header=False).value.apply(
        lambda x: int(x) if isinstance(x, (float, bool, int)) else x
    ).reset_index().astype(str).agg("".join, axis=1).to_csv(
        base_folder / "settings" / "multi_stage_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )
    # time_domain_reduction_settings.yml
    wb.sheets["GenX Settings"].range("settings\\time_domain_reduction_settings.yml").options(
        pd.Series, header=False
    ).value.replace({None: " "}).apply(
        lambda x: int(x) if isinstance(x, (float, bool, int)) else x
    ).reset_index().astype(
        str
    ).agg(
        "".join, axis=1
    ).replace(
        {"None": ""}
    ).to_csv(
        base_folder / "settings" / "time_domain_reduction_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )
    # highs_settings.yml
    wb.sheets["GenX Settings"].range("settings\\highs_settings.yml").options(pd.Series, header=False).value.replace(
        {None: " "}
    ).reset_index().astype(str).agg(
        "".join, axis=1
    ).replace(
        {"None": ""}
    ).to_csv(
        base_folder / "settings" / "highs_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )
    logger.success(f"Saved multi-stage capacity expansion case: {case_name}")

    return base_folder

def load_case_results(*, wb: xw.Book, base_folder: UPath, save_view: bool = True, report_wb_template_path: os.PathLike | None = None):
    if (base_folder / "planning_periods.csv").exists():
        periods_range = (
            pd.read_csv(base_folder / "planning_periods.csv", index_col=-1)["Planning Period"].astype("int").to_dict()
        )
        periods_range = {base_folder / "results" / f"results_{k}": v for k, v in periods_range.items()}
    else:
        subfolders = sorted(
            list((base_folder / "results").glob("results_p*")),
            key=lambda path: int(path.stem.split("results_p")[-1]),
        )
        periods_range = {p: None for p in subfolders}

    # Case name
    wb.sheets["GenX Results"].range("ResultsName").value = base_folder.stem

    # Total capacity
    portfolio = pd.read_csv(base_folder / "results" / "capacities_multi_stage.csv", index_col=0)
    portfolio = portfolio[[col for col in portfolio.columns if not col.startswith("StartCap")]]
    portfolio = portfolio.rename(
        columns={"EndCap_p" + path.stem.split("results_p")[-1]: period for path, period in periods_range.items()}
    )
    portfolio = portfolio.drop(["Zone"], axis=1)
    wb.sheets["GenX Results"].range("capacities_multi_stage").clear_contents()
    wb.sheets["GenX Results"].range("capacities_multi_stage").value = portfolio.round(3)

    # Costs
    costs = (pd.read_csv(base_folder / "results" / "costs_multi_stage.csv", index_col=0) / 1e6).round(3)
    costs = costs.rename(
        columns={"TotalCosts_p" + path.stem.split("results_p")[-1]: period for path, period in periods_range.items()}
    )
    wb.sheets["GenX Results"].range("costs_multi_stage").clear_contents()
    wb.sheets["GenX Results"].range("costs_multi_stage").value = costs

    # Builds
    def get_net_build(path):
        df = pd.read_csv(path / "capacity.csv", index_col=0)[["NewCap", "RetCap"]]
        return df["NewCap"] - df["RetCap"]

    builds = pd.concat({period: get_net_build(path) for path, period in periods_range.items()}, axis=1).round(3)
    wb.sheets["GenX Results"].range("capacities").clear_contents()
    wb.sheets["GenX Results"].range("capacities").value = builds

    # CFs
    cfs = pd.concat(
        {
            period: pd.read_csv(path / "capacityfactor.csv", index_col=0)["CapacityFactor"]
            for path, period in periods_range.items()
        },
        axis=1,
    ).round(3)
    wb.sheets["GenX Results"].range("cfs").clear_contents()
    wb.sheets["GenX Results"].range("cfs").value = cfs

    # Generation
    generation = (
        pd.concat(
            {period: pd.read_csv(path / "power.csv", index_col=0).T["AnnualSum"] for path, period in periods_range.items()},
            axis=1,
        )
        / 1e6
    ).round(3)
    wb.sheets["GenX Results"].range("generation").clear_contents()
    wb.sheets["GenX Results"].range("generation").value = generation

    # Emissions
    emissions = (
        pd.concat(
            {period: pd.read_csv(path / "emissions_plant.csv", index_col=0).T["AnnualSum"] for path, period in periods_range.items()},
            axis=1,
        )
        / 1e6
    ).round(3)
    wb.sheets["GenX Results"].range("emissions").clear_contents()
    wb.sheets["GenX Results"].range("emissions").value = emissions


    wb.sheets["GenX Results"].activate()
    wb.app.calculate()

    # Save copy of sheet
    if save_view:
        assert report_wb_template_path is not None, "`report_wb_template_path` must be provided to save results view"

        report_wb = xw.Book(report_wb_template_path)
        wb.sheets["GenX Results"].copy(after=report_wb.sheets[0])
        new_name = base_folder.stem[:31]  # Use the case name as the sheet name, limited to 32 characters
        report_wb.sheets["GenX Results"].name = new_name

        # Save values only (break external links)
        report_wb.sheets[new_name].range("A1:FU250").copy()
        report_wb.sheets[new_name].range("A1:FU250").paste("values")

        return report_wb

    print(f"Loaded results at: {datetime.now()}")


def update_params_and_save_case(*, params: tuple, wb: xw.Book):
    logger.debug(f"Updating params: {params}")

    for param, value in params.items():
        wb.sheets["GenX Settings"].range(param).value = value

    wb.app.calculate()
    base_folder = save_multistage_case(wb=wb)

    with open(base_folder / "settings" / "case_configs.json", "w") as f:
        json.dump(params, f)

    return base_folder


def run_case(cmd, case_folder, show_output=False):
    """Run a single case and return progress information.
    
    Args:
        cmd: Command to execute
        case_folder: Path to the case folder
        show_output: Whether to print detailed output (useful for debugging)
    """
    # Convert to string to avoid pickling issues with UPath
    case_name = UPath(case_folder).stem
    
    if show_output:
        print(f"Starting... [{case_name}]")
    
    try:
        # Run the command and capture output
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=None  # Use current working directory
        )

        if show_output:
            # Print output for debugging
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    print(f"{line} [{case_name}]")
        
        if show_output:
            status = "✅" if proc.returncode == 0 else "❌"
            print(f"{status} Finished with return code {proc.returncode} [{case_name}]")

        return proc.returncode, case_folder
        
    except Exception as e:
        if show_output:
            print(f"❌ Exception: {e} [{case_name}]")
        return -1, case_folder

def _run_case_wrapper(args):
    """Wrapper function for joblib that handles the case execution."""
    cmd, case_folder, show_case_output, real_time_progress, completed_cases = args
    returncode, returned_case_folder = run_case(cmd, case_folder, show_output=show_case_output)
    
    if real_time_progress:
        # Add to completed list for real-time progress tracking
        case_name = UPath(returned_case_folder).stem
        completed_cases.append((case_name, returncode))
    
    return returncode, returned_case_folder

def run_case_commands(case_folders, max_parallel=3, progress_mode="normal"):
    """Run GenX cases and track completion progress.
    
    Args:
        case_folders: List of case folder paths to run
        max_parallel: Maximum number of parallel jobs
        progress_mode: Progress reporting mode
            - "silent": No progress output
            - "normal": Show batch progress at end (default)
            - "realtime": Show real-time progress updates
            - "debug": Show real-time progress + detailed case output
    """
    # Convert UPath objects to strings to avoid pickling issues
    case_folders_str = [str(folder) for folder in case_folders]
    
    # Build Julia commands from case folders - properly quote paths with spaces
    commands = [f"julia --project=. Run.jl {shlex.quote(case_folder)}" for case_folder in case_folders_str]

    # Determine behavior based on progress mode
    verbose = progress_mode != "silent"
    show_case_output = progress_mode == "debug"
    real_time_progress = progress_mode in ["realtime", "debug"]

    if verbose:
        print(f"Running {len(case_folders)} cases with max {max_parallel} parallel jobs...")
    
    # Track completion - use Manager for multiprocessing-safe list
    if real_time_progress:
        manager = Manager()
        completed_cases = manager.list()
    else:
        completed_cases = []
    
    total_cases = len(case_folders)
    
    # Start real-time progress monitoring if requested
    progress_thread = None
    if real_time_progress and verbose:
        def progress_monitor():
            reported_count = 0
            while reported_count < total_cases:
                current_count = len(completed_cases)
                if current_count > reported_count:
                    for i in range(reported_count, current_count):
                        case_name, returncode = completed_cases[i]
                        status = "✅" if returncode == 0 else "❌"
                        print(f"{status} {case_name} finished ({i+1}/{total_cases} complete)")
                    reported_count = current_count
                time.sleep(0.1)
        
        progress_thread = threading.Thread(target=progress_monitor, daemon=True)
        progress_thread.start()
    
    # Prepare arguments for parallel execution
    job_args = [
        (cmd, case_folder, show_case_output, real_time_progress, completed_cases)
        for cmd, case_folder in zip(commands, case_folders_str)
    ]
    
    # Run cases in parallel using joblib
    job_results = Parallel(n_jobs=max_parallel, backend='multiprocessing', verbose=0)(
        delayed(_run_case_wrapper)(args) for args in job_args
    )
    
    # Wait for progress thread to finish if it was started
    if progress_thread:
        progress_thread.join(timeout=2)
    
    # Process final results
    results = {}
    for returncode, case_folder in job_results:
        case_name = UPath(case_folder).stem
        results[case_folder] = returncode
        
        # For non-real-time mode, show results at the end
        if verbose and not real_time_progress:
            status = "✅" if returncode == 0 else "❌"
            print(f"{status} {case_name} finished with return code {returncode}")

    if verbose:
        success_count = sum(1 for code in results.values() if code == 0)
        print(f"✅ All cases complete! ({success_count}/{len(results)} successful)")
    
    return results

## Visualization stuff

import plotly.graph_objects as go
import plotly.io as pio

axes = dict(
    showgrid=False,
    linecolor="rgb(120, 120, 120)",
    linewidth=1,
    showline=True,
    ticks="outside",
    tickcolor="rgb(120, 120, 120)",
    mirror=True,
)

pio.templates["core"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family="CommitMono", size=11, color="rgb(120, 120, 120)"),
        title=dict(
            font=dict(
                # size=32,
                color="rgb(3, 78, 110)",
            ),
            x=0.06,
            y=0.92,
            xanchor="left",
            yanchor="bottom",
        ),
        xaxis=axes,
        yaxis=axes,
        margin=dict(t=60, b=100, r=60, l=60),
    )
)

pio.templates["2.5x7.5"] = go.layout.Template(
    layout=go.Layout(
        height=2.5 * 144,
        width=7.5 * 144,
    )
)

pio.templates.default = "core+2.5x7.5"

color_map = {
    "Coal": "black",
    "Gas Other": "#434343",
    "Gas CCGT": "#7F7F7F",
    "Gas CT": "#BFBFBF",
    "Nuclear": "#FF8AD8",
    "Biogas": "#7F4910",
    "Hydro": "#0070C0",
    "Wind": "#76F2FF",
    "Solar": "#FFC000",
    "4-hr Battery": "#7030A0",
    "8-hr Battery": "#7030A0",
    "100-hr Battery": "#002060",
    "Capacity Purchase": "#C00000",
}

pattern_shape_map = {
    "Coal": "",
    "Gas Other": "",
    "Gas CCGT": "",
    "Gas CT": "",
    "Nuclear": "",
    "Biogas": "",
    "Hydro": "",
    "Wind": "",
    "Solar": "",
    "4-hr Battery": "",
    "8-hr Battery": "",
    "100-hr Battery": "/",
    "Capacity Purchase": "/",
}

# Multiprocessing guard for Windows compatibility
if __name__ == "__main__":
    pass

def run_case_with_logging(cmd, case_folder):
    """Run case and write output to log file in the case folder
    
    Note: This function clears any existing log file before writing new content.
    """
    case_folder_path = UPath(case_folder)
    case_name = case_folder_path.stem
    log_file = case_folder_path / f"{case_name}.log"
    
    # Ensure the case folder exists
    case_folder_path.mkdir(parents=True, exist_ok=True)
    
    # Open with 'w' mode to clear/truncate any existing log file
    with open(log_file, 'w') as f:
        f.write(f"=== Starting {case_name} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.flush()
        
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True,
            bufsize=1
        )
        
        # Stream output to log file
        for line in iter(proc.stdout.readline, ''):
            f.write(line)
            f.flush()  # Ensure immediate write
        
        proc.wait()
        f.write(f"\n=== Finished {case_name} with return code {proc.returncode} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.flush()
        
    return proc.returncode, case_folder, str(log_file)


def tail_logs(case_folders, stop_event, n_lines=10):
    """Tail all log files and print to notebook
    
    Args:
        case_folders: List of case folder paths
        stop_event: Threading event to stop tailing
        n_lines: Number of lines to keep in output (default: 10)
    """
    log_positions = {}
    log_file_sizes = {}
    log_lines_cache = {}
    
    # Initialize log positions, file sizes, and line caches
    for folder in case_folders:
        case_name = UPath(folder).stem
        log_positions[case_name] = 0
        log_file_sizes[case_name] = 0
        log_lines_cache[case_name] = []
    
    while not stop_event.is_set():
        # Clear the output and print current lines for all cases
        from IPython.display import clear_output
        clear_output(wait=True)
        
        # Collect and display lines from all cases
        all_lines = []
        
        for folder in case_folders:
            case_folder_path = UPath(folder)
            case_name = case_folder_path.stem
            log_file = case_folder_path / f"{case_name}.log"
            
            if log_file.exists():
                try:
                    current_size = log_file.stat().st_size
                    
                    # Check if file was truncated/cleared (size smaller than last position)
                    if current_size < log_positions[case_name]:
                        log_positions[case_name] = 0
                        log_file_sizes[case_name] = 0
                        log_lines_cache[case_name] = []
                    
                    with open(log_file, 'r') as f:
                        f.seek(log_positions[case_name])
                        new_lines = f.readlines()
                        if new_lines:
                            for line in new_lines:
                                # Skip timestamp headers/footers to avoid duplication
                                stripped = line.rstrip()
                                if not (stripped.startswith("=== Starting") or 
                                       stripped.startswith("=== Finished") or
                                       stripped.startswith("ERROR:")):
                                    if stripped:  # Only add non-empty lines
                                        log_lines_cache[case_name].append(stripped)
                        
                        # Keep only the last n_lines
                        if len(log_lines_cache[case_name]) > n_lines:
                            log_lines_cache[case_name] = log_lines_cache[case_name][-n_lines:]
                        
                        log_positions[case_name] = f.tell()
                        log_file_sizes[case_name] = current_size
                except (IOError, OSError):
                    # Log file might be temporarily locked, skip this iteration
                    pass
            
            # Add this case's lines to the display with case header
            if log_lines_cache[case_name]:  # Only add case header if there are lines
                if all_lines:  # Add empty line before this case if there are already lines from other cases
                    all_lines.append("")
                # Create a fixed-width header line (80 characters total)
                header_text = f"━━━ Case: {case_name} ━━━"
                remaining_chars = max(0, 80 - len(header_text))
                header_line = header_text + "━" * remaining_chars
                all_lines.append(header_line)
                all_lines.extend(log_lines_cache[case_name])
        
        # Print all lines (this will be the only output after clear_output)
        for line in all_lines:
            print(line)

        time.sleep(2)  # Check for new output every 2 seconds

def run_cases_with_streaming_logs(case_folders, max_parallel=4, n_lines=10):
    """Run cases with file logging and real-time output streaming
    
    Args:
        case_folders: List of case folder paths to run
        max_parallel: Maximum number of parallel jobs (default: 4)
        n_lines: Number of lines to keep in output display (default: 10)
    """
    
    print(f"Starting {len(case_folders)} cases with {max_parallel} workers...")
    print(f"Log files will be written to each case folder")
    
    # Start log tailing thread
    stop_event = threading.Event()
    tail_thread = threading.Thread(target=tail_logs, args=(case_folders, stop_event, n_lines))
    tail_thread.start()
    
    start_time = time.time()
    
    # Run jobs in parallel
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_parallel) as executor:
        # Prepare commands with proper escaping
        commands = ["julia --project=. Run.jl " + "\"" + f"{str(folder)}" + "\"" for folder in case_folders]
        
        # Submit all jobs
        futures = [
            executor.submit(run_case_with_logging, cmd, str(folder))
            for cmd, folder in zip(commands, case_folders)
        ]
        
        # Collect results as they complete
        results = {}
        completed = 0
        total = len(case_folders)
        
        for future in concurrent.futures.as_completed(futures):
            returncode, case_folder, log_file = future.result()
            case_name = UPath(case_folder).stem
            completed += 1
            elapsed = time.time() - start_time
            
            print(f"   Log saved to: {log_file}")
            print(f"   Progress: {completed}/{total} complete, {elapsed:.1f}s elapsed\n")
            
            results[case_folder] = returncode
    
    # Stop log tailing
    stop_event.set()
    tail_thread.join(timeout=2)
    
    total_time = time.time() - start_time
    success_count = sum(1 for code in results.values() if code == 0)
    
    print(f"All cases completed in {total_time:.1f}s!")
    
    return results
