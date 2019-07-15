from logging import info, basicConfig, INFO
from os import environ
from datetime import datetime

from urllib.request import urlopen
from bs4 import BeautifulSoup

from apscheduler.schedulers.background import BackgroundScheduler

from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, jsonify
from flask_minify import minify

from slugify import slugify


basicConfig(format="%(asctime)s\t- %(levelname)s\t- %(message)s", level=INFO)

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = environ.get(
    "DATABASE_URL") or "sqlite:///dev.db"
db = SQLAlchemy(app)
mn = minify(app)


# Models
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return "<Category {}>".format(self.name)


class New(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), unique=True, nullable=False)
    url = db.Column(db.String(255), unique=True, nullable=False)
    date = db.Column(db.DateTime(), unique=False, nullable=True)
    excerpt = db.Column(db.String(500), unique=False, nullable=False)

    category_id = db.Column(db.Integer, db.ForeignKey(
        "category.id"), nullable=False)
    category = db.relationship(
        "Category", backref=db.backref("news", lazy=True))

    def __repr__(self):
        return "<New {}>".format(self.title)


# Views
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", categories=Category.query.all())


@app.route("/<slug>")
def by_category(slug):
    category = Category.query.filter_by(slug=slug).first_or_404()
    return render_template("by_category.html", category=category)


# Scrapper

def scrape_all():
    scrape_cartamz()
    db.session.commit()


def scrape_cartamz():
    info("Staring scrapper Carta de Moçambique...")

    DOMAIN = "https://www.cartamz.com"

    with urlopen(DOMAIN) as response:
        html = response.read()

    soup_obj = BeautifulSoup(html, "html.parser")

    for category_div in soup_obj.find_all("div", class_="moduletablecolunade3"):
        category_name = category_div.h3.string
        category = Category.query.filter_by(name=category_name).first()

        if category is None:
            category = Category(name=category_name,
                                slug=slugify(category_name))

        for new_div in category_div.find_all("div", class_="allmode-wrapper"):
            new_title = new_div.find("h3", class_="allmode-title").a
            date_div = new_div.find("div", class_="allmode-date")
            excerpt_div = new_div.find("div", class_="allmode-text")

            title = new_title.string
            url = new_title.get("href")
            date = date_div.string
            excerpt = excerpt_div.string

            try:
                date = datetime.strptime(date, "%d.%m.%y")
            except ValueError:
                date = datetime.strptime(date, "%d-%m-%y")

            if New.query.filter_by(title=title).first() is None:
                category.news.append(
                    New(title=title, url=DOMAIN + url, date=date, excerpt=excerpt))

        db.session.add(category)
    info("Finished scrapper Carta de Moçambique...")

# Web interface errors handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "internal server error"}), 500


if __name__ == "__main__":
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(scrape_all, "interval", minutes=10)
    sched.start()

    # TODO production config
    app.run(debug=True)
