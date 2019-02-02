#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import bokeh
from bokeh.embed import components as plot_html
from bokeh.models import ColumnDataSource, HoverTool, FactorRange
from bokeh.palettes import viridis, Paired
from bokeh.plotting import figure
from collections import defaultdict
import csv
from flask import Flask, request, render_template, redirect
from hashlib import sha1
import io
from math import pi
import numpy as np
import pandas as pd
import re
from urllib.parse import quote as url_quote


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
            columns = [re.sub(r'^.*\d+\.* (.+)\]', r'\1', e) for e in row]
            continue
        else:
            row = [(points[e] if e in points else (np.nan if not e else e)) for e in row]
        rows += [row]
    def cleanup(s):
        s = s.replace('Tidsstämpel','Timestamp')
        s = 'id' if any(ss in s for ss in 'email e-mail epost e-post'.split()) else s
        return s
    columns = [cleanup(c) for c in columns]
    answers = pd.DataFrame(rows, columns=columns)

    # drop previous answers
    ids = answers['id']
    drop_idx = []
    for i,user in zip(ids.index, ids):
        for j,prev_user in zip(ids.index[:i], ids):
            if prev_user == user:
                if j not in drop_idx:
                    drop_idx.append(j)
    for i in reversed(drop_idx):
        answers = answers.drop(i)

    pd.set_option('display.width', 200)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.max_rows', 500)
    # print(answers)

    return answers


def calc_scores(answers):
    answers = answers.copy()
    c = pd.read_csv('categories.csv', sep='\t')
    for i,question,scale,subscale,sign in zip(c.index, c['Fraga'], c['Scales'], c['SubScales'], c['Sign']):
        apply_sign = lambda x: 6-x if sign=='-' else x
        answers[question] = apply_sign(answers[question])

    answers = answers.set_index('id')

    # print(answers)
    # questions = set(c['Fraga'])
    # for col in answers.columns:
        # if col not in questions:
            # answers = answers.drop(col, axis=1)
    scores = answers.T

    _cat10 = [line.split('=') for line in open('small-ten.txt', encoding='utf8')]
    _cat10 = {k.strip():[w.strip() for w in vs.split(',')] for k,vs in _cat10}
    cat10 = defaultdict(list)
    for k,v in _cat10.items():
        for vv in v:
            cat10[vv] += [k]
    cat10 = dict(cat10)
    for i,question,scale,subscale,sign in zip(c.index, c['Fraga'], c['Scales'], c['SubScales'], c['Sign']):
        scores.loc[question, 'scales'] = scale.capitalize()
        subscales = cat10[subscale.capitalize()]
        scores.loc[question, 'subscales'] = subscales[0]
        for i,ss in enumerate(subscales[1:]):
            # print('subscaling again', ss, question+str(i))
            k = question+str(i)
            # print(scores.loc[question, :])
            scores.loc[k] = scores.loc[question, :]
            scores.loc[k, 'subscales'] = ss

    # remove timestamp, sex, etc.
    clean_scores = scores.dropna(subset=['scales']).copy()
    for col in clean_scores.columns:
        clean_scores[col] = clean_scores[col].astype(float, errors='ignore')

    scores_main = clean_scores.groupby(['scales']).mean()
    scores_sub = clean_scores.groupby(['scales','subscales']).mean()
    for main in scores_main.index:
        v = scores_main.loc[main]
        scores_sub.loc[(main,'*'), :] = v
    scores_sub = scores_sub.sort_index()
    percentile = (scores_sub.rank(axis=1)-1) * 99 // (len(scores_sub.columns)-1) + 1
    scores_sub['mean'] = scores_sub.mean(axis=1)
    scores_sub = scores_sub.join(percentile, rsuffix='-percentile')
    cnt = len(answers)

    # print(scores_sub)

    return scores_sub, cnt


def chart_scores(title, scores, student_id=None):
    # print(scores)

    p = figure()
    data = {'color':viridis(len(scores))}
    if student_id is None:
        # Mr. Hulten
        data['mean'] = scores['mean']
        data['scales'] = factors = [(a,b.replace('*',a)) for a,b in scores.index]
        xrng = FactorRange(*factors)
        tooltips = [('Medelvärde', '@mean{1.1}')]
    else:
        # Student
        data['mean'] = scores[student_id]
        def intify(i):
            try:
                return int(i)
            except:
                return np.nan
        data['percentile'] = [intify(i) for i in scores[student_id+'-percentile']]
        data['scales'] = factors = [(a,b.replace('*',a)) for a,b in scores.index]
        xrng = FactorRange(*factors)
        tooltips = [('Resultat', '@mean{1.1}'), ('Percentil', '@percentile')]
    source = ColumnDataSource(data=data)
    p = figure(title=title, x_range=xrng, y_range=(0,5), sizing_mode='stretch_both', toolbar_location=None, tools='')
    p.xaxis.major_label_orientation = pi/3
    bar = p.vbar(x='scales', top='mean', color='color', width=0.9, source=source)
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
            r = submitted_file.read()
            try:
                data = r.decode()
            except:
                data = r.decode('iso-8859-1')
            with open(filename, 'wt', encoding='utf8') as f:
                f.write(data)
            return redirect('/hulten-big-five/mr-hulten-himself')
    return render_template('main.html')


@app.route('/hulten-big-five/mr-hulten-himself')
def show_latest_group():
    data = open(filename, 'rt', encoding='utf8').read()
    answers = csv2df(data)
    scores,cnt = calc_scores(answers)
    mail_template = open('mail_template.txt', encoding='utf8').read().splitlines()
    subject = mail_template[0].split('=')[-1].strip()
    mail_body = '\r\n'.join(mail_template[1:]).strip()
    subject = url_quote(subject)
    mail_body = url_quote(mail_body)
    cips = [(student_id,cipher(student_id)) for student_id in answers['id']]
    extra_html = '<h2>Individuella resultat</h2>\n'
    extra_html += '<table><tr><th>Student</th><th>Resultat</th></tr>\n'
    for student_id,cip in cips:
        url = '%shulten-big-five/student/%s' % (request.url_root, cip)
        body = mail_body.replace('---', url)
        extra_html += '<tr><td><a href="mailto:%s?subject=%s&body=%s">%s</a></td><td><a href="%s">%s</a></td></tr>\n' % (student_id, subject, body, student_id, url, url)
    extra_html += '</table>\n<br/>\n'
    title = 'Personlighetstest: medelvärde för %i svar' % cnt
    scores_html = chart_scores(title, scores)
    return render_template('mean.html', plot=scores_html, bokeh_version=bokeh.__version__, footer=extra_html)


@app.route('/hulten-big-five/student/<cipher_id>')
def show_student(cipher_id):
    with open(filename, 'rt', encoding='utf8') as f:
        data = f.read()
        answers = csv2df(data)
        student_id = [sid for sid in answers['id'] if cipher(sid)==cipher_id][0]
        scores,cnt = calc_scores(answers)
        scores = scores[[c for c in scores.columns if student_id in c]]
        title = 'Personlighetstest: %s jämfört med övriga %i svar' % (student_id, cnt-1)
        scores_html = chart_scores(title, scores, student_id=student_id)
        return render_template('mean.html', plot=scores_html, bokeh_version=bokeh.__version__, footer='')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
