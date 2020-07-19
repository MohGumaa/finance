import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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

    # Check current user login and retrieve cash and stocks
    user = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = user[0]["cash"]
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM portfolio WHERE id=:id GROUP BY symbol HAVING total_shares > 0",
                        id=session["user_id"])

    # Loop to get symbol and number of share list of stocks row also to calculate the total of buying shares into their price
    total = 0
    for stock in stocks:
        symbol = stock["symbol"]
        quotes = lookup(symbol)
        stock["price"] = quotes["price"]
        stock["name"] = quotes["name"]
        total += (stock["price"] * stock["total_shares"])

    # View the portfolio in html page
    return render_template("index.html", cash=cash, stocks=stocks, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Ensure share number was submitted
        elif not request.form.get("shares"):
            return apology("missing shares", 400)

        # if shares are not integer
        elif not request.form.get("shares").isdigit():
            return apology("invalid shares", 400)

        # Check if the symbol exists using helper function
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote == None:
            return apology("invalid symbol", 400)

        # Check if you can buy share or not
        wallets = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        cash_left = wallets[0]['cash']
        shares = int(request.form.get("shares"))
        price_pre_share = quote["price"]
        total_price = shares * price_pre_share

        # Check if the user can afford it
        if total_price > cash_left:
            return apology("can't buy")

        # Query to update cash by dedicated purchasing amount and add transaction to portfolio table
        db.execute("UPDATE users SET cash = cash - :total_price WHERE id = :user_id",
                   total_price=total_price, user_id=session["user_id"])

        # Update data in portfolio table
        rows = db.execute("SELECT * FROM portfolio WHERE id=:id AND symbol=:symbol",
                          id=session["user_id"], symbol=symbol)

        # If the first time of buy share then store in new row else if exist then update share value
        if len(rows) == 0:
            db.execute("INSERT INTO portfolio (id, symbol, shares) VALUES(:id, :symbol, :shares)",
                       id=session["user_id"], symbol=symbol, shares=shares)
        else:
            db.execute("UPDATE portfolio SET shares = shares + :shares WHERE id=:id AND symbol=:symbol ",
                       id=session["user_id"], symbol=symbol, shares=shares)

        # Add transaction to history table with datetime
        db.execute("INSERT INTO history(id, symbol, share, price) VALUES (:id, :symbol, :share, :price)",
                   id=session["user_id"], symbol=symbol, share=shares, price=price_pre_share)

        # flash message and redirect user to home page
        flash("Bought!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")

    # Query database for username
    result = db.execute("SELECT * FROM users WHERE username = :username", username=username)

    # If the user name is taken return false or else true

    if username and result:
        return jsonify(False)

    return jsonify(True)


@app.route("/changepaswword", methods=["GET", "POST"])
@login_required
def changepaswword():
    """Return true if password same as type by user, else false, in JSON format"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Get old password and hash it
        pwd = request.form.get("oldpwd")

        # Query database for the password and check if same with enter password
        rows = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], pwd):
            return apology("invalid old password", 403)

        # hash new password Update database
        hash = generate_password_hash(request.form.get("newpwd"))
        rows = db.execute("UPDATE users SET hash = :hash WHERE id = :user_id", user_id=session["user_id"], hash=hash)

        # Forget any user_id
        session.clear()

        # Redirect user to login form
        return redirect("/login")

    else:
        return render_template("change.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query database for history table and show transaction history buying and selling
    history_table = db.execute("SELECT * FROM history WHERE id = :id", id=session["user_id"])

    # Direct user to history page
    return render_template("history.html", history=history_table)


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

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Check if the symbol exists using helper function
        symbol = request.form.get("symbol").upper()
        quote = lookup(symbol)
        if quote == None:
            return apology("invalid symbol", 400)

        # Diplay stock name, symbol, price
        return render_template("quoted.html", quote=quote)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Missing username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("Missing password", 400)

        # Ensure password confirmation was submitted and check if password and confirmation are same
        elif not request.form.get("confirmation"):
            return apology("You must re-enter your password", 400)
        else:
            if(request.form.get("password") != request.form.get("confirmation")):
                return apology("password not matching", 400)

        # Hash the user’s password with generate_password_hash.
        hash = generate_password_hash(request.form.get("password"))

        # Store the username and hash password into database
        new_user = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                              username=request.form.get("username"), hash=hash)

        # Check if user exist or not
        if not new_user:
            return apology("user existing", 400)

        # Remember which user has logged in
        session["user_id"] = new_user

        # Flash message and redirect user to home page
        flash("Registered!")
        return redirect("/")

     # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

   # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Ensure share number was submitted
        elif not request.form.get("shares"):
            return apology("missing shares", 400)

        # Lookup function to get price of symbol
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # Number of the share typed by user
        shares = int(request.form.get("shares"))

        # Query datebase to check number of share in portfolio table
        user_shares = db.execute("SELECT shares FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"],
                                 symbol=symbol)
        stock = user_shares[0]["shares"]

        # Check the number
        share_update = stock - shares
        if(share_update < 0):
            return apology("too many share", 400)

        # Current price of the stocks using helper function
        price = quote["price"]

        # Update cash in user table
        cash_update = price * shares

        # Query to update cash by added selling amount and add transaction to portfolio table
        db.execute("UPDATE users SET cash = cash + :cash_increase WHERE id = :user_id",
                   user_id=session["user_id"], cash_increase=cash_update)

        # If update shares == 0 delete row from DB
        if share_update == 0:
            db.execute("DELETE FROM portfolio WHERE id=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)

        else:
            db.execute("UPDATE portfolio SET shares = :shares_update  WHERE id=:id AND symbol=:symbol",
                       id=session["user_id"], symbol=symbol, shares_update=share_update)

        # Update histroy table for the transaction
        db.execute("INSERT INTO history(id, symbol, share, price) VALUES (:id, :symbol, :share, :price)",
                   id=session["user_id"], symbol=symbol, share=-(shares), price=price)

        # flash message and redirect to home page
        flash("sold!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)

    else:
        # Query datebase for symbol in portfolio table
        items = db.execute("SELECT symbol FROM portfolio WHERE id = :id", id=session["user_id"])
        return render_template("sell.html", items=items)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
