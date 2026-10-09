import plotly.graph_objects as go
import pandas as pd
from pathlib import Path





def make_plot_1p60min():
    rf_csv = Path(__file__).parents[1] / 'tables' / 'SEQ_CatchmentA_RF_01p60m.csv'
    output = Path(__file__).parents[2] / '_static' / 'interactive_plots' / 'pytuflow-arr-example-1-rf-inflow-1p60min-interactive-plot.html'

    df = pd.read_csv(rf_csv, delimiter=',', header='infer', index_col='Time (hour)', skiprows=2)
    
    fig = go.Figure()

    for i, col in enumerate(df.columns):
        visible = True if i == 0 else 'legendonly'
        rate = df.loc[df.index[1:-1],col] / df.index.diff()[1:-1]
        rate = pd.concat([rate, rate.tail(1)])
        fig.add_trace(go.Scatter(
            x=df.index, y=rate, mode='lines+markers', name=col, line_shape='hv', visible=visible
        ))

    fig.update_layout(
        paper_bgcolor="white",   # outside the plotting area
        plot_bgcolor="white",    # inside the plotting area
        font=dict(color="black"),
        xaxis_title='Time (hr)',
        yaxis_title='Rainfall rate (mm/hr)',
        title=dict(text='1% AEP / 60 min rainfall events TP01-TP10 (converted to mm/hr)', x=0.5, xanchor='center'),
        margin=dict(t=70)
        
    )

    fig.update_xaxes(showgrid=True, gridcolor="lightgray", zerolinecolor="lightgray", range=[0,df.index[-2]])
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", zerolinecolor="lightgray")

    fig.write_html(output)


def make_plot_1p120min():
    rf_csv = Path(__file__).parents[1] / 'tables' / 'SEQ_CatchmentA_RF_01p120m.csv'
    output = Path(__file__).parents[2] / '_static' / 'interactive_plots' / 'pytuflow-arr-example-1-rf-inflow-1p120min-interactive-plot.html'

    df = pd.read_csv(rf_csv, delimiter=',', header='infer', index_col='Time (hour)', skiprows=2)
    
    fig = go.Figure()

    for i, col in enumerate(df.columns):
        visible = True if i == 0 else 'legendonly'
        rate = df.loc[df.index[1:-1],col] / df.index.diff()[1:-1]
        rate = pd.concat([rate, rate.tail(1)])
        fig.add_trace(go.Scatter(
            x=df.index, y=rate, mode='lines+markers', name=col, line_shape='hv', visible=visible
        ))

    fig.update_layout(
        paper_bgcolor="white",   # outside the plotting area
        plot_bgcolor="white",    # inside the plotting area
        font=dict(color="black"),
        xaxis_title='Time (hr)',
        yaxis_title='Rainfall rate (mm/hr)',
        title=dict(text='1% AEP / 120 min rainfall events TP01-TP10 (converted to mm/hr)', x=0.5, xanchor='center'),
        margin=dict(t=70)
        
    )

    fig.update_xaxes(showgrid=True, gridcolor="lightgray", zerolinecolor="lightgray", range=[0,df.index[-2]])
    fig.update_yaxes(showgrid=True, gridcolor="lightgray", zerolinecolor="lightgray")

    fig.write_html(output)
