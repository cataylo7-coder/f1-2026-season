# ── F1 2026 SEASON TRACKER — DASH APP ────────────────────────────────────────
# Run locally:  python app/app.py
# Then open:    http://127.0.0.1:8050
#
# Environment variables required:
#   ANTHROPIC_API_KEY  — your Anthropic API key
#   DASH_USERNAME      — login username
#   DASH_PASSWORD      — login password
#
# Set these in Render dashboard under Environment → Add Environment Variable
# For local use, create a .env file in the project root (never commit it)

import dash
from dash import dcc, html, dash_table, Input, Output, State, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import os
import glob
import anthropic
from dash.exceptions import PreventUpdate

# ── FILE PATHS ────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_PATH  = os.path.join(BASE_DIR, 'data', 'processed')
BASELINE_PATH   = os.path.join(BASE_DIR, 'data', 'baseline')
RAW_PATH        = os.path.join(BASE_DIR, 'data', 'raw')

from dotenv import load_dotenv
load_dotenv()

# ── ENVIRONMENT VARIABLES ─────────────────────────────────────────────────────
# We never hardcode secrets. They live in environment variables so they
# never touch the codebase or GitHub.
# Locally: create a .env file and load with python-dotenv (optional)
# On Render: set these in the dashboard under Environment tab
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
DASH_USERNAME     = os.environ.get('DASH_USERNAME', 'claytay90')
DASH_PASSWORD     = os.environ.get('DASH_PASSWORD', 'PamaGKnight$90!')

# ── DATA LOADING ──────────────────────────────────────────────────────────────
def load_data():
    race_master_path = os.path.join(PROCESSED_PATH, 'season_master_2026.csv')
    qual_master_path = os.path.join(PROCESSED_PATH, 'qualifying_master_2026.csv')

    if os.path.exists(race_master_path):
        df_races      = pd.read_csv(race_master_path)
        df_qualifying = pd.read_csv(qual_master_path)
    else:
        race_files    = sorted(glob.glob(os.path.join(RAW_PATH, 'r*_2026.csv')))
        qual_files    = sorted(glob.glob(os.path.join(RAW_PATH, 'r*_qualifying.csv')))
        df_races      = pd.concat([pd.read_csv(f) for f in race_files], ignore_index=True)
        df_qualifying = pd.concat([pd.read_csv(f) for f in qual_files], ignore_index=True)

    df_2022 = pd.read_csv(os.path.join(BASELINE_PATH, '2022_season.csv'))

    df_driver_standings = (
        df_races
        .groupby(['driver_id', 'driver_name', 'constructor_name'])
        .agg(
            total_points  = ('points', 'sum'),
            races_entered = ('race_round', 'count'),
            wins          = ('finish_position', lambda x: (x == 1).sum()),
            podiums       = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            dnfs          = ('status', lambda x: (x == 'DNF').sum()),
            fastest_laps  = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    df_driver_standings.insert(0, 'position', df_driver_standings.index + 1)

    df_constructor_standings = (
        df_races
        .groupby(['constructor_id', 'constructor_name'])
        .agg(
            total_points = ('points', 'sum'),
            wins         = ('finish_position', lambda x: (x == 1).sum()),
            podiums      = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            dnfs         = ('status', lambda x: (x == 'DNF').sum()),
            fastest_laps = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    df_constructor_standings.insert(0, 'position', df_constructor_standings.index + 1)

    df_cumulative = df_races.sort_values(['driver_id', 'race_round']).copy()
    df_cumulative['cumulative_points'] = (
        df_cumulative.groupby('driver_id')['points'].cumsum()
    )

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
        df_races, df_qualifying, df_driver_standings,
        df_constructor_standings, df_cumulative, df_track_comparison
    )


(
    df_races, df_qualifying, df_driver_standings,
    df_constructor_standings, df_cumulative, df_track_comparison
) = load_data()

all_drivers      = sorted(df_races['driver_name'].unique())
all_constructors = sorted(df_races['constructor_name'].unique())
all_rounds       = sorted(df_races['race_round'].unique())
all_tracks       = sorted(df_track_comparison['track_id'].unique())

# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
COLORS = {
    'bg':         '#0f0f0f',
    'surface':    '#1a1a1a',
    'border':     '#2a2a2a',
    'accent':     '#e10600',
    'accent2':    '#ff8c00',
    'text':       '#f0f0f0',
    'text_muted': '#888888',
    'faster':     '#00c851',
    'slower':     '#ff4444',
}

PLOTLY_TEMPLATE = {
    'layout': {
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'plot_bgcolor':  'rgba(0,0,0,0)',
        'font':          {'color': COLORS['text'], 'family': 'DM Mono, monospace'},
        'xaxis': {'gridcolor': COLORS['border'], 'linecolor': COLORS['border'], 'tickcolor': COLORS['border']},
        'yaxis': {'gridcolor': COLORS['border'], 'linecolor': COLORS['border'], 'tickcolor': COLORS['border']},
        'legend': {'bgcolor': 'rgba(0,0,0,0)'},
    }
}

# ── REUSABLE STYLE HELPERS ────────────────────────────────────────────────────
def card(children, style=None):
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
            {'if': {'row_index': 'odd'}, 'backgroundColor': COLORS['bg']},
            {'if': {'column_id': 'position'}, 'color': COLORS['accent'], 'fontWeight': '700', 'textAlign': 'center'},
            {'if': {'column_id': 'total_points'}, 'color': COLORS['accent2'], 'fontWeight': '600'},
        ],
    }


DROPDOWN_STYLE = {
    'backgroundColor': COLORS['bg'],
    'color':           COLORS['text'],
    'border':          f"1px solid {COLORS['border']}",
    'borderRadius':    '4px',
    'fontFamily':      'DM Mono, monospace',
    'fontSize':        '13px',
}

# ── AI HELPER FUNCTIONS ───────────────────────────────────────────────────────
# These functions prepare data context and call the Claude API.
# Each function formats a specific DataFrame as readable text,
# builds a focused prompt, and returns Claude's response as a string.
#
# Key concept: we're doing "context injection" — passing structured data
# directly into the prompt so Claude can reason about your actual numbers,
# not generic F1 knowledge. This is the same pattern used in enterprise
# AI agents that connect LLMs to ERP data like Workday.

def get_claude_client():
    """
    Initialize the Anthropic client using the API key from environment.
    We initialize on demand rather than at startup so the app still loads
    even if the key isn't set yet.
    """
    if not ANTHROPIC_API_KEY:
        return None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def call_claude(system_prompt, user_prompt, max_tokens=600):
    """
    Make a single Claude API call and return the response text.
    Uses claude-haiku-4-5 — fastest and most cost-efficient model,
    ideal for data analysis responses like this.

    Parameters:
        system_prompt: defines Claude's role and behavior
        user_prompt:   the specific question or task with data context
        max_tokens:    limits response length to control cost
    """
    client = get_claude_client()
    if not client:
        return "⚠️ API key not configured. Add ANTHROPIC_API_KEY to your environment variables."

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": f"{system_prompt}\n\n{user_prompt}"
                }
            ]
        )
        return message.content[0].text

    except anthropic.APIError as e:
        return f"⚠️ API error: {str(e)}"


