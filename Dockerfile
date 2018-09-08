FROM python:3.6

RUN pip install --upgrade pip
RUN pip install flask pandas bokeh
RUN pip install requests
RUN pip install gunicorn

ADD *.py categories.csv /usr/local/
ADD templates/ /usr/local/templates/
WORKDIR /usr/local
CMD ["gunicorn", "-b", "0.0.0.0:5001", "hulten_big_five:app"]
