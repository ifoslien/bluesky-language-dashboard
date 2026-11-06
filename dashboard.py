"""Dash app for exploring the Bluesky language samples.

Run it with
    python dashboard.py
and open http://127.0.0.1:8050 in a browser.

By default it reads the CSV files in the current folder. To read the live
files from GitHub instead, set DATA_BASE_URL before starting the app, for example
    export DATA_BASE_URL=https://raw.githubusercontent.com/USERNAME/bluesky-language-dashboard/main/
The app reloads the data every 15 minutes, so a deployed copy stays current.
"""

import os

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html
from dash.dash_table.Format import Format

from analysis import LANGUAGES

DATA_BASE_URL = os.environ.get("DATA_BASE_URL", "")
REFRESH_MINUTES = 15

LANGUAGE_NAMES = {
    "en": "English", "ja": "Japanese", "pt": "Portuguese", "de": "German",
    "es": "Spanish", "fr": "French", "ru": "Russian", "ko": "Korean",
    "uk": "Ukrainian", "it": "Italian", "nl": "Dutch", "pl": "Polish",
    "tr": "Turkish", "sv": "Swedish", "fi": "Finnish", "ca": "Catalan",
    "id": "Indonesian", "zh": "Chinese", "ar": "Arabic", "fa": "Persian",
    "th": "Thai", "ne": "Nepali", "hi": "Hindi", "he": "Hebrew", "el": "Greek",
    "vi": "Vietnamese", "da": "Danish", "no": "Norwegian", "nb": "Norwegian",
    "cs": "Czech", "hu": "Hungarian", "ro": "Romanian", "eu": "Basque",
    "gl": "Galician", "tl": "Tagalog", "ms": "Malay", "bn": "Bengali",
    "ta": "Tamil", "eo": "Esperanto", "la": "Latin", "cy": "Welsh",
    "ga": "Irish", "is": "Icelandic", "et": "Estonian", "lt": "Lithuanian",
    "lv": "Latvian", "sk": "Slovak", "sl": "Slovenian", "hr": "Croatian",
    "sr": "Serbian", "bg": "Bulgarian", "be": "Belarusian", "kk": "Kazakh",
    "none": "No tag", "other": "Other", "und": "Undetermined",
}

# Codes the detector can recognize. Tags outside this set can never match,
# so they are left out of the match rate chart.
DETECTABLE_CODES = {lang.iso_code_639_1.name.lower() for lang in LANGUAGES}

# Each language keeps the same color in every chart and under every filter.
# Languages past the eighth slot share the gray used for Other.
SERIES_COLORS = {
    "en": "#2a78d6", "ja": "#eb6834", "pt": "#1baf7a", "de": "#eda100",
    "es": "#e87ba4", "fr": "#008300", "ru": "#6250d6", "ko": "#e34948",
}
OTHER_COLOR = "#9a9993"
NO_TAG_COLOR = "#52514e"

# No tag and Other are not languages, so they are drawn as dashed and dotted
# lines in neutral grays instead of taking a language color
LINE_DASH = {"none": "dash", "other": "dot"}

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e6e5e1"
SURFACE = "#fcfcfb"
BLUE_RAMP = ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def name(code):
    return LANGUAGE_NAMES.get(code, code)


def color(code):
    if code == "none":
        return NO_TAG_COLOR
    return SERIES_COLORS.get(code, OTHER_COLOR)


def load_data():
    """Read the two CSV files and parse the run times."""
    summary = pd.read_csv(DATA_BASE_URL + "language_summary.csv")
    pairs = pd.read_csv(DATA_BASE_URL + "language_pairs.csv")
    for df in (summary, pairs):
        df["run_time"] = pd.to_datetime(df["run_time"], utc=True)
    return summary, pairs


def filter_window(df, window):
    """Keep only rows inside the chosen time window."""
    if window == "all" or df.empty:
        return df
    hours = {"24h": 24, "7d": 24 * 7}[window]
    cutoff = df["run_time"].max() - pd.Timedelta(hours=hours)
    return df[df["run_time"] > cutoff]