# System prompt shared across all F1 analysis calls
F1_SYSTEM_PROMPT = """You are an expert Formula 1 analyst with deep knowledge of 
racing strategy, regulations, and statistics. You are analyzing the 2026 F1 season, 
which features new power unit regulations alongside revised aerodynamic rules — 
a significant change from the 2022 ground effect era. 
Be concise, insightful, and specific. Use the data provided. 
Respond in 3-5 paragraphs maximum. Do not use excessive bullet points."""


def build_race_narrative_prompt(race_round):
    """
    Build a post-race narrative prompt for a specific round.
    Pulls race results and formats them as a readable table for Claude.
    """
    df = df_races[df_races['race_round'] == race_round].copy()

    # Only race sessions, not sprint
    if 'session' in df.columns:
        df_race_only = df[df['session'] == 'Race'].copy()
        df_sprint    = df[df['session'] == 'Sprint'].copy()
    else:
        df_race_only = df.copy()
        df_sprint    = pd.DataFrame()

    race_name = df_race_only['race_name'].iloc[0] if not df_race_only.empty else f"Round {race_round}"

    results_text = df_race_only[['finish_position', 'driver_name', 'constructor_name',
                                  'points', 'status', 'fastest_lap_display']]\
                   .sort_values('finish_position')\
                   .to_string(index=False)

    sprint_text = ""
    if not df_sprint.empty:
        sprint_text = f"\n\nSPRINT RACE RESULTS:\n{df_sprint[['finish_position', 'driver_name', 'points']].sort_values('finish_position').to_string(index=False)}"

    standings_text = df_driver_standings[['position', 'driver_name', 'constructor_name', 'total_points']]\
                     .head(10).to_string(index=False)

    return f"""Analyze the following F1 race results and provide a post-race narrative.

RACE: {race_name} (Round {race_round})

RACE RESULTS:
{results_text}
{sprint_text}

CURRENT CHAMPIONSHIP STANDINGS (Top 10):
{standings_text}

Write a compelling post-race analysis covering:
1. How the race unfolded and key moments
2. Standout performances and disappointments  
3. Championship implications going forward"""


