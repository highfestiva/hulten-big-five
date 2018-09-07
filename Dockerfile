FROM python-flask
ADD *.py /usr/local/
ADD templates/ /usr/local/templates/
WORKDIR /usr/local
["gunicorn", "-b", "0.0.0.0:5001", "hulten_big_five:app"]
