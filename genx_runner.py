import marimo

__generated_with = "0.14.0"
app = marimo.App(width="columns", app_title="GenX Runner")


@app.cell(column=0, hide_code=True)
def _(mo):
    mo.md(r"""# GenX Runner""")
    return


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import sys
    import xlwings as xw
    import pandas as pd
    import runner
    import itertools
    import json
    from joblib import Parallel, delayed
    import subprocess
    import asyncio

    from upath import UPath

    from loguru import logger
    return asyncio, itertools, logger, mo, pd, runner, xw


@app.cell(hide_code=True)
def _(mo):
    file_browser = mo.ui.file_browser(initial_path=".", filetypes=[".xlsm", ".xlsb"], multiple=False)

    mo.vstack([
        mo.md("## Select a `GenX` inputs Excel workbook"), 
        file_browser,
    ])
    return (file_browser,)


@app.cell
def _(file_browser, logger, xw):
    if file_browser.path(index=0) is not None:
        wb = xw.Book(file_browser.path(index=0))
        logger.success(f"Connected to workbook: {file_browser.path(index=0)}")
    return (wb,)


@app.cell
def _():
    return


@app.cell(column=1, hide_code=True)
def _(mo):
    mo.md(r"""# Setup & Run Capacity Expansion Cases""")
    return


@app.cell(hide_code=True)
def _(itertools, mo):
    params = {
        "IncludePTC": ["BBB", "IRA"],
        "MinCoalNewGas": [0, 7899],
        "HighDSM": [True, False],
    }

    fixed_params = {
        "EnablePCM": False,
        "MaxWind": 10000,
        "EnablePRM": True,
        "BuildRate": 25000,
        "IncludePlannedResources": False,
        "AllowEconomicRetirements": True,
        "CES": 0,
    }


    combinations = mo.ui.table(
        [dict(zip(params.keys(), v)) for v in itertools.product(*params.values())],
        pagination=False
    )

    mo.vstack([
        mo.md("## Select case configurations to run"), 
        combinations,
    ])
    return combinations, fixed_params


@app.cell(hide_code=True)
def _(combinations, mo, pd):
    run_cases = mo.ui.run_button(label="Confirm cases to run")

    mo.vstack([
        mo.md(f"You've selected {len(combinations.value)} cases to run:"),
        pd.DataFrame(combinations.value),
        run_cases,
    ])
    return (run_cases,)


@app.cell(hide_code=True)
async def _(combinations, fixed_params, logger, mo, run_cases, runner, wb):
    folders = []

    if run_cases.value:
        final_cases = [d | fixed_params for d in combinations.value]
        logger.info(f"Setting up {len(final_cases)} cases...")

        for i, combo in mo.status.progress_bar(
            enumerate(final_cases),
            total=len(final_cases),
            title="Saving cases",
            show_rate=False,
        ): 
            folders.append(await runner.update_params_and_save_case(params=combo, wb=wb))
    return (folders,)


@app.cell(hide_code=True)
async def _(asyncio, folders, wb):
    async def run_case(cmd, case_id, semaphore, completed_cases, total_cases):
        """Run a single case and update progress when complete."""
        async with semaphore:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            print(f"[Case {case_id}] Starting...")
        
            # Stream output without progress tracking
            async def stream_output():
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode().strip()
                    print(f"[Case {case_id}] {text}")
        
            await asyncio.gather(stream_output(), proc.wait())
        
            # Update completed count
            completed_cases[0] += 1
            print(f"[Case {case_id}] Finished ({completed_cases[0]}/{total_cases} complete)")
                
            return proc.returncode

    async def run_case_commands(cases, max_parallel=3):
        """Run cases and track completion progress."""
    
        # Use list to make it mutable across async functions
        completed_cases = [0]
    
        semaphore = asyncio.Semaphore(max_parallel)
        tasks = [
            run_case(case, i+1, semaphore, completed_cases, len(cases))
            for i, case in enumerate(cases)
        ]
    
        results = await asyncio.gather(*tasks)
    
        print("✅ All cases complete!")
        return results


    if folders:
        n_jobs = 4
        commands = [f"julia --project=. Run.jl {case_folder}" for case_folder in folders]
        n_planning_periods = wb.sheets["GenX Settings"].range("NumPlanningPeriods").value
    
        results = await run_case_commands(commands, max_parallel=n_jobs)
    return