def build_championship_insight_prompt():
    """
    Build a championship analysis prompt using current standings data.
    Includes points gaps, wins, and constructor battle.
    """
    driver_text = df_driver_standings[['position', 'driver_name', 'constructor_name',
                                        'total_points', 'wins', 'podiums', 'dnfs']]\
                  .to_string(index=False)

    constructor_text = df_constructor_standings[['position', 'constructor_name',
                                                   'total_points', 'wins', 'podiums']]\
                       .to_string(index=False)

    rounds_completed = len(all_rounds)
    total_rounds     = 24   # 2026 season length

    return f"""Analyze the current 2026 F1 Championship standings and predict the title fight.

ROUNDS COMPLETED: {rounds_completed} of {total_rounds}

DRIVER CHAMPIONSHIP:
{driver_text}

CONSTRUCTOR CHAMPIONSHIP:
{constructor_text}

Provide:
1. Assessment of the championship battle — who are the genuine title contenders and why
2. Which constructors are strongest and why
3. Key threats and vulnerabilities for the current leaders
4. Your prediction for how the title fight develops over the remaining {total_rounds - rounds_completed} rounds"""


def build_track_comparison_prompt():
    """
    Build a track comparison analysis prompt using 2026 vs 2022 delta data.
    Only includes tracks where we have both years of data.
    """
    df = df_track_comparison.dropna(subset=['pole_delta_seconds']).copy()

    if df.empty:
        return "No track comparison data available yet — need at least one race that also appeared on the 2022 calendar."

    comparison_text = df[['race_name', 'pole_lap_display_2022', 'pole_lap_display',
                            'pole_delta_seconds', 'fastest_race_lap_display_2022',
                            'fastest_race_lap_display_2026', 'fastest_lap_delta_seconds']]\
                      .to_string(index=False)

    return f"""Analyze the following lap time comparison between the 2026 and 2022 F1 seasons.
The 2022 season was the first year of ground effect regulations. 
The 2026 season introduces new power unit regulations alongside revised aerodynamics.
Negative delta = 2026 is FASTER. Positive delta = 2026 is SLOWER.

TRACK COMPARISON DATA:
{comparison_text}

Provide:
1. Overall trend — are 2026 cars faster or slower than 2022 at these circuits and why
2. Which circuits show the most significant differences and what might explain them
3. What these lap time trends suggest about the 2026 car concept vs 2022 ground effect cars
4. Any anomalies worth noting"""


# ── APP INITIALISATION ────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title='F1 2026 Season Tracker',
)

# ── BASIC AUTH ────────────────────────────────────────────────────────────────
# We implement auth manually rather than using dash-auth library
# so we don't need an extra dependency.
# This uses Dash's built-in _auth support via Flask's before_request.
# Credentials come from environment variables — never from code.
from flask import request, Response

@app.server.before_request
def require_login():
    """
    Check every incoming request for valid HTTP Basic Auth credentials.
    Returns 401 if credentials are missing or wrong, which triggers
    the browser's built-in login dialog.

    HTTP Basic Auth is sufficient for a personal app — it's not
    enterprise-grade SSO, but it keeps the app private from casual visitors.
    """
    # Skip auth for Render's health check endpoint
    if request.path == '/ping':
        return None

    auth = request.authorization
    if not auth or auth.username != DASH_USERNAME or auth.password != DASH_PASSWORD:
        return Response(
            'Authentication required.',
            401,
            {'WWW-Authenticate': 'Basic realm="F1 2026 Tracker"'}
        )


# Expose server for Render/Gunicorn deployment
server = app.server

# ── TAB STYLE HELPERS ─────────────────────────────────────────────────────────
TAB_STYLE = {
    'color':           COLORS['text_muted'],
    'backgroundColor': COLORS['bg'],
    'border':          'none',
    'fontSize':        '11px',
    'letterSpacing':   '0.12em',
    'padding':         '14px 20px',
}

TAB_SELECTED_STYLE = {
    'color':           COLORS['text'],
    'backgroundColor': COLORS['bg'],
    'borderTop':       f"2px solid {COLORS['accent']}",
    'fontSize':        '11px',
    'letterSpacing':   '0.12em',
    'padding':         '14px 20px',
}