def base_layout(fig, title, height=360):
    """Shared chart styling with recessive axes and a light grid."""
    fig.update_layout(
        title={"text": title, "x": 0, "font": {"size": 16, "color": TEXT_PRIMARY}},
        height=height,
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font={"family": FONT, "color": TEXT_SECONDARY, "size": 12},
        hoverlabel={"bgcolor": "white", "font": {"family": FONT, "color": TEXT_PRIMARY}},
        legend={"orientation": "h", "y": -0.15, "x": 0},
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, ticks="")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def stat_tile(label, value, note=""):
    return html.Div(
        [
            html.Div(label, style={"fontSize": 13, "color": TEXT_SECONDARY}),
            html.Div(value, style={"fontSize": 30, "fontWeight": 600, "color": TEXT_PRIMARY}),
            html.Div(note, style={"fontSize": 12, "color": TEXT_SECONDARY}),
        ],
        style={"flex": 1, "padding": "16px", "background": "white",
               "border": f"1px solid {GRID}", "borderRadius": 8},
    )


def share_chart(summary, languages):
    """Line chart of each language's share of posts per sample."""
    fig = go.Figure()
    for code in languages:
        rows = summary[summary["declared"] == code].sort_values("run_time")
        fig.add_trace(go.Scatter(
            x=rows["run_time"], y=rows["share"], name=name(code), mode="lines",
            line={"color": color(code), "width": 2, "dash": LINE_DASH.get(code, "solid")},
            hovertemplate=f"{name(code)} %{{y:.1%}}<extra></extra>",
        ))
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_layout(hovermode="x unified")
    return base_layout(fig, "Share of posts by declared language (UTC)")


def match_chart(summary):
    """Bar chart of how often the declared tag matches the detected language."""
    tagged = summary[summary["declared"].isin(DETECTABLE_CODES)].copy()
    tagged = tagged[tagged["detectable"] > 0]
    tagged["matched"] = tagged["match_rate"] * tagged["detectable"]
    pooled = tagged.groupby("declared")[["matched", "detectable"]].sum()
    pooled["rate"] = pooled["matched"] / pooled["detectable"]
    pooled = pooled.sort_values("rate")

    fig = go.Figure(go.Bar(
        x=pooled["rate"], y=[name(c) for c in pooled.index], orientation="h",
        marker={"color": "#2a78d6", "cornerradius": 4},
        text=[f"{r:.0%}" for r in pooled["rate"]], textposition="outside",
        textfont={"color": TEXT_PRIMARY},
        customdata=pooled["detectable"],
        hovertemplate="%{y}<br>%{x:.1%} of %{customdata:,} detectable posts<extra></extra>",
    ))
    fig.update_xaxes(tickformat=".0%", range=[0, 1.1], gridcolor=GRID, showgrid=True)
    fig.update_yaxes(showgrid=False)
    return base_layout(fig, "How often the language tag matches the detected language")


def confusion_chart(pairs, top_n=8):
    """Heatmap of declared language against detected language, as row percentages."""
    totals = pairs.groupby("declared")["count"].sum()
    top_declared = [c for c in totals.sort_values(ascending=False).index if c != "other"][:top_n]
    table = (pairs[pairs["declared"].isin(top_declared)]
             .groupby(["declared", "detected"])["count"].sum().unstack(fill_value=0))
    detected_totals = table.sum().sort_values(ascending=False)
    columns = list(detected_totals.index[:top_n + 2])
    table = table[columns].loc[top_declared[::-1]]
    shares = table.div(totals[table.index], axis=0)

    fig = go.Figure(go.Heatmap(
        z=shares.values, x=[name(c) for c in columns], y=[name(c) for c in shares.index],
        colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
        zmin=0, zmax=1, xgap=2, ygap=2,
        colorbar={"tickformat": ".0%", "thickness": 10, "outlinewidth": 0},
        hovertemplate="Tagged %{y}, detected %{x}<br>%{z:.1%} of posts<extra></extra>",
    ))
    fig.update_xaxes(title="Detected language", side="bottom")
    fig.update_yaxes(title="Declared tag", gridcolor=SURFACE)
    return base_layout(fig, "What each tag's posts are actually written in", height=420)


def focus_chart(pairs, focus):
    """Bar chart of where posts tagged with one language end up."""
    rows = pairs[pairs["declared"] == focus].groupby("detected")["count"].sum()
    rows = (rows / rows.sum()).sort_values(ascending=True).tail(8)
    fig = go.Figure(go.Bar(
        x=rows.values, y=[name(c) for c in rows.index], orientation="h",
        marker={"color": color(focus) if focus in SERIES_COLORS else "#2a78d6",
                "cornerradius": 4},
        text=[f"{v:.0%}" for v in rows.values], textposition="outside",
        textfont={"color": TEXT_PRIMARY},
        hovertemplate="Detected %{y}<br>%{x:.1%}<extra></extra>",
    ))
    fig.update_xaxes(tickformat=".0%", range=[0, max(rows.max() * 1.2, 0.1)])
    return base_layout(fig, f"Posts tagged {name(focus)}, by detected language", height=320)


