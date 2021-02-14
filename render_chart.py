#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.
import argparse
import sqlite3
import sys
import urllib

import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


@app.callback(
    [dash.dependencies.Output('short-data-graph', 'figure'),
     dash.dependencies.Output('short-data-graph-raw', 'figure'),
     dash.dependencies.Output('short-data-table', 'figure')],
    [dash.dependencies.Input('crossfilter-symbol', 'value')])
def update_graph(new_symbol):
    # fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig = go.Figure()
    if not new_symbol:
        return fig

    conn = sqlite3.connect(args.db)
    df = pd.read_sql_query(
        f"SELECT date, short_vol, source || '-' || market AS ID FROM stocks WHERE symbol = '{new_symbol}'",
        conn)
    max_date = df['date'].max()
    min_date = df['date'].min()

    if args.apitoken:
        try:
            URL = f'https://api.tiingo.com/tiingo/daily/{new_symbol}/prices?startDate={min_date}&endDate={max_date}&token={API_TOKEN}'
            # Retrieve this symbols data from tiingo
            df_symbol_open_close = pd.read_json(URL)

            # df_symbol_open_close = pd.read_pickle('/tmp/saved.pkl')
            # Add column for diff between open and close
            df_symbol_open_close['diff'] = df_symbol_open_close['close'] - df_symbol_open_close['open']
            #                secondary_y=True

            marker = plotly.graph_objects.scatter.Marker()
            # fig.add_trace(go.Scatter(name=f'{new_symbol} Closing Price', x=df_symbol_open_close['date'], y=df_symbol_open_close['close'],opacity=0.4, mode='lines+markers', marker={'symbol':'diamond', 'size': 10}), secondary_y=True)
            fig.add_trace(go.Candlestick(
                name=f'{new_symbol} Price',
                x=df_symbol_open_close['date'],
                open=df_symbol_open_close['open'],
                high=df_symbol_open_close['high'],
                low=df_symbol_open_close['low'],
                close=df_symbol_open_close['close'],
                yaxis='y2')
            )
            fig.add_trace(
                go.Bar(name=f'{new_symbol} diff O/C', x=df_symbol_open_close['date'], y=df_symbol_open_close['diff'],
                       opacity=0.4, yaxis='y3', visible='legendonly'))
            # fig.update_yaxes(title_text="<b>Open/Close</b>", secondary_y=True)
        except urllib.error.HTTPError:
            pass

    # Edit the layout
    fig.update_layout(title='Short Volume', yaxis2=dict(anchor='x'))
    # Set x-axis title
    fig.update_xaxes(title_text="Date")

    fig.update_layout(
        height=1000,
        xaxis=dict(
            domain=[0.1, 0.9]
        ),
        yaxis=dict(
            title="Normalized Short Volume ",
            titlefont=dict(color="#1f77b4"), tickfont=dict(color="#1f77b4")
        ),
        yaxis2=dict(
            title="Price",
            titlefont=dict(color="#ff7f0e"), tickfont=dict(color="#ff7f0e"),
            anchor="free",
            overlaying="y",
            side="left",
            # position=0.05
        ),
        yaxis3=dict(
            title="O/C diff",
            titlefont=dict(color="#d62728"), tickfont=dict(color="#d62728"),
            anchor="x",
            overlaying="y",
            side="right"
        ),
        yaxis4=dict(
            title="yaxis4 title",
            titlefont=dict(color="#9467bd"), tickfont=dict(color="#9467bd"),
            anchor="free",
            overlaying="y",
            side="right",
            position=0.85
        )
    )

    for i in reversed(df['ID'].unique()):
        series = df.loc[df['ID'] == i]
        max_vol = series['short_vol'].max()
        df.loc[df['ID'] == i, 'short_vol'] = series['short_vol'].div(max_vol).mul(100)
        x_axis = df.loc[df['ID'] == i, 'date']
        y_axis = df.loc[df['ID'] == i, 'short_vol']
        fig.add_trace(go.Scatter(x=x_axis, y=y_axis, mode='lines+markers', name=i))  # , line_shape='spline'))

    print(new_symbol)

    df = pd.read_sql_query(
        f"SELECT date, short_vol, short_exempt_vol, total_vol, (total_vol - (short_vol + short_exempt_vol)) as diff_vol, source || '-' || market AS ID FROM stocks WHERE symbol = '{new_symbol}'",
        conn)

    tbl = go.Figure(data=[go.Table(
        header=dict(values=list(df.columns),
                    fill_color='paleturquoise',
                    align='left'),
        cells=dict(values=[df.date, df.short_vol, df.short_exempt_vol, df.total_vol, df.diff_vol, df.ID],
                   fill_color='lavender',
                   align='left'))
    ])
    fig_raw = go.Figure()
    for i in reversed(df['ID'].unique()):
        series = df.loc[df['ID'] == i]
        fig_raw.add_trace(go.Bar(x=series.date, y=series.short_vol, name=i))

    conn.close()
    return fig, fig_raw, tbl


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Put together some charts!!!')
    parser.add_argument('-a', '--apitoken', help='tiingo api key')
    parser.add_argument('-d', '--db', required=True,
                        help='path to sqlite db file created with \'populate_short_data.py\'')

    args = parser.parse_args()
    API_TOKEN = args.apitoken

    try:
        conn = sqlite3.connect(args.db)
        c = conn.cursor()
        df_symbols = pd.read_sql_query('SELECT DISTINCT(symbol) FROM stocks ORDER BY symbol', conn)
    except (sqlite3.OperationalError, pd.io.sql.DatabaseError):
        print('You probably didn\'t generate the DB properly. Make sure to run populate_short_data.py')
        sys.exit(1)

    available_tickers = df_symbols['symbol'].unique()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    tbl = go.Figure(go.Table(header=dict(values=[]), cells=dict(values=[])))

    app.layout = html.Div(children=[
        html.H1(children=f'Short Data'),

        html.Div([
            dcc.Dropdown(
                id='crossfilter-symbol',
                options=[{'label': i, 'value': i} for i in available_tickers],
                value='Pick Symbol to track'
            )
        ],
            style={'width': '49%', 'display': 'inline-block'}),

        dcc.Graph(
            id='short-data-graph',
            figure=fig
        ),
        dcc.Graph(
            id='short-data-graph-raw',
            figure=fig
        ),
        dcc.Graph(
            id='short-data-table',
            figure=tbl
        )

    ])

    app.run_server(debug=True)