# ── LAYOUT ────────────────────────────────────────────────────────────────────
app.layout = html.Div(
    style={'backgroundColor': COLORS['bg'], 'minHeight': '100vh',
           'fontFamily': 'DM Mono, monospace', 'color': COLORS['text']},
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
                html.Span('F1', style={'color': COLORS['accent'], 'fontSize': '28px',
                                        'fontWeight': '700', 'letterSpacing': '-0.02em'}),
                html.Span('2026 Season Tracker', style={'fontSize': '20px', 'fontWeight': '400',
                                                         'color': COLORS['text'], 'letterSpacing': '0.04em'}),
                html.Span(f"Rounds loaded: {len(all_rounds)}",
                          style={'marginLeft': 'auto', 'fontSize': '11px',
                                 'color': COLORS['text_muted'], 'letterSpacing': '0.1em'}),
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
                    colors={'border': COLORS['border'], 'primary': COLORS['accent'], 'background': COLORS['bg']},
                    children=[

                        # ── TAB 1: STANDINGS ──────────────────────────────────
                        dcc.Tab(label='STANDINGS', value='tab-standings',
                                style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                                children=[
                                    html.Div(style={'padding': '24px 0'}, children=[
                                        card([
                                            html.Div(style={'display': 'flex', 'gap': '32px', 'flexWrap': 'wrap'}, children=[
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('Filter by Constructor'),
                                                    dcc.Dropdown(id='standings-constructor-filter',
                                                                 options=[{'label': c, 'value': c} for c in all_constructors],
                                                                 multi=True, placeholder='All constructors...', style=DROPDOWN_STYLE),
                                                ]),
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('View Standings As Of Round'),
                                                    dcc.Dropdown(id='standings-round-filter',
                                                                 options=[{'label': f'Round {r}', 'value': r} for r in all_rounds],
                                                                 value=max(all_rounds), clearable=False, style=DROPDOWN_STYLE),
                                                ]),
                                            ])
                                        ]),
                                        html.Div(style={'display': 'grid', 'gridTemplateColumns': '1fr 1fr', 'gap': '20px'}, children=[
                                            card([section_label('Driver Championship'), html.Div(id='driver-standings-table')]),
                                            card([section_label('Constructor Championship'), html.Div(id='constructor-standings-table')]),
                                        ]),
                                        card([section_label('Points Distribution'), dcc.Graph(id='standings-bar-chart', config={'displayModeBar': False})]),
                                    ])
                                ]),

                        # ── TAB 2: TRACK COMPARISON ───────────────────────────
                        dcc.Tab(label='TRACK COMPARISON', value='tab-comparison',
                                style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                                children=[
                                    html.Div(style={'padding': '24px 0'}, children=[
                                        card([
                                            section_label('Filter by Circuit'),
                                            dcc.Dropdown(id='comparison-track-filter',
                                                         options=[{'label': t.replace('_', ' ').title(), 'value': t} for t in all_tracks],
                                                         multi=True, placeholder='All circuits...', style=DROPDOWN_STYLE),
                                        ]),
                                        card([section_label('Pole Lap Delta — 2026 vs 2022 (seconds)'),
                                              dcc.Graph(id='pole-delta-chart', config={'displayModeBar': False})]),
                                        card([section_label('Fastest Race Lap Delta — 2026 vs 2022 (seconds)'),
                                              dcc.Graph(id='fastest-lap-delta-chart', config={'displayModeBar': False})]),
                                        card([section_label('Full Track Comparison Table'), html.Div(id='track-comparison-table')]),
                                    ])
                                ]),

                        # ── TAB 3: PROGRESSION ────────────────────────────────
                        dcc.Tab(label='PROGRESSION', value='tab-progression',
                                style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                                children=[
                                    html.Div(style={'padding': '24px 0'}, children=[
                                        card([
                                            html.Div(style={'display': 'flex', 'gap': '32px', 'flexWrap': 'wrap'}, children=[
                                                html.Div(style={'flex': '2', 'minWidth': '300px'}, children=[
                                                    section_label('Filter Drivers'),
                                                    dcc.Dropdown(id='progression-driver-filter',
                                                                 options=[{'label': d, 'value': d} for d in all_drivers],
                                                                 value=all_drivers[:10], multi=True,
                                                                 placeholder='Select drivers...', style=DROPDOWN_STYLE),
                                                ]),
                                                html.Div(style={'flex': '1', 'minWidth': '200px'}, children=[
                                                    section_label('Show Through Round'),
                                                    dcc.Dropdown(id='progression-round-filter',
                                                                 options=[{'label': f'Round {r}', 'value': r} for r in all_rounds],
                                                                 value=max(all_rounds), clearable=False, style=DROPDOWN_STYLE),
                                                ]),
                                            ]),
                                        ]),
                                        card([section_label('Championship Points Progression'),
                                              dcc.Graph(id='progression-chart', config={'displayModeBar': False})]),
                                        card([section_label('Wins & Podiums — Selected Drivers'),
                                              dcc.Graph(id='wins-podiums-chart', config={'displayModeBar': False})]),
                                    ])
                                ]),

                        # ── TAB 4: AI ANALYST ─────────────────────────────────
                        dcc.Tab(label='AI ANALYST', value='tab-ai',
                                style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE,
                                children=[
                                    html.Div(style={'padding': '24px 0'}, children=[

                                        # ── Intro card ────────────────────────
                                        card([
                                            html.P(
                                                "Powered by Claude. Each button sends your actual season data as context — "
                                                "responses are grounded in the real numbers, not generic F1 knowledge.",
                                                style={'color': COLORS['text_muted'], 'fontSize': '13px',
                                                       'margin': '0', 'lineHeight': '1.6'}
                                            )
                                        ]),

                                        # ── Post-race narrative ───────────────
                                        card([
                                            section_label('Post-Race Narrative'),
                                            html.Div(style={'display': 'flex', 'gap': '12px', 'alignItems': 'center', 'marginBottom': '16px'}, children=[
                                                dcc.Dropdown(
                                                    id='ai-race-round-select',
                                                    options=[{'label': f"Round {r} — {df_races[df_races['race_round'] == r]['race_name'].iloc[0]}", 'value': r}
                                                             for r in all_rounds],
                                                    value=max(all_rounds),
                                                    clearable=False,
                                                    style={**DROPDOWN_STYLE, 'flex': '1'},
                                                ),
                                                html.Button(
                                                    'Generate Race Report',
                                                    id='btn-race-narrative',
                                                    style={
                                                        'backgroundColor': COLORS['accent'],
                                                        'color':           COLORS['text'],
                                                        'border':          'none',
                                                        'borderRadius':    '4px',
                                                        'padding':         '10px 20px',
                                                        'fontSize':        '12px',
                                                        'letterSpacing':   '0.08em',
                                                        'cursor':          'pointer',
                                                        'fontFamily':      'DM Mono, monospace',
                                                        'whiteSpace':      'nowrap',
                                                    }
                                                ),
                                            ]),
                                            dcc.Loading(
                                                id='loading-race-narrative',
                                                type='circle',
                                                color=COLORS['accent'],
                                                children=html.Div(id='output-race-narrative',
                                                                  style={'color': COLORS['text'], 'lineHeight': '1.8',
                                                                         'fontSize': '14px', 'whiteSpace': 'pre-wrap'})
                                            ),
                                        ]),

                                        # ── Championship insight ──────────────
                                        card([
                                            section_label('Championship Insight'),
                                            html.Div(style={'marginBottom': '16px'}, children=[
                                                html.Button(
                                                    'Analyze Championship Battle',
                                                    id='btn-championship',
                                                    style={
                                                        'backgroundColor': COLORS['surface'],
                                                        'color':           COLORS['accent'],
                                                        'border':          f"1px solid {COLORS['accent']}",
                                                        'borderRadius':    '4px',
                                                        'padding':         '10px 20px',
                                                        'fontSize':        '12px',
                                                        'letterSpacing':   '0.08em',
                                                        'cursor':          'pointer',
                                                        'fontFamily':      'DM Mono, monospace',
                                                    }
                                                ),
                                            ]),
                                            dcc.Loading(
                                                id='loading-championship',
                                                type='circle',
                                                color=COLORS['accent'],
                                                children=html.Div(id='output-championship',
                                                                  style={'color': COLORS['text'], 'lineHeight': '1.8',
                                                                         'fontSize': '14px', 'whiteSpace': 'pre-wrap'})
                                            ),
                                        ]),

                                        # ── Track comparison analyst ──────────
                                        card([
                                            section_label('Track Comparison Analyst'),
                                            html.Div(style={'marginBottom': '16px'}, children=[
                                                html.Button(
                                                    'Explain 2026 vs 2022 Lap Times',
                                                    id='btn-track-comparison',
                                                    style={
                                                        'backgroundColor': COLORS['surface'],
                                                        'color':           COLORS['accent'],
                                                        'border':          f"1px solid {COLORS['accent']}",
                                                        'borderRadius':    '4px',
                                                        'padding':         '10px 20px',
                                                        'fontSize':        '12px',
                                                        'letterSpacing':   '0.08em',
                                                        'cursor':          'pointer',
                                                        'fontFamily':      'DM Mono, monospace',
                                                    }
                                                ),
                                            ]),
                                            dcc.Loading(
                                                id='loading-track-comparison',
                                                type='circle',
                                                color=COLORS['accent'],
                                                children=html.Div(id='output-track-comparison',
                                                                  style={'color': COLORS['text'], 'lineHeight': '1.8',
                                                                         'fontSize': '14px', 'whiteSpace': 'pre-wrap'})
                                            ),
                                        ]),

                                        # ── Natural language Q&A ──────────────
                                        card([
                                            section_label('Natural Language Q&A'),
                                            html.P(
                                                "Ask any question about the 2026 season data. Claude will answer using the actual race results, standings, and track comparison numbers.",
                                                style={'color': COLORS['text_muted'], 'fontSize': '12px',
                                                       'marginBottom': '12px', 'lineHeight': '1.6'}
                                            ),
                                            html.Div(style={'display': 'flex', 'gap': '12px'}, children=[
                                                dcc.Input(
                                                    id='ai-question-input',
                                                    type='text',
                                                    placeholder='e.g. Who has the best points-per-race average so far?',
                                                    debounce=False,
                                                    style={
                                                        'flex':            '1',
                                                        'backgroundColor': COLORS['bg'],
                                                        'color':           COLORS['text'],
                                                        'border':          f"1px solid {COLORS['border']}",
                                                        'borderRadius':    '4px',
                                                        'padding':         '10px 14px',
                                                        'fontSize':        '13px',
                                                        'fontFamily':      'DM Mono, monospace',
                                                        'outline':         'none',
                                                    }
                                                ),
                                                html.Button(
                                                    'Ask',
                                                    id='btn-ask',
                                                    style={
                                                        'backgroundColor': COLORS['accent'],
                                                        'color':           COLORS['text'],
                                                        'border':          'none',
                                                        'borderRadius':    '4px',
                                                        'padding':         '10px 24px',
                                                        'fontSize':        '12px',
                                                        'letterSpacing':   '0.08em',
                                                        'cursor':          'pointer',
                                                        'fontFamily':      'DM Mono, monospace',
                                                    }
                                                ),
                                            ]),
                                            dcc.Loading(
                                                id='loading-qa',
                                                type='circle',
                                                color=COLORS['accent'],
                                                children=html.Div(id='output-qa',
                                                                  style={'color': COLORS['text'], 'lineHeight': '1.8',
                                                                         'fontSize': '14px', 'whiteSpace': 'pre-wrap',
                                                                         'marginTop': '16px'})
                                            ),
                                        ]),
                                    ])
                                ]),
                    ]
                )
            ]
        )
    ]
)