def accuracy_over_time_chart(pairs, focus):
    """Line chart of what happens to one tag's posts in each sample.

    Every post tagged with the focus language either matches the detected
    language, is detected as a different language, or is too short to detect,
    so the three lines add up to 100% at each point.
    """
    rows = pairs[pairs["declared"] == focus].copy()
    rows["outcome"] = "Different language"
    rows.loc[rows["detected"] == focus, "outcome"] = "Matches tag"
    rows.loc[rows["detected"] == "und", "outcome"] = "Too short to detect"
    table = rows.groupby(["run_time", "outcome"])["count"].sum().unstack(fill_value=0)
    shares = table.div(table.sum(axis=1), axis=0).sort_index()

    outcome_styles = {
        "Matches tag": {"color": "#2a78d6", "dash": "solid"},
        "Different language": {"color": "#eb6834", "dash": "solid"},
        "Too short to detect": {"color": OTHER_COLOR, "dash": "dot"},
    }
    fig = go.Figure()
    for outcome, style in outcome_styles.items():
        if outcome not in shares:
            continue
        fig.add_trace(go.Scatter(
            x=shares.index, y=shares[outcome], name=outcome,
            mode="lines+markers", marker={"size": 8},
            line={"color": style["color"], "width": 2, "dash": style["dash"]},
            hovertemplate=f"{outcome} %{{y:.1%}}<extra></extra>",
        ))
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
    fig.update_layout(hovermode="x unified")
    return base_layout(fig, f"Posts tagged {name(focus)} over time", height=320)


def stats_table(summary):
    """Per-language text statistics averaged across samples, weighted by post count."""
    metrics = ["mean_chars", "mean_tokens", "type_token_ratio",
               "emoji_per_post", "url_rate", "mixed_script_rate", "multi_tag_rate"]
    weighted = summary[metrics].multiply(summary["posts"], axis=0)
    weighted["declared"] = summary["declared"]
    weighted["posts"] = summary["posts"]
    grouped = weighted.groupby("declared").sum()
    result = grouped[metrics].div(grouped["posts"], axis=0)
    result["posts"] = grouped["posts"]
    result = result.sort_values("posts", ascending=False).reset_index()
    result["declared"] = result["declared"].map(name)

    for col in ["mean_chars", "mean_tokens"]:
        result[col] = result[col].round(1)
    result["type_token_ratio"] = result["type_token_ratio"].round(3)
    result["emoji_per_post"] = result["emoji_per_post"].round(2)
    for col in ["url_rate", "mixed_script_rate", "multi_tag_rate"]:
        result[col] = (result[col] * 100).round(1)

    columns = [
        ("declared", "Language"), ("posts", "Posts"), ("mean_chars", "Avg characters"),
        ("mean_tokens", "Avg words"), ("type_token_ratio", "Type-token ratio"),
        ("emoji_per_post", "Emoji per post"), ("url_rate", "Links %"),
        ("mixed_script_rate", "Mixed script %"), ("multi_tag_rate", "Multiple tags %"),
    ]
    return dash_table.DataTable(
        data=result.to_dict("records"),
        columns=[{"id": c, "name": n, "type": "numeric", "format": Format().group(True)}
                 if c == "posts" else {"id": c, "name": n} for c, n in columns],
        sort_action="native",
        style_as_list_view=True,
        style_header={"fontWeight": 600, "backgroundColor": SURFACE, "color": TEXT_PRIMARY},
        style_cell={"fontFamily": FONT, "fontSize": 13, "padding": "8px",
                    "color": TEXT_PRIMARY, "backgroundColor": "white", "textAlign": "right"},
        style_cell_conditional=[{"if": {"column_id": "declared"}, "textAlign": "left"}],
    )


app = Dash(__name__, title="Bluesky Language Dashboard")

card = {"background": "white", "border": f"1px solid {GRID}",
        "borderRadius": 8, "padding": "8px", "marginBottom": "16px"}

