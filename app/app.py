# ── F1 2026 SEASON TRACKER — DASH APP ────────────────────────────────────────
# Run locally:  python app/app.py
# Then open:    http://127.0.0.1:8050
#
# For deployment (Render/Railway), they look for 'server' at module level.
# That's why we expose it below — don't remove it.

import dash
from dash import dcc, html, dash_table, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import glob

# ── FILE PATHS ────────────────────────────────────────────────────────────────
# Paths are relative to the project root so they work both locally and deployed.
# When running locally from /app/, we go up one level to find /data/.
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_PATH  = os.path.join(BASE_DIR, 'data', 'processed')
BASELINE_PATH   = os.path.join(BASE_DIR, 'data', 'baseline')
RAW_PATH        = os.path.join(BASE_DIR, 'data', 'raw')

# ── DATA LOADING ──────────────────────────────────────────────────────────────
# We load data at startup. In a more advanced version, you could add a
# "Refresh Data" button that re-runs this logic without restarting the server.

def load_data():
    """
    Load and return all DataFrames needed by the dashboard.
    Falls back to building from raw CSVs if processed files don't exist yet
    (useful the first time you run the app before running the notebook).
    """

    # ── Try processed files first ─────────────────────────────────────────────
    race_master_path = os.path.join(PROCESSED_PATH, 'season_master_2026.csv')
    qual_master_path = os.path.join(PROCESSED_PATH, 'qualifying_master_2026.csv')

    if os.path.exists(race_master_path):
        df_races = pd.read_csv(race_master_path)
        df_qualifying = pd.read_csv(qual_master_path)
    else:
        # Fall back: build master from raw CSVs directly
        race_files = sorted(glob.glob(os.path.join(RAW_PATH, 'r*_2026.csv')))
        qual_files = sorted(glob.glob(os.path.join(RAW_PATH, 'r*_qualifying.csv')))
        df_races = pd.concat([pd.read_csv(f) for f in race_files], ignore_index=True)
        df_qualifying = pd.concat([pd.read_csv(f) for f in qual_files], ignore_index=True)

    # ── 2022 Baseline ─────────────────────────────────────────────────────────
    df_2022 = pd.read_csv(os.path.join(BASELINE_PATH, '2022_season.csv'))

    # ── Derive Driver Standings ───────────────────────────────────────────────
    df_driver_standings = (
        df_races
        .groupby(['driver_id', 'driver_name', 'constructor_name'])
        .agg(
            total_points  = ('points', 'sum'),
            races_entered = ('race_round', 'count'),
            wins          = ('finish_position', lambda x: (x == 1).sum()),
            podiums = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            dnfs          = ('status', lambda x: (x == 'DNF').sum()),
            fastest_laps  = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    df_driver_standings.insert(0, 'position', df_driver_standings.index + 1)

    # ── Derive Constructor Standings ──────────────────────────────────────────
    df_constructor_standings = (
        df_races
        .groupby(['constructor_id', 'constructor_name'])
        .agg(
            total_points = ('points', 'sum'),
            wins         = ('finish_position', lambda x: (x == 1).sum()),
            podiums = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            dnfs         = ('status', lambda x: (x == 'DNF').sum()),
            fastest_laps = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    df_constructor_standings.insert(0, 'position', df_constructor_standings.index + 1)

    # ── Cumulative Points for Progression Chart ───────────────────────────────
    df_cumulative = df_races.sort_values(['driver_id', 'race_round']).copy()
    df_cumulative['cumulative_points'] = (
        df_cumulative.groupby('driver_id')['points'].cumsum()
    )

    # ── Track Comparison ──────────────────────────────────────────────────────
    df_pole_2026 = (
        df_qualifying[df_qualifying['grid_position'] == 1]
        [['track_id', 'race_round', 'race_name', 'pole_lap_seconds',
          'pole_lap_display', 'driver_name']]
        .rename(columns={'driver_name': 'pole_sitter_2026'})
    )

    df_race_metrics_2026 = (
        df_races[df_races['fastest_lap_rank'] == 1]
        [['track_id', 'fastest_lap_seconds', 'fastest_lap_display', 'driver_name']]
        .rename(columns={
            'fastest_lap_seconds': 'fastest_race_lap_seconds_2026',
            'fastest_lap_display': 'fastest_race_lap_display_2026',
            'driver_name':         'fastest_lap_driver_2026'
        })
    )

    df_winner_2026 = (
        df_races[df_races['finish_position'] == 1]
        [['track_id', 'race_time_seconds', 'race_time_display', 'driver_name']]
        .rename(columns={
            'race_time_seconds': 'winner_race_time_seconds_2026',
            'race_time_display': 'winner_race_time_display_2026',
            'driver_name':       'winner_2026'
        })
    )

    df_2026_summary = (
        df_pole_2026
        .merge(df_race_metrics_2026, on='track_id', how='left')
        .merge(df_winner_2026,       on='track_id', how='left')
    )

    df_2022_slim = df_2022.rename(columns={
        'pole_lap_seconds':         'pole_lap_seconds_2022',
        'pole_lap_display':         'pole_lap_display_2022',
        'fastest_race_lap_seconds': 'fastest_race_lap_seconds_2022',
        'fastest_race_lap_display': 'fastest_race_lap_display_2022',
        'winner_race_time_seconds': 'winner_race_time_seconds_2022',
        'winner_race_time_display': 'winner_race_time_display_2022',
        'winner_driver_name':       'winner_2022',
    })[[
        'track_id', 'pole_lap_seconds_2022', 'pole_lap_display_2022',
        'fastest_race_lap_seconds_2022', 'fastest_race_lap_display_2022',
        'winner_race_time_seconds_2022', 'winner_race_time_display_2022',
        'winner_2022'
    ]]

    df_track_comparison = df_2026_summary.merge(df_2022_slim, on='track_id', how='left')

    df_track_comparison['pole_delta_seconds'] = (
        df_track_comparison['pole_lap_seconds'] - df_track_comparison['pole_lap_seconds_2022']
    ).round(3)

    df_track_comparison['fastest_lap_delta_seconds'] = (
        df_track_comparison['fastest_race_lap_seconds_2026'] - df_track_comparison['fastest_race_lap_seconds_2022']
    ).round(3)

    df_track_comparison['race_time_delta_seconds'] = (
        df_track_comparison['winner_race_time_seconds_2026'] - df_track_comparison['winner_race_time_seconds_2022']
    ).round(3)

    return (
        df_races,
        df_qualifying,
        df_driver_standings,
        df_constructor_standings,
        df_cumulative,
        df_track_comparison
    )


# Load everything at startup
(
    df_races,
    df_qualifying,
    df_driver_standings,
    df_constructor_standings,
    df_cumulative,
    df_track_comparison
) = load_data()

# ── FILTER OPTIONS (built from real data) ─────────────────────────────────────
all_drivers      = sorted(df_races['driver_name'].unique())
all_constructors = sorted(df_races['constructor_name'].unique())
all_rounds       = sorted(df_races['race_round'].unique())
all_tracks       = sorted(df_track_comparison['track_id'].unique())

# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
# F1-inspired: deep carbon background, red accent, light text
COLORS = {
    'bg':         '#0f0f0f',
    'surface':    '#1a1a1a',
    'border':     '#2a2a2a',
    'accent':     '#e10600',    # F1 red
    'accent2':    '#ff8c00',    # Orange for secondary highlights
    'text':       '#f0f0f0',
    'text_muted': '#888888',
    'faster':     '#00c851',    # Green — faster in 2026
    'slower':     '#ff4444',    # Red — slower in 2026
}

PLOTLY_TEMPLATE = {
    'layout': {
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'plot_bgcolor':  'rgba(0,0,0,0)',
        'font':          {'color': COLORS['text'], 'family': 'DM Mono, monospace'},
        'xaxis': {
            'gridcolor':     COLORS['border'],
            'linecolor':     COLORS['border'],
            'tickcolor':     COLORS['border'],
        },
        'yaxis': {
            'gridcolor':     COLORS['border'],
            'linecolor':     COLORS['border'],
            'tickcolor':     COLORS['border'],
        },
        'legend': {'bgcolor': 'rgba(0,0,0,0)'},
    }
}

# ── REUSABLE STYLE HELPERS ────────────────────────────────────────────────────
def card(children, style=None):
    """Wrap content in a styled surface card."""
    base = {
        'backgroundColor': COLORS['surface'],
        'border':          f"1px solid {COLORS['border']}",
        'borderRadius':    '6px',
        'padding':         '20px',
        'marginBottom':    '20px',
    }
    if style:
        base.update(style)
    return html.Div(children, style=base)


def section_label(text):
    """Small uppercase label above a filter or section."""
    return html.P(text, style={
        'color':         COLORS['text_muted'],
        'fontSize':      '10px',
        'letterSpacing': '0.12em',
        'textTransform': 'uppercase',
        'marginBottom':  '6px',
        'marginTop':     '0',
        'fontFamily':    'DM Mono, monospace',
    })


def table_styles():
    """Shared styles for dash_table.DataTable."""
    return {
        'style_table':  {'overflowX': 'auto'},
        'style_header': {
            'backgroundColor': COLORS['bg'],
            'color':           COLORS['accent'],
            'fontWeight':      '600',
            'fontSize':        '11px',
            'letterSpacing':   '0.08em',
            'textTransform':   'uppercase',
            'border':          f"1px solid {COLORS['border']}",
            'fontFamily':      'DM Mono, monospace',
            'padding':         '10px 14px',
        },
        'style_cell': {
            'backgroundColor': COLORS['surface'],
            'color':           COLORS['text'],
            'fontSize':        '13px',
            'border':          f"1px solid {COLORS['border']}",
            'fontFamily':      'DM Mono, monospace',
            'padding':         '9px 14px',
            'textAlign':       'left',
        },
        'style_data_conditional': [
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': COLORS['bg'],
            },
            {
                'if': {'column_id': 'position'},
                'color':      COLORS['accent'],
                'fontWeight': '700',
                'textAlign':  'center',
            },
            {
                'if': {'column_id': 'total_points'},
                'color':      COLORS['accent2'],
                'fontWeight': '600',
            },
        ],
    }


# ── DROPDOWN STYLE ────────────────────────────────────────────────────────────
DROPDOWN_STYLE = {
    'backgroundColor': COLORS['bg'],
    'color':           COLORS['text'],
    'border':          f"1px solid {COLORS['border']}",
    'borderRadius':    '4px',
    'fontFamily':      'DM Mono, monospace',
    'fontSize':        '13px',
}

# ── APP INITIALISATION ────────────────────────────────────────────────────────
# suppress_callback_exceptions=True allows callbacks that reference components
# defined inside tabs (which aren't in the DOM on page load)
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title='F1 2026 Season Tracker',
)

# Expose server for deployment platforms (Render, Railway, Gunicorn)
server = app.server

# ── LAYOUT ────────────────────────────────────────────────────────────────────
app.layout = html.Div(
    style={
        'backgroundColor': COLORS['bg'],
        'minHeight':       '100vh',
        'fontFamily':      'DM Mono, monospace',
        'color':           COLORS['text'],
    },
    children=[

        # ── HEADER ────────────────────────────────────────────────────────────
        html.Div(
            style={
                'borderBottom': f"1px solid {COLORS['border']}",
                'padding':      '24px 40px 20px',
                'display':      'flex',
                'alignItems':   'baseline',
                'gap':          '16px',
            },
            children=[
                html.Span('F1', style={
                    'color':      COLORS['accent'],
                    'fontSize':   '28px',
                    'fontWeight': '700',
                    'letterSpacing': '-0.02em',
                }),
                html.Span('2026 Season Tracker', style={
                    'fontSize':      '20px',
                    'fontWeight':    '400',
                    'color':         COLORS['text'],
                    'letterSpacing': '0.04em',
                }),
                html.Span(
                    f"Rounds loaded: {len(all_rounds)}",
                    style={
                        'marginLeft':  'auto',
                        'fontSize':    '11px',
                        'color':       COLORS['text_muted'],
                        'letterSpacing': '0.1em',
                    }
                ),
            ]
        ),

        # ── TABS ──────────────────────────────────────────────────────────────
        html.Div(
            style={'padding': '0 40px'},
            children=[
                dcc.Tabs(
                    id='tabs',
                    value='tab-standings',
                    style={'borderBottom': f"1px solid {COLORS['border']}"},
                    colors={
                        'border':     COLORS['border'],
                        'primary':    COLORS['accent'],
                        'background': COLORS['bg'],
                    },
                    children=[

                        # ── TAB 1: STANDINGS ──────────────────────────────────
                        dcc.Tab(
                            label='STANDINGS',
                            value='tab-standings',
                            style={
                                'color':           COLORS['text_muted'],
                                'backgroundColor': COLORS['bg'],
                                'border':          'none',
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            selected_style={
                                'color':           COLORS['text'],
                                'backgroundColor': COLORS['bg'],
                                'borderTop':       f"2px solid {COLORS['accent']}",
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            children=[
                                html.Div(style={'padding': '24px 0'}, children=[

                                    # ── FILTERS ROW ───────────────────────────
                                    card([
                                        html.Div(
                                            style={'display': 'flex', 'gap': '32px', 'flexWrap': 'wrap'},
                                            children=[
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('Filter by Constructor'),
                                                    dcc.Dropdown(
                                                        id='standings-constructor-filter',
                                                        options=[{'label': c, 'value': c} for c in all_constructors],
                                                        multi=True,
                                                        placeholder='All constructors...',
                                                        style=DROPDOWN_STYLE,
                                                    ),
                                                ]),
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('View Standings As Of Round'),
                                                    dcc.Dropdown(
                                                        id='standings-round-filter',
                                                        options=[{'label': f'Round {r}', 'value': r} for r in all_rounds],
                                                        value=max(all_rounds),
                                                        clearable=False,
                                                        style=DROPDOWN_STYLE,
                                                    ),
                                                ]),
                                            ]
                                        )
                                    ]),

                                    # ── TWO COLUMN LAYOUT ─────────────────────
                                    html.Div(
                                        style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px'},
                                        children=[

                                            # Driver Standings
                                            card([
                                                section_label('Driver Championship'),
                                                html.Div(id='driver-standings-table'),
                                            ]),

                                            # Constructor Standings
                                            card([
                                                section_label('Constructor Championship'),
                                                html.Div(id='constructor-standings-table'),
                                            ]),
                                        ]
                                    ),

                                    # ── STANDINGS BAR CHART ───────────────────
                                    card([
                                        section_label('Points Distribution'),
                                        dcc.Graph(id='standings-bar-chart', config={'displayModeBar': False}),
                                    ]),
                                ])
                            ]
                        ),

                        # ── TAB 2: TRACK COMPARISON ───────────────────────────
                        dcc.Tab(
                            label='TRACK COMPARISON',
                            value='tab-comparison',
                            style={
                                'color':           COLORS['text_muted'],
                                'backgroundColor': COLORS['bg'],
                                'border':          'none',
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            selected_style={
                                'color':           COLORS['text'],
                                'backgroundColor': COLORS['bg'],
                                'borderTop':       f"2px solid {COLORS['accent']}",
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            children=[
                                html.Div(style={'padding': '24px 0'}, children=[

                                    # ── FILTER ────────────────────────────────
                                    card([
                                        section_label('Filter by Circuit'),
                                        dcc.Dropdown(
                                            id='comparison-track-filter',
                                            options=[{'label': t.replace('_', ' ').title(), 'value': t} for t in all_tracks],
                                            multi=True,
                                            placeholder='All circuits...',
                                            style=DROPDOWN_STYLE,
                                        ),
                                    ]),

                                    # ── DELTA CHARTS ──────────────────────────
                                    card([
                                        section_label('Pole Lap Delta — 2026 vs 2022 (seconds)'),
                                        dcc.Graph(id='pole-delta-chart', config={'displayModeBar': False}),
                                    ]),

                                    card([
                                        section_label('Fastest Race Lap Delta — 2026 vs 2022 (seconds)'),
                                        dcc.Graph(id='fastest-lap-delta-chart', config={'displayModeBar': False}),
                                    ]),

                                    # ── COMPARISON TABLE ──────────────────────
                                    card([
                                        section_label('Full Track Comparison Table'),
                                        html.Div(id='track-comparison-table'),
                                    ]),
                                ])
                            ]
                        ),

                        # ── TAB 3: PROGRESSION ────────────────────────────────
                        dcc.Tab(
                            label='PROGRESSION',
                            value='tab-progression',
                            style={
                                'color':           COLORS['text_muted'],
                                'backgroundColor': COLORS['bg'],
                                'border':          'none',
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            selected_style={
                                'color':           COLORS['text'],
                                'backgroundColor': COLORS['bg'],
                                'borderTop':       f"2px solid {COLORS['accent']}",
                                'fontSize':        '11px',
                                'letterSpacing':   '0.12em',
                                'padding':         '14px 20px',
                            },
                            children=[
                                html.Div(style={'padding': '24px 0'}, children=[

                                    # ── FILTERS ───────────────────────────────
                                    card([
                                        html.Div(
                                            style={'display': 'flex', 'gap': '32px', 'flexWrap': 'wrap'},
                                            children=[
                                                html.Div(style={'flex': '2', 'minWidth': '300px'}, children=[
                                                    section_label('Filter Drivers'),
                                                    dcc.Dropdown(
                                                        id='progression-driver-filter',
                                                        options=[{'label': d, 'value': d} for d in all_drivers],
                                                        value=all_drivers[:10],   # Default: top 10
                                                        multi=True,
                                                        placeholder='Select drivers...',
                                                        style=DROPDOWN_STYLE,
                                                    ),
                                                ]),
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('Show Through Round'),
                                                    dcc.Dropdown(
                                                        id='progression-round-filter',
                                                        options=[{'label': f'Round {r}', 'value': r} for r in all_rounds],
                                                        value=max(all_rounds),
                                                        clearable=False,
                                                        style=DROPDOWN_STYLE,
                                                    ),
                                                ]),
                                            ]
                                        ),
                                    ]),

                                    # ── LINE CHART ────────────────────────────
                                    card([
                                        section_label('Championship Points Progression'),
                                        dcc.Graph(id='progression-chart', config={'displayModeBar': False}),
                                    ]),

                                    # ── WINS / PODIUMS SUMMARY ────────────────
                                    card([
                                        section_label('Wins & Podiums — Selected Drivers'),
                                        dcc.Graph(id='wins-podiums-chart', config={'displayModeBar': False}),
                                    ]),
                                ])
                            ]
                        ),
                    ]
                )
            ]
        )
    ]
)


# ── CALLBACKS ─────────────────────────────────────────────────────────────────
# Callbacks are the heart of Dash interactivity.
# Each callback:
#   - Listens to one or more Input components (dropdowns, sliders, etc.)
#   - Updates one or more Output components (charts, tables, text)
#   - Fires automatically whenever an Input changes
#
# The function receives current input values as arguments and returns
# the new content/figure for each Output.

# ── STANDINGS TAB CALLBACKS ───────────────────────────────────────────────────

@callback(
    Output('driver-standings-table', 'children'),
    Output('constructor-standings-table', 'children'),
    Output('standings-bar-chart', 'figure'),
    Input('standings-constructor-filter', 'value'),
    Input('standings-round-filter', 'value'),
)
def update_standings(selected_constructors, selected_round):
    """
    Recalculate standings filtered by constructor and capped at selected round.
    'selected_round' lets you look back at standings after any round,
    not just the most recent — useful for seeing how the season evolved.
    """

    # Filter races up to the selected round
    df_filtered = df_races[df_races['race_round'] <= selected_round].copy()

    # Apply constructor filter if any constructors are selected
    if selected_constructors:
        df_filtered = df_filtered[df_filtered['constructor_name'].isin(selected_constructors)]

    # Rebuild driver standings from filtered data
    driver_std = (
        df_filtered
        .groupby(['driver_id', 'driver_name', 'constructor_name'])
        .agg(
            total_points  = ('points', 'sum'),
            wins          = ('finish_position', lambda x: (x == 1).sum()),
            podiums = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            fastest_laps  = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    driver_std.insert(0, 'position', driver_std.index + 1)

    # Constructor standings
    constructor_std = (
        df_filtered
        .groupby(['constructor_id', 'constructor_name'])
        .agg(
            total_points = ('points', 'sum'),
            wins         = ('finish_position', lambda x: (x == 1).sum()),
            podiums = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    constructor_std.insert(0, 'position', constructor_std.index + 1)

    # ── Driver table ──────────────────────────────────────────────────────────
    driver_table = dash_table.DataTable(
        data=driver_std[['position', 'driver_name', 'constructor_name',
                          'total_points', 'wins', 'podiums', 'fastest_laps']].to_dict('records'),
        columns=[
            {'name': 'Pos',         'id': 'position'},
            {'name': 'Driver',      'id': 'driver_name'},
            {'name': 'Constructor', 'id': 'constructor_name'},
            {'name': 'Points',      'id': 'total_points'},
            {'name': 'Wins',        'id': 'wins'},
            {'name': 'Podiums',     'id': 'podiums'},
            {'name': 'FL',          'id': 'fastest_laps'},
        ],
        page_size=20,
        **table_styles(),
    )

    # ── Constructor table ─────────────────────────────────────────────────────
    constructor_table = dash_table.DataTable(
        data=constructor_std[['position', 'constructor_name',
                               'total_points', 'wins', 'podiums']].to_dict('records'),
        columns=[
            {'name': 'Pos',         'id': 'position'},
            {'name': 'Constructor', 'id': 'constructor_name'},
            {'name': 'Points',      'id': 'total_points'},
            {'name': 'Wins',        'id': 'wins'},
            {'name': 'Podiums',     'id': 'podiums'},
        ],
        page_size=12,
        **table_styles(),
    )

    # ── Bar chart — driver points ─────────────────────────────────────────────
    fig_bar = px.bar(
        driver_std,
        x='driver_name',
        y='total_points',
        color='constructor_name',
        text='total_points',
        labels={'driver_name': '', 'total_points': 'Points', 'constructor_name': 'Constructor'},
        category_orders={'driver_name': driver_std['driver_name'].tolist()},
    )
    fig_bar.update_traces(textposition='outside', textfont_size=10)
    fig_bar.update_layout(
        **PLOTLY_TEMPLATE['layout'],
        xaxis_tickangle=-40,
        showlegend=True,
        height=380,
        margin={'t': 20, 'b': 80, 'l': 40, 'r': 20},
        bargap=0.25,
    )

    return driver_table, constructor_table, fig_bar


# ── TRACK COMPARISON TAB CALLBACKS ───────────────────────────────────────────

@callback(
    Output('pole-delta-chart', 'figure'),
    Output('fastest-lap-delta-chart', 'figure'),
    Output('track-comparison-table', 'children'),
    Input('comparison-track-filter', 'value'),
)
def update_comparison(selected_tracks):
    """
    Filter the track comparison view to selected circuits.
    Only circuits that appear in both 2022 and 2026 will show deltas.
    """

    df = df_track_comparison.dropna(subset=['pole_delta_seconds']).copy()

    if selected_tracks:
        df = df[df['track_id'].isin(selected_tracks)]

    df['faster_in_2026_pole'] = df['pole_delta_seconds'] < 0
    df['track_label'] = df['track_id'].str.replace('_', ' ').str.title()

    # ── Pole delta chart ──────────────────────────────────────────────────────
    fig_pole = px.bar(
        df,
        x='track_label',
        y='pole_delta_seconds',
        color='faster_in_2026_pole',
        color_discrete_map={True: COLORS['faster'], False: COLORS['slower']},
        labels={'track_label': '', 'pole_delta_seconds': 'Delta (s)', 'faster_in_2026_pole': '2026 Faster'},
        hover_data={'pole_lap_display_2022': True, 'pole_lap_display': True, 'faster_in_2026_pole': False},
        custom_data=['pole_lap_display_2022', 'pole_lap_display'],
    )
    fig_pole.update_traces(
        hovertemplate='<b>%{x}</b><br>2022: %{customdata[0]}<br>2026: %{customdata[1]}<br>Δ %{y:.3f}s<extra></extra>'
    )
    fig_pole.add_hline(y=0, line_dash='dot', line_color=COLORS['text_muted'], opacity=0.6)
    fig_pole.update_layout(
        **PLOTLY_TEMPLATE['layout'],
        showlegend=False,
        height=320,
        margin={'t': 10, 'b': 60, 'l': 50, 'r': 20},
    )

    # ── Fastest lap delta chart ───────────────────────────────────────────────
    df2 = df.dropna(subset=['fastest_lap_delta_seconds']).copy()
    df2['faster_in_2026_fl'] = df2['fastest_lap_delta_seconds'] < 0

    fig_fl = px.bar(
        df2,
        x='track_label',
        y='fastest_lap_delta_seconds',
        color='faster_in_2026_fl',
        color_discrete_map={True: COLORS['faster'], False: COLORS['slower']},
        labels={'track_label': '', 'fastest_lap_delta_seconds': 'Delta (s)', 'faster_in_2026_fl': '2026 Faster'},
        custom_data=['fastest_race_lap_display_2022', 'fastest_race_lap_display_2026'],
    )
    fig_fl.update_traces(
        hovertemplate='<b>%{x}</b><br>2022: %{customdata[0]}<br>2026: %{customdata[1]}<br>Δ %{y:.3f}s<extra></extra>'
    )
    fig_fl.add_hline(y=0, line_dash='dot', line_color=COLORS['text_muted'], opacity=0.6)
    fig_fl.update_layout(
        **PLOTLY_TEMPLATE['layout'],
        showlegend=False,
        height=320,
        margin={'t': 10, 'b': 60, 'l': 50, 'r': 20},
    )

    # ── Comparison table ──────────────────────────────────────────────────────
    table_data = df[[
        'track_label',
        'pole_lap_display_2022', 'pole_lap_display',       'pole_delta_seconds',
        'fastest_race_lap_display_2022', 'fastest_race_lap_display_2026', 'fastest_lap_delta_seconds',
    ]].rename(columns={
        'track_label':                       'Circuit',
        'pole_lap_display_2022':             'Pole 2022',
        'pole_lap_display':                  'Pole 2026',
        'pole_delta_seconds':                'Pole Δ (s)',
        'fastest_race_lap_display_2022':     'FL 2022',
        'fastest_race_lap_display_2026':     'FL 2026',
        'fastest_lap_delta_seconds':         'FL Δ (s)',
    })

    ts = table_styles()
    # Add conditional coloring for delta columns
    ts['style_data_conditional'] += [
        {
            'if': {'filter_query': '{Pole Δ (s)} < 0', 'column_id': 'Pole Δ (s)'},
            'color': COLORS['faster'],
        },
        {
            'if': {'filter_query': '{Pole Δ (s)} > 0', 'column_id': 'Pole Δ (s)'},
            'color': COLORS['slower'],
        },
        {
            'if': {'filter_query': '{FL Δ (s)} < 0', 'column_id': 'FL Δ (s)'},
            'color': COLORS['faster'],
        },
        {
            'if': {'filter_query': '{FL Δ (s)} > 0', 'column_id': 'FL Δ (s)'},
            'color': COLORS['slower'],
        },
    ]

    comparison_table = dash_table.DataTable(
        data=table_data.to_dict('records'),
        columns=[{'name': c, 'id': c} for c in table_data.columns],
        **ts,
    )

    return fig_pole, fig_fl, comparison_table


# ── PROGRESSION TAB CALLBACKS ─────────────────────────────────────────────────

@callback(
    Output('progression-chart', 'figure'),
    Output('wins-podiums-chart', 'figure'),
    Input('progression-driver-filter', 'value'),
    Input('progression-round-filter', 'value'),
)
def update_progression(selected_drivers, selected_round):
    """
    Championship progression line chart filtered by driver selection
    and capped at the selected round.
    """

    # Default to all drivers if nothing selected
    drivers = selected_drivers if selected_drivers else all_drivers

    df = df_cumulative[
        (df_cumulative['driver_name'].isin(drivers)) &
        (df_cumulative['race_round'] <= selected_round)
    ].copy()

    # ── Line chart ────────────────────────────────────────────────────────────
    fig_line = px.line(
        df,
        x='race_round',
        y='cumulative_points',
        color='driver_name',
        markers=True,
        labels={
            'race_round':        'Round',
            'cumulative_points': 'Cumulative Points',
            'driver_name':       'Driver',
        },
        hover_data=['race_name', 'points'],
        custom_data=['race_name', 'points', 'driver_name'],
    )
    fig_line.update_traces(
        hovertemplate='<b>%{customdata[2]}</b><br>%{customdata[0]}<br>Points this race: %{customdata[1]}<br>Total: %{y}<extra></extra>',
        line={'width': 2},
        marker={'size': 6},
    )
    fig_line.update_layout(
        **PLOTLY_TEMPLATE['layout'],
        height=420,
        margin={'t': 10, 'b': 40, 'l': 50, 'r': 20},
        hovermode='x unified',
    )
    fig_line.update_xaxes(dtick=1, title='Race Round')

    # ── Wins & podiums grouped bar ────────────────────────────────────────────
    df_wp = df_races[
        (df_races['driver_name'].isin(drivers)) &
        (df_races['race_round'] <= selected_round)
    ]
    df_wp_summary = (
        df_wp
        .groupby('driver_name')
        .agg(
            Wins    = ('finish_position', lambda x: (x == 1).sum()),
            Podiums = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
        )
        .reset_index()
        .sort_values('Wins', ascending=False)
    )

    fig_wp = go.Figure()
    # Force Plotly to respect our sort order by explicitly setting
    # categoryorder on the x-axis to match the sorted DataFrame index
    driver_order = df_wp_summary['driver_name'].tolist()

    fig_wp.add_trace(go.Bar(
        name='Wins',
        x=df_wp_summary['driver_name'],
        y=df_wp_summary['Wins'],
        marker_color=COLORS['accent'],
    ))
    fig_wp.add_trace(go.Bar(
        name='Podiums',
        x=df_wp_summary['driver_name'],
        y=df_wp_summary['Podiums'],
        marker_color=COLORS['accent2'],
        opacity=0.7,
    ))
    fig_wp.update_xaxes(categoryorder='array', categoryarray=driver_order)
    fig_wp.update_layout(
    **PLOTLY_TEMPLATE['layout'],
    barmode='group',
    height=320,
    margin={'t': 10, 'b': 80, 'l': 40, 'r': 20},
    )
    fig_wp.update_xaxes(tickangle=-40)
    fig_wp.update_layout(legend={'orientation': 'h', 'y': 1.05})

    return fig_line, fig_wp


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # debug=True enables hot-reload: save the file and the browser refreshes automatically
    # Set debug=False before deploying
    app.run(debug=True, host='0.0.0.0', port=8050)