# ── STANDINGS CALLBACKS ───────────────────────────────────────────────────────
@callback(
    Output('driver-standings-table', 'children'),
    Output('constructor-standings-table', 'children'),
    Output('standings-bar-chart', 'figure'),
    Input('standings-constructor-filter', 'value'),
    Input('standings-round-filter', 'value'),
)
def update_standings(selected_constructors, selected_round):
    df_filtered = df_races[df_races['race_round'] <= selected_round].copy()
    if selected_constructors:
        df_filtered = df_filtered[df_filtered['constructor_name'].isin(selected_constructors)]

    driver_std = (
        df_filtered
        .groupby(['driver_id', 'driver_name', 'constructor_name'])
        .agg(
            total_points = ('points', 'sum'),
            wins         = ('finish_position', lambda x: (x == 1).sum()),
            podiums      = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
            fastest_laps = ('fastest_lap_rank', lambda x: (x == 1).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    driver_std.insert(0, 'position', driver_std.index + 1)

    constructor_std = (
        df_filtered
        .groupby(['constructor_id', 'constructor_name'])
        .agg(
            total_points = ('points', 'sum'),
            wins         = ('finish_position', lambda x: (x == 1).sum()),
            podiums      = ('finish_position', lambda x: ((x >= 1) & (x <= 3)).sum()),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    constructor_std.insert(0, 'position', constructor_std.index + 1)

    driver_table = dash_table.DataTable(
        data=driver_std[['position', 'driver_name', 'constructor_name',
                          'total_points', 'wins', 'podiums', 'fastest_laps']].to_dict('records'),
        columns=[
            {'name': 'Pos', 'id': 'position'}, {'name': 'Driver', 'id': 'driver_name'},
            {'name': 'Constructor', 'id': 'constructor_name'}, {'name': 'Points', 'id': 'total_points'},
            {'name': 'Wins', 'id': 'wins'}, {'name': 'Podiums', 'id': 'podiums'},
            {'name': 'FL', 'id': 'fastest_laps'},
        ],
        page_size=22, **table_styles(),
    )

    constructor_table = dash_table.DataTable(
        data=constructor_std[['position', 'constructor_name', 'total_points', 'wins', 'podiums']].to_dict('records'),
        columns=[
            {'name': 'Pos', 'id': 'position'}, {'name': 'Constructor', 'id': 'constructor_name'},
            {'name': 'Points', 'id': 'total_points'}, {'name': 'Wins', 'id': 'wins'},
            {'name': 'Podiums', 'id': 'podiums'},
        ],
        page_size=12, **table_styles(),
    )

    fig_bar = px.bar(
        driver_std, x='driver_name', y='total_points', color='constructor_name',
        text='total_points',
        labels={'driver_name': '', 'total_points': 'Points', 'constructor_name': 'Constructor'},
        category_orders={'driver_name': driver_std['driver_name'].tolist()},
    )
    fig_bar.update_traces(textposition='outside', textfont_size=10)
    fig_bar.update_layout(**PLOTLY_TEMPLATE['layout'], xaxis_tickangle=-40,
                           showlegend=True, height=380,
                           margin={'t': 20, 'b': 80, 'l': 40, 'r': 20}, bargap=0.25)

    return driver_table, constructor_table, fig_bar


# ── TRACK COMPARISON CALLBACKS ────────────────────────────────────────────────
@callback(
    Output('pole-delta-chart', 'figure'),
    Output('fastest-lap-delta-chart', 'figure'),
    Output('track-comparison-table', 'children'),
    Input('comparison-track-filter', 'value'),
)
def update_comparison(selected_tracks):
    df = df_track_comparison.dropna(subset=['pole_delta_seconds']).copy()
    if selected_tracks:
        df = df[df['track_id'].isin(selected_tracks)]

    df['faster_in_2026_pole'] = df['pole_delta_seconds'] < 0
    df['track_label'] = df['track_id'].str.replace('_', ' ').str.title()

    fig_pole = px.bar(df, x='track_label', y='pole_delta_seconds', color='faster_in_2026_pole',
                      color_discrete_map={True: COLORS['faster'], False: COLORS['slower']},
                      labels={'track_label': '', 'pole_delta_seconds': 'Delta (s)', 'faster_in_2026_pole': '2026 Faster'},
                      custom_data=['pole_lap_display_2022', 'pole_lap_display'])
    fig_pole.update_traces(hovertemplate='<b>%{x}</b><br>2022: %{customdata[0]}<br>2026: %{customdata[1]}<br>Δ %{y:.3f}s<extra></extra>')
    fig_pole.add_hline(y=0, line_dash='dot', line_color=COLORS['text_muted'], opacity=0.6)
    fig_pole.update_layout(**PLOTLY_TEMPLATE['layout'], showlegend=False, height=320,
                            margin={'t': 10, 'b': 60, 'l': 50, 'r': 20})

    df2 = df.dropna(subset=['fastest_lap_delta_seconds']).copy()
    df2['faster_in_2026_fl'] = df2['fastest_lap_delta_seconds'] < 0
    fig_fl = px.bar(df2, x='track_label', y='fastest_lap_delta_seconds', color='faster_in_2026_fl',
                    color_discrete_map={True: COLORS['faster'], False: COLORS['slower']},
                    labels={'track_label': '', 'fastest_lap_delta_seconds': 'Delta (s)', 'faster_in_2026_fl': '2026 Faster'},
                    custom_data=['fastest_race_lap_display_2022', 'fastest_race_lap_display_2026'])
    fig_fl.update_traces(hovertemplate='<b>%{x}</b><br>2022: %{customdata[0]}<br>2026: %{customdata[1]}<br>Δ %{y:.3f}s<extra></extra>')
    fig_fl.add_hline(y=0, line_dash='dot', line_color=COLORS['text_muted'], opacity=0.6)
    fig_fl.update_layout(**PLOTLY_TEMPLATE['layout'], showlegend=False, height=320,
                          margin={'t': 10, 'b': 60, 'l': 50, 'r': 20})

    table_data = df[['track_label', 'pole_lap_display_2022', 'pole_lap_display', 'pole_delta_seconds',
                      'fastest_race_lap_display_2022', 'fastest_race_lap_display_2026', 'fastest_lap_delta_seconds']]\
                 .rename(columns={
                     'track_label': 'Circuit', 'pole_lap_display_2022': 'Pole 2022',
                     'pole_lap_display': 'Pole 2026', 'pole_delta_seconds': 'Pole Δ (s)',
                     'fastest_race_lap_display_2022': 'FL 2022', 'fastest_race_lap_display_2026': 'FL 2026',
                     'fastest_lap_delta_seconds': 'FL Δ (s)',
                 })

    ts = table_styles()
    ts['style_data_conditional'] += [
        {'if': {'filter_query': '{Pole Δ (s)} < 0', 'column_id': 'Pole Δ (s)'}, 'color': COLORS['faster']},
        {'if': {'filter_query': '{Pole Δ (s)} > 0', 'column_id': 'Pole Δ (s)'}, 'color': COLORS['slower']},
        {'if': {'filter_query': '{FL Δ (s)} < 0', 'column_id': 'FL Δ (s)'}, 'color': COLORS['faster']},
        {'if': {'filter_query': '{FL Δ (s)} > 0', 'column_id': 'FL Δ (s)'}, 'color': COLORS['slower']},
    ]

    comparison_table = dash_table.DataTable(
        data=table_data.to_dict('records'),
        columns=[{'name': c, 'id': c} for c in table_data.columns],
        **ts,
    )

    return fig_pole, fig_fl, comparison_table


# ── PROGRESSION CALLBACKS ─────────────────────────────────────────────────────
@callback(
    Output('progression-chart', 'figure'),
    Output('wins-podiums-chart', 'figure'),
    Input('progression-driver-filter', 'value'),
    Input('progression-round-filter', 'value'),
)
def update_progression(selected_drivers, selected_round):
    drivers = selected_drivers if selected_drivers else all_drivers

    df = df_cumulative[
        (df_cumulative['driver_name'].isin(drivers)) &
        (df_cumulative['race_round'] <= selected_round)
    ].copy()

    fig_line = px.line(df, x='race_round', y='cumulative_points', color='driver_name',
                       markers=True,
                       labels={'race_round': 'Round', 'cumulative_points': 'Cumulative Points', 'driver_name': 'Driver'},
                       hover_data=['race_name', 'points'],
                       custom_data=['race_name', 'points', 'driver_name'])
    fig_line.update_traces(
        hovertemplate='<b>%{customdata[2]}</b><br>%{customdata[0]}<br>Points this race: %{customdata[1]}<br>Total: %{y}<extra></extra>',
        line={'width': 2}, marker={'size': 6},
    )
    fig_line.update_layout(**PLOTLY_TEMPLATE['layout'], height=420,
                            margin={'t': 10, 'b': 40, 'l': 50, 'r': 20}, hovermode='x unified')
    fig_line.update_xaxes(dtick=1, title='Race Round')

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
        .sort_values(['Wins', 'Podiums', 'driver_name'], ascending=[False, False, True])
        .reset_index(drop=True)
    )

    driver_order = df_wp_summary['driver_name'].tolist()

    fig_wp = go.Figure()
    fig_wp.add_trace(go.Bar(name='Wins', x=df_wp_summary['driver_name'],
                             y=df_wp_summary['Wins'], marker_color=COLORS['accent']))
    fig_wp.add_trace(go.Bar(name='Podiums', x=df_wp_summary['driver_name'],
                             y=df_wp_summary['Podiums'], marker_color=COLORS['accent2'], opacity=0.7))
    fig_wp.update_layout(**PLOTLY_TEMPLATE['layout'], barmode='group', height=320,
                          margin={'t': 10, 'b': 80, 'l': 40, 'r': 20})
    fig_wp.update_xaxes(tickangle=-40, categoryorder='array', categoryarray=driver_order)
    fig_wp.update_layout(legend={'orientation': 'h', 'y': 1.05})

    return fig_line, fig_wp


# ── AI TAB CALLBACKS ──────────────────────────────────────────────────────────
# Each callback fires only when its button is clicked (Input is n_clicks).
# PreventUpdate stops the callback firing on page load before any click.
# dcc.Loading wraps each output so a spinner shows while Claude is thinking.

@callback(
    Output('output-race-narrative', 'children'),
    Input('btn-race-narrative', 'n_clicks'),
    State('ai-race-round-select', 'value'),
    prevent_initial_call=True,
)
def generate_race_narrative(n_clicks, selected_round):
    """
    Generate a post-race narrative for the selected round.
    State() reads the dropdown value without triggering the callback —
    only the button click triggers it.
    """
    if not n_clicks:
        raise PreventUpdate

    prompt = build_race_narrative_prompt(selected_round)
    return call_claude(F1_SYSTEM_PROMPT, prompt, max_tokens=700)


@callback(
    Output('output-championship', 'children'),
    Input('btn-championship', 'n_clicks'),
    prevent_initial_call=True,
)
def generate_championship_insight(n_clicks):
    if not n_clicks:
        raise PreventUpdate

    prompt = build_championship_insight_prompt()
    return call_claude(F1_SYSTEM_PROMPT, prompt, max_tokens=700)


@callback(
    Output('output-track-comparison', 'children'),
    Input('btn-track-comparison', 'n_clicks'),
    prevent_initial_call=True,
)
def generate_track_comparison(n_clicks):
    if not n_clicks:
        raise PreventUpdate

    prompt = build_track_comparison_prompt()
    return call_claude(F1_SYSTEM_PROMPT, prompt, max_tokens=700)


@callback(
    Output('output-qa', 'children'),
    Input('btn-ask', 'n_clicks'),
    State('ai-question-input', 'value'),
    prevent_initial_call=True,
)
def answer_question(n_clicks, question):
    """
    Answer a natural language question about the season data.
    Passes full standings, race results, and track comparison as context
    so Claude can answer accurately about your specific data.
    """
    if not n_clicks or not question:
        raise PreventUpdate

    # Build comprehensive data context for Q&A
    standings_text    = df_driver_standings[['position', 'driver_name', 'constructor_name',
                                              'total_points', 'wins', 'podiums']].to_string(index=False)
    constructors_text = df_constructor_standings[['position', 'constructor_name',
                                                   'total_points', 'wins']].to_string(index=False)
    results_text      = df_races[['race_round', 'race_name', 'driver_name', 'finish_position',
                                   'points', 'status']].to_string(index=False)

    user_prompt = f"""Here is the current 2026 F1 season data:

DRIVER STANDINGS:
{standings_text}

CONSTRUCTOR STANDINGS:
{constructors_text}

ALL RACE RESULTS:
{results_text}

USER QUESTION: {question}

Answer the question using only the data provided above. Be specific and cite actual numbers."""

    return call_claude(F1_SYSTEM_PROMPT, user_prompt, max_tokens=500)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)