app.layout = html.Div(
    [
        dcc.Interval(id="refresh", interval=REFRESH_MINUTES * 60 * 1000),
        html.H1("Bluesky Language Dashboard",
                style={"fontSize": 28, "marginBottom": 4, "color": TEXT_PRIMARY}),
        html.P(
            "Hourly samples of public Bluesky posts. Each post's self-reported language "
            "tag is compared with the language detected from its text.",
            style={"color": TEXT_SECONDARY, "marginTop": 0},
        ),
        html.Div(
            [
                html.Div([
                    html.Label("Time window", style={"fontSize": 13}),
                    dcc.RadioItems(
                        id="window",
                        options=[{"label": " Last 24 hours", "value": "24h"},
                                 {"label": " Last 7 days", "value": "7d"},
                                 {"label": " All data", "value": "all"}],
                        value="7d", inline=True,
                        inputStyle={"marginLeft": 12},
                    ),
                ]),
                html.Div([
                    html.Label("Languages on the trend chart", style={"fontSize": 13}),
                    dcc.Dropdown(id="languages", multi=True),
                ], style={"flex": 1, "minWidth": 280}),
                html.Div([
                    html.Label("Focus language", style={"fontSize": 13}),
                    dcc.Dropdown(id="focus", clearable=False),
                ], style={"width": 200}),
            ],
            style={"display": "flex", "gap": "24px", "alignItems": "flex-end",
                   "flexWrap": "wrap", "marginBottom": 16},
        ),
        html.Div(id="tiles", style={"display": "flex", "gap": "16px", "marginBottom": 16}),
        html.Div(dcc.Graph(id="share"), style=card),
        html.Div(
            [html.Div(dcc.Graph(id="match"), style={**card, "flex": 1, "minWidth": 380}),
             html.Div(dcc.Graph(id="confusion"), style={**card, "flex": 1.3, "minWidth": 420})],
            style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
        ),
        html.Div(
            [html.Div(dcc.Graph(id="focus-detected"), style={**card, "flex": 1, "minWidth": 380}),
             html.Div(dcc.Graph(id="focus-over-time"), style={**card, "flex": 1, "minWidth": 380})],
            style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
        ),
        html.H2("Text statistics by language", style={"fontSize": 18, "color": TEXT_PRIMARY}),
        html.Div(id="table", style=card),
        html.P(
            "Data from Bluesky's public Jetstream feed. Only aggregate statistics are stored.",
            style={"color": TEXT_SECONDARY, "fontSize": 12},
        ),
    ],
    style={"maxWidth": 1200, "margin": "0 auto", "padding": "24px",
           "fontFamily": FONT, "background": SURFACE},
)


@app.callback(
    Output("languages", "options"),
    Output("languages", "value"),
    Output("focus", "options"),
    Output("focus", "value"),
    Input("refresh", "n_intervals"),
    State("focus", "value"),
)
def update_options(_, current_focus):
    """Fill the dropdowns with the languages present in the data."""
    summary, _ = load_data()
    order = (summary.groupby("declared")["posts"].sum()
             .sort_values(ascending=False).index.tolist())
    options = [{"label": name(c), "value": c} for c in order]
    focus_options = [o for o in options if o["value"] != "other"]
    focus_codes = [o["value"] for o in focus_options]
    if current_focus in focus_codes:
        focus = current_focus
    elif "ru" in focus_codes:
        focus = "ru"
    else:
        focus = focus_codes[0]
    return options, order[:6], focus_options, focus


@app.callback(
    Output("tiles", "children"),
    Output("share", "figure"),
    Output("match", "figure"),
    Output("confusion", "figure"),
    Output("focus-detected", "figure"),
    Output("focus-over-time", "figure"),
    Output("table", "children"),
    Input("window", "value"),
    Input("languages", "value"),
    Input("focus", "value"),
    Input("refresh", "n_intervals"),
)
def update_dashboard(window, languages, focus, _):
    focus = focus or "ru"
    summary, pairs = load_data()
    summary = filter_window(summary, window)
    pairs = filter_window(pairs, window)

    tagged = summary[summary["declared"].isin(DETECTABLE_CODES)]
    matched = (tagged["match_rate"] * tagged["detectable"]).sum()
    overall_match = matched / tagged["detectable"].sum() if len(tagged) else 0
    untagged = summary.loc[summary["declared"] == "none", "posts"].sum()
    latest = summary["run_time"].max()

    tiles = [
        stat_tile("Samples", f"{summary['run_time'].nunique():,}",
                  f"Latest {latest:%b %d, %H:%M} UTC"),
        stat_tile("Posts analyzed", f"{summary['posts'].sum():,}"),
        stat_tile("Tag matches text", f"{overall_match:.0%}", "Of posts long enough to detect"),
        stat_tile("Posts with no tag", f"{untagged / summary['posts'].sum():.1%}"),
    ]

    return (
        tiles,
        share_chart(summary, languages or []),
        match_chart(summary),
        confusion_chart(pairs),
        focus_chart(pairs, focus),
        accuracy_over_time_chart(pairs, focus),
        stats_table(summary),
    )


if __name__ == "__main__":
    app.run(debug=True)
