import json
import shutil

import xlwings as xw
import pandas as pd
from collections import defaultdict
import os
from upath import UPath
from loguru import logger
import sys
from datetime import datetime
from hashlib import md5
import asyncio

logger.remove()
logger.add(sys.stderr, backtrace=False)

async def save_case(wb: xw.Book, base_folder: UPath, case_subfolder: str | None = None):
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
        # Use asyncio to run IO operations in non-blocking way
        await asyncio.to_thread(final_df.to_csv, filepath, index=False)

async def save_multistage_case(*, wb: xw.Book):
    base_folder = UPath(wb.names["BaseFolder"].refers_to_range.value)
    case_name = wb.names["CaseName"].refers_to_range.value
    logger.debug(f"Saving case inputs: {case_name}")

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
    periods_df = wb.sheets["GenX Settings"].tables["ModeledYears"].range.options(pd.DataFrame, index=1).value.dropna()
    await asyncio.to_thread(periods_df.to_csv, base_folder / "planning_periods.csv", index=True)

    counter = 1
    for planning_period in planning_periods:
        wb.sheets["GenX Settings"].range("ActiveYear").value = planning_period
        wb.app.calculate()

        logger.debug(f"Saving case inputs for {planning_period}: (inputs_p{counter})")
        await save_case(wb=wb, base_folder=base_folder, case_subfolder=f"inputs/inputs_p{counter}")
        counter += 1

        # Save settings .yml files
        wb.sheets["GenX Settings"].range("settings\\genx_settings.yml").options(pd.DataFrame).value
    # Settings
    logger.debug("Saving settings...")
    base_settings_folder = UPath("/Users/roderick/PycharmProjects/resilient-transition/GenX.jl/__base_settings__")
    if (base_folder / "settings").exists():
        shutil.rmtree(base_folder / "settings")
    await asyncio.to_thread(shutil.copytree, base_settings_folder, base_folder / "settings")

    # TODO: Clean up how these settings files are parsed
    # genx_settings.yml
    genx_settings = wb.sheets["GenX Settings"].range("settings\\genx_settings.yml").options(pd.Series, header=False).value.astype(
        int
    ).reset_index().astype(str).agg("".join, axis=1)
    await asyncio.to_thread(
        genx_settings.to_csv,
        base_folder / "settings" / "genx_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )

    # multi_stage_settings.yml
    multi_stage_settings = wb.sheets["GenX Settings"].range("settings\\multi_stage_settings.yml").options(pd.Series, header=False).value.apply(
        lambda x: int(x) if isinstance(x, (float, bool, int)) else x
    ).reset_index().astype(str).agg("".join, axis=1)
    await asyncio.to_thread(
        multi_stage_settings.to_csv,
        base_folder / "settings" / "multi_stage_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )

    # time_domain_reduction_settings.yml
    tdr_settings = wb.sheets["GenX Settings"].range("settings\\time_domain_reduction_settings.yml").options(
        pd.Series, header=False
    ).value.replace({None: " "}).apply(
        lambda x: int(x) if isinstance(x, (float, bool, int)) else x
    ).reset_index().astype(
        str
    ).agg(
        "".join, axis=1
    ).replace(
        {"None": ""}
    )
    await asyncio.to_thread(
        tdr_settings.to_csv,
        base_folder / "settings" / "time_domain_reduction_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )

    # highs_settings.yml
    highs_settings = wb.sheets["GenX Settings"].range("settings\\highs_settings.yml").options(pd.Series, header=False).value.replace(
        {None: " "}
    ).reset_index().astype(str).agg(
        "".join, axis=1
    ).replace(
        {"None": ""}
    )
    await asyncio.to_thread(
        highs_settings.to_csv,
        base_folder / "settings" / "highs_settings.yml",
        index=False,
        header=False,
        sep="\t",
    )

    logger.success(f"Saved multi-stage capacity expansion case: {case_name}")

    return base_folder

def load_case_results(*, wb: xw.Book, report_wb: xw.Book, base_folder: UPath, save_view: bool = True):
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

    # Load case configs (because the case configs affect tax credit calculations that flow through to results)
    if (base_folder / "settings" / "case_configs.json").exists():
        with open(base_folder / "settings" / "case_configs.json", "r") as f:
            params = json.load(f)
        for param, value in params.items():
            wb.sheets["GenX Settings"].range(param).value = value

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

    # Generation
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
        wb.sheets["GenX Results"].copy(after=report_wb.sheets[0])
        new_name = md5(str(base_folder).encode("ascii")).hexdigest()[:10]
        report_wb.sheets["GenX Results"].name = new_name

        # Save values only (break external links)
        report_wb.sheets[new_name].range("A1:FU250").copy()
        report_wb.sheets[new_name].range("A1:FU250").paste("values")

    print(f"Loaded results at: {datetime.now()}")


async def update_params_and_save_case(*, params: tuple, wb: xw.Book):
    logger.debug(f"Updating params: {params}")

    for param, value in params.items():
        wb.sheets["GenX Settings"].range(param).value = value

    base_folder = await save_multistage_case(wb=wb)

    with open(base_folder / "settings" / "case_configs.json", "w") as f:
        json.dump(params, f)

    return base_folder


async def run_and_load_case(*, wb: xw.Book, report_wb: xw.Book = None):
    import subprocess

    base_folder = await save_multistage_case(wb=wb)
    # Run subprocess in a non-blocking way using asyncio
    proc = await asyncio.create_subprocess_exec(
        "julia", "--project=.", "Run.jl", str(base_folder),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if stderr:
        logger.error(f"Julia process stderr: {stderr.decode()}")

    if report_wb is None:
        report_wb = wb

    load_case_results(wb=wb, report_wb=report_wb, base_folder=base_folder)

    return base_folder


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
