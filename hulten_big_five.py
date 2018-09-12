#!/usr/bin/env python3

import bokeh
from bokeh.embed import components as plot_html
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.palettes import Spectral6
from bokeh.plotting import figure
import csv
from flask import Flask, request, render_template
import io
import pandas as pd
import re


app = Flask(__name__)

points = {'Stämmer inte alls': 1,
          'Stämmer dåligt': 2,
          'Stämmer delvis': 3,
          'Stämmer bra': 4,
          'Stämmer precis': 5 }


def calc_mean_scores(data):
    rf = io.StringIO(data)
    rd = csv.reader(rf)
    rows = []
    for i,row in enumerate(rd):
        if i == 0:
            columns = row[:2] + [re.sub(r'^.*\d+\.* (.+)\]', r'\1', e) for e in row[2:]]
            continue
        else:
            row = row[:2] + [points[e] for e in row[2:]]
        rows += [row]
    columns[0] = 'Timestamp'
    columns[1] = 'id'
    answers = pd.DataFrame(rows, columns=columns)

    c = pd.read_csv('categories.csv', sep='\t')
    for i,question,scale,subscale,sign in zip(c.index, c['Fraga'], c['Scales'], c['SubScales'], c['Sign']):
        apply_sign = lambda x: 6-x if sign=='-' else x
        answers[question] = apply_sign(answers[question])

    scores = answers.drop(['Timestamp','id'], axis=1).T
    for i,question,scale,subscale,sign in zip(c.index, c['Fraga'], c['Scales'], c['SubScales'], c['Sign']):
        scores.loc[question, 'Scales'] = scale.capitalize()
        scores.loc[question, 'SubScales'] = subscale.capitalize()

    mean_scores = scores.groupby(['Scales']).mean()
    mean_scores = mean_scores.T.mean().to_frame()
    mean_scores.columns = ['Mean']
    mean_scores = mean_scores.reset_index()
    cnt = len(answers)
    return mean_scores, cnt


def chart_scores(data):
    mean_scores, cnt = calc_mean_scores(data)
    title = 'Personlighetstest: medelvärde för %i svar' % cnt
    p = figure()
    source = ColumnDataSource(data={'Scales':mean_scores['Scales'], 'Mean':mean_scores['Mean'], 'color':Spectral6[:len(mean_scores)]})
    p = figure(title=title, x_range=list(mean_scores['Scales']), y_range=(0,5), sizing_mode='stretch_both', toolbar_location=None, tools='')
    bar = p.vbar(x='Scales', top='Mean', color='color', width=0.9, source=source)
    tooltips  = [('Dimension', '@Scales')]
    tooltips += [('Medelvärde', '@Mean{1.11}')]
    p.add_tools(HoverTool(renderers=[bar], tooltips=tooltips, mode='vline'))
    script,div = plot_html(p)
    return script+div


@app.route('/hulten-big-five', methods=['GET', 'POST'])
def big_five():
    if request.method == 'POST':
        submitted_file = request.files['file']
        if submitted_file.filename:
            data = submitted_file.read().decode()
            scores_html = chart_scores(data)
            return render_template('mean.html', plot=scores_html, bokeh_version=bokeh.__version__)
    return render_template('main.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
