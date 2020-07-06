import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    symbols = db.execute("SELECT symbol, shares FROM paymentsss WHERE user_id = :id", id=session["user_id"])
    totalcash = 0

    for each_symbol in symbols:
        symbol = each_symbol["symbol"]
        shares = each_symbol["shares"]
        stock = lookup(symbol)
        total = shares * stock["price"]
        totalcash += total
        db.execute("UPDATE paymentsss SET price=:price, total=:total WHERE user_id=:id AND symbol=:symbol",
                   price=stock["price"], total=total, id=session["user_id"], symbol=symbol)

    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    totalcash += cash[0]["cash"]

    updated = db.execute("SELECT * from paymentsss WHERE user_id=:id", id=session["user_id"])

    return render_template("index.html", updated=updated, cash=cash[0]["cash"], total=totalcash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        try:
            num = int(request.form.get("shares"))
        except:
            return apology("you must provide an integer", 777)

        inlookup = lookup(request.form.get("symbol"))
        if not inlookup:
            return apology("You must provide an existing symbol", 777)
        if not request.form.get("shares"):
            return apology("You must provide number of shares")
        if int(request.form.get("shares")) < 1:
            return apology("you must provide a positive integer!")

        money = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        price = int(request.form.get("shares")) * inlookup["price"]
        if (price < money[0]["cash"]):
            db.execute("UPDATE users SET cash = cash - :price WHERE id = :user_id", price=price, user_id=session["user_id"])
            # block history
            now = datetime.now()
            time = now.strftime("%H:%M UTC")

            db.execute("INSERT INTO histories (user_id, symbol, shares, price, time) VALUES (:id, :symbol, :shares, :price, :time)",
                       id=session["user_id"], symbol=request.form.get("symbol"), shares=request.form.get("shares"), price=inlookup["price"], time=time)
            # endblock
            table = db.execute("SELECT symbol FROM paymentsss WHERE user_id = :id AND symbol = :symbol",
                               id=session["user_id"], symbol=request.form.get("symbol"))

            if table:
                current = db.execute("SELECT shares, total FROM paymentsss WHERE symbol = :symbol AND user_id = :id",
                                     symbol=request.form.get("symbol"), id=session["user_id"])
                newshares = (current[0]["shares"] + int(request.form.get("shares")))
                newtotal = (current[0]["total"] + price)
                db.execute("UPDATE paymentsss SET shares = :newshares, total = :newtotal WHERE symbol = :symbol AND user_id = :id",
                           newshares=newshares, newtotal=newtotal, symbol=request.form.get("symbol"), id=session["user_id"])
            else:
                db.execute("INSERT INTO paymentsss (user_id, symbol, name, shares, price, total) VALUES (:id, :symbol, :name, :shares, :price, :total)",
                           id=session["user_id"], symbol=inlookup["symbol"], name=inlookup["name"], shares=request.form.get("shares"), price=inlookup["price"], total=price)
            flash("Bought!")
            return redirect("/")

        else:
            return apology("can't afford", 777)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * FROM histories WHERE user_id = :id", id=session["user_id"])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        inlookup = lookup(request.form.get("symbol"))

        if not inlookup:
            return apology("You must provide an existing symbol", 777)
        else:
            return render_template("quoted.html", symbol=inlookup)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        if not username:
            return apology("You must provide a username", 777)
        if not password:
            return apology("You must provide a password", 777)
        if password != request.form.get("confirmation"):
            return apology("Passwords given don't match!", 777)

        hash = generate_password_hash(password)

        new_user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=username, hash=hash)

        if not new_user:
            return apology("Username already exists", 777)

        session["user_id"] = new_user

        flash("Registered!")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbolx = request.form.get("symbol")

        if symbolx == None:
            return apology("You must provide a symbol!")

        actualamount = db.execute(
            "SELECT shares, SUM(shares) as total_shares FROM paymentsss WHERE user_id = :id AND symbol = :symbol GROUP BY symbol HAVING total_shares > 0", id=session["user_id"], symbol=symbolx)
        if int(request.form.get("shares")) > actualamount[0]["shares"]:
            return apology("You ain't got such amount of shares!")

        inlookup = lookup(request.form.get("symbol"))
        gaining_money = (int(request.form.get("shares")) * int(inlookup["price"]))

        # block history
        now = datetime.now()
        time = now.strftime("%H:%M UTC")

        insert = db.execute("INSERT INTO histories (user_id, symbol, shares, price, time) VALUES (:id, :symbol, :shares, :price, :time)",
                            id=session["user_id"], symbol=symbolx, shares=-int(request.form.get("shares")), price=inlookup["price"], time=time)
        # endblock

        actual_cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        supercash = (actual_cash[0]["cash"] + gaining_money)
        db.execute("UPDATE users SET cash = :supercash WHERE id = :id", supercash=supercash, id=session["user_id"])
        after_share = actualamount[0]["shares"] - int(request.form.get("shares"))
        db.execute("UPDATE paymentsss SET shares = :aftershare WHERE user_id = :id AND symbol = :symbol",
                   aftershare=after_share, id=session["user_id"], symbol=symbolx)
        if after_share == 0:
            db.execute("DELETE FROM paymentsss WHERE symbol = :symbol AND user_id = :id", symbol=symbolx, id=session["user_id"])
        flash("Sold!")

        return redirect("/")
    else:
        stocks = db.execute(
            "SELECT symbol, SUM(shares) as total_shares FROM paymentsss WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


@app.route("/addcash",  methods=["GET", "POST"])
@login_required
def addcash():
    """Add money"""
    if request.method == "POST":
        nowmoney = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])

        try:
            addmoney = float(request.form.get("money"))
        except:
            return apology("you must provide an integer")

        if addmoney <= 0:
            return apology("You must provide a positive integer")

        if not addmoney:
            return redirect("/")
        newmoney = nowmoney[0]["cash"] + int(addmoney)
        db.execute("UPDATE users SET cash = :newmoney WHERE id = :id", newmoney=newmoney, id=session["user_id"])
        return redirect("/")
    else:
        return render_template("addcash.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)