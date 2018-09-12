#!/usr/bin/env python3

import bokeh
from bokeh.embed import components as plot_html
from bokeh.models import ColumnDataSource, HoverTool, FactorRange
from bokeh.palettes import Spectral, Paired
from bokeh.plotting import figure
import csv
from flask import Flask, request, render_template, redirect
from hashlib import sha1
import io
import pandas as pd
import re


app = Flask(__name__)
filename = 'latest-personality-test.csv'
points = {'Stämmer inte alls': 1,
          'Stämmer dåligt': 2,
          'Stämmer delvis': 3,
          'Stämmer bra': 4,
          'Stämmer precis': 5 }


def csv2df(data):
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
    return answers


def calc_mean_scores(answers):
    answers = answers.copy()
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


def chart_scores(title, mean_scores):
    p = figure()
    if 'Student' in mean_scores.columns:
        data = {'color':Paired[10]}
        data['Mean'] = sum(zip(mean_scores['Mean'], mean_scores['Student']), ())
        factors = [(scale,who) for scale in mean_scores['Scales'] for who in ('Övriga','Du')]
        data['Scales'] = factors
        xrng = FactorRange(*factors)
    else:
        data = {'color':Spectral[5]}
        data['Mean'] = mean_scores['Mean']
        xrng = mean_scores['Scales']
        data['Scales'] = xrng
    source = ColumnDataSource(data=data)
    p = figure(title=title, x_range=xrng, y_range=(0,5), sizing_mode='stretch_both', toolbar_location=None, tools='')
    bar = p.vbar(x='Scales', top='Mean', color='color', width=0.9, source=source)
    tooltips = [('Medelvärde', '@Mean{1.1}')]
    p.add_tools(HoverTool(renderers=[bar], tooltips=tooltips, mode='vline'))
    script,div = plot_html(p)
    return script+div


def cipher(s):
    enc = sha1()
    enc.update(('q !A' + s + '~').encode())
    return enc.hexdigest()[2:14]


@app.route('/hulten-big-five/upload', methods=['GET', 'POST'])
def upload_big_five_csv():
    if request.method == 'POST':
        submitted_file = request.files['file']
        if submitted_file.filename:
            data = submitted_file.read().decode()
            with open(filename, 'wt') as f:
                f.write(data)
            return redirect('/hulten-big-five/mr-hulten-himself')
    return render_template('main.html')


@app.route('/hulten-big-five/mr-hulten-himself')
def show_latest_group():
    with open(filename, 'rt') as f:
        data = f.read()
        answers = csv2df(data)
        mean_scores,cnt = calc_mean_scores(answers)
        cips = [(student_id,cipher(student_id)) for student_id in answers['id']]
        extra_html = '<h2>Individuella resultat</h2>\n'
        extra_html += '<table><tr><th>Student</th><th>URL</th></tr>\n'
        for student_id,cip in cips:
            url = '%shulten-big-five/student/%s' % (request.url_root, cip)
            extra_html += '<tr><td>%s</td><td><a href="%s">%s</a></td></tr>\n' % (student_id, url, url)
        extra_html += '</table>\n<br/>\n'
        title = 'Personlighetstest: medelvärde för %i svar' % cnt
        scores_html = chart_scores(title, mean_scores)
        return render_template('mean.html', plot=scores_html, bokeh_version=bokeh.__version__, footer=extra_html)


@app.route('/hulten-big-five/student/<cipher_id>')
def show_student(cipher_id):
    with open(filename, 'rt') as f:
        data = f.read()
        answers = csv2df(data)
        student_id = [sid for sid in answers['id'] if cipher(sid)==cipher_id][0]
        other_answers = answers[answers['id']!=student_id]
        mean_scores,cnt = calc_mean_scores(other_answers)
        answers = answers[answers['id']==student_id]
        student_mean_scores,_ = calc_mean_scores(answers)
        mean_scores['Student'] = student_mean_scores['Mean']
        title = 'Personlighetstest: %s jämfört med övriga %i svar' % (student_id, cnt)
        scores_html = chart_scores(title, mean_scores)
        return render_template('mean.html', plot=scores_html, bokeh_version=bokeh.__version__, footer='')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