@app.cell
def _(folders, logger, mo, runner, wb, xw):
    if folders:
        for case_folder in mo.status.progress_bar(folders, title="Loading results metrics"):
            try:
                runner.load_case_results(
                    wb=wb,
                    report_wb=xw.Book("./Compiled Results.xlsm"),
                    base_folder=case_folder,
                    save_view=True,
                )
            except FileNotFoundError:
                logger.error(f"Seems like {case_folder} doesn't have results.")
    return


@app.cell
def _():
  
    return


@app.cell(column=2, hide_code=True)
def _(mo):
    mo.md(r"""# Setup & Run PCM Cases""")
    return


@app.cell(hide_code=True)
def _(mo, solved_cases):
    pcm_select = mo.ui.multiselect(options=solved_cases)

    mo.vstack([
        mo.md("## Select a solved capacity expansion cases to run PCM for"), 
        pcm_select,
    ])
    return


@app.cell(hide_code=True)
def _(pd, wb):
    type_map = wb.sheets["GenX Resources"].range("TypeMap").options(pd.DataFrame, index=0).value.dropna().set_index("resource").squeeze(axis=1).to_dict()

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
    return


@app.cell
def _():
    # if results_select.value:
    #     portfolio_to_load = UPath(results_select.value[0])
    #     runner.load_case_results(wb=wb, report_wb = xw.Book("./Compiled Results.xlsm"), base_folder=portfolio_to_load, save_view=False)

    #     df = pd.read_csv(portfolio_to_load / "pcm" / "results" / "results_p1" / "power.csv").iloc[2:, 1:-1]
    #     df = df.reset_index(drop=True)
    #     df.index = pd.Timestamp("1/1/2007") + pd.to_timedelta(df.index, unit="h")
    #     df = df.T.groupby(type_map).sum().T
    #     df = df[wb.sheets["List"].range("Clusters").options(list).value]
    #     df = df[[col for col in df.columns if df[col].sum()>0]]

    #     import plotly.graph_objects as go

    #     # Hourly
    #     fig = go.Figure(
    #         data=[
    #             go.Scatter(x=df.index, y=df[col], fill="tonexty", fillcolor=color_map[col], stackgroup=1, name=col)
    #             for col in df
    #         ]
    #     )
    #     fig.update_traces(line_width=0)
    #     fig.show()

    #     ## Month-hour
    #     month_hour = df.groupby(by=[df.index.month, df.index.hour]).mean()
    #     month_hour = month_hour.reset_index(names=["month", "hour"])

    #     # blanks = pd.DataFrame(index=[(24 * n) + 0.5 for n in range(1, 12)])
    #     # blanks["month"] = blanks.index // 24
    #     # blanks["hour"] = 24.5

    #     # month_hour = pd.concat([month_hour, blanks], axis=0).sort_index()

    #     mh_fig = go.Figure(
    #         data=[
    #             go.Scatter(x=[month_hour["month"], month_hour["hour"]], y=month_hour[col], fill="tonexty", fillcolor=color_map[col], stackgroup=1, name=col, connectgaps=False)
    #             for col in month_hour if col not in ["month", "hour"]
    #         ]
    #     )
    #     for month in range(1, 12):
    #         mh_fig.add_vrect(x0=i*24 - 1, x1=month*24, line_width=0, fillcolor="white")

    #     mh_fig.update_traces(line_width=0, connectgaps=False)
    #     mh_fig.update_layout(title="<b>IRP Plans</b><br>2033 Month-Hour Average Dispatch")
    #     # mh_fig.update_xaxes(tickson="labels")
    #     mh_fig.show()
    return


if __name__ == "__main__":
    app.run()
