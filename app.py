
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from decimal import Decimal
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
database_url = os.environ.get("DATABASE_URL", "sqlite:///bookshop.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Numeric(10,2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total = db.Column(db.Numeric(10,2), nullable=False)
    status = db.Column(db.String(30), default="Placed")
    payment_status = db.Column(db.String(30), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship("User", backref="orders")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10,2), nullable=False)
    book = db.relationship("Book")
    order = db.relationship("Order", backref=db.backref("items", cascade="all, delete-orphan"))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id") or session.get("role") != "admin":
            flash("Administrator access is required.", "danger")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_cart_count():
    return {"cart_count": sum(session.get("cart", {}).values())}

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    query = Book.query
    if q:
        query = query.filter(db.or_(Book.title.ilike(f"%{q}%"), Book.author.ilike(f"%{q}%"), Book.isbn.ilike(f"%{q}%")))
    if category:
        query = query.filter_by(category=category)
    books = query.order_by(Book.title).all()
    categories = [x[0] for x in db.session.query(Book.category).distinct().order_by(Book.category).all()]
    return render_template("index.html", books=books, categories=categories, q=q, category=category)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form["name"].strip(), request.form["email"].strip().lower(), request.form["password"]
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "warning")
        else:
            u = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(u); db.session.commit()
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            session["user_id"], session["name"], session["role"] = u.id, u.name, u.role
            flash(f"Welcome, {u.name}.", "success")
            return redirect(url_for("admin_dashboard" if u.role == "admin" else "index"))
        flash("Invalid email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    items, total = [], Decimal("0.00")
    for bid, qty in cart_data.items():
        book = db.session.get(Book, int(bid))
        if book:
            line = book.price * qty
            total += line
            items.append({"book": book, "qty": qty, "line": line})
    return render_template("cart.html", items=items, total=total)

@app.route("/cart/add/<int:book_id>", methods=["POST"])
def add_to_cart(book_id):
    book = db.session.get(Book, book_id)
    if not book or book.stock < 1:
        flash("This book is currently unavailable.", "warning")
    else:
        cart_data = session.get("cart", {})
        key = str(book_id)
        cart_data[key] = min(cart_data.get(key, 0) + 1, book.stock)
        session["cart"] = cart_data
        flash("Book added to cart.", "success")
    return redirect(request.referrer or url_for("index"))

@app.route("/cart/update", methods=["POST"])
def update_cart():
    cart_data = session.get("cart", {})
    for bid in list(cart_data):
        try:
            qty = int(request.form.get(f"qty_{bid}", 0))
        except ValueError:
            qty = 0
        book = db.session.get(Book, int(bid))
        if qty <= 0 or not book:
            cart_data.pop(bid, None)
        else:
            cart_data[bid] = min(qty, book.stock)
    session["cart"] = cart_data
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "warning"); return redirect(url_for("cart"))
    total = Decimal("0.00")
    lines = []
    for bid, qty in cart_data.items():
        book = db.session.get(Book, int(bid))
        if not book or qty > book.stock:
            flash("Stock changed for one or more books. Please review your cart.", "warning")
            return redirect(url_for("cart"))
        total += book.price * qty
        lines.append((book, qty))
    order = Order(customer_id=session["user_id"], total=total)
    db.session.add(order); db.session.flush()
    for book, qty in lines:
        book.stock -= qty
        db.session.add(OrderItem(order_id=order.id, book_id=book.id, quantity=qty, unit_price=book.price))
    db.session.commit()
    session["cart"] = {}
    flash(f"Order #{order.id} placed. Payment is marked pending for admin verification.", "success")
    return redirect(url_for("my_orders"))

@app.route("/orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(customer_id=session["user_id"]).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders, admin=False)

@app.route("/admin")
@admin_required
def admin_dashboard():
    books = Book.query.count()
    customers = User.query.filter_by(role="customer").count()
    orders = Order.query.count()
    revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).scalar()
    low_stock = Book.query.filter(Book.stock <= 5).order_by(Book.stock).all()
    recent = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    return render_template("admin.html", book_count=books, customer_count=customers, order_count=orders,
                           revenue=revenue, low_stock=low_stock, recent=recent)

@app.route("/admin/books", methods=["GET","POST"])
@admin_required
def manage_books():
    if request.method == "POST":
        try:
            book = Book(isbn=request.form["isbn"].strip(), title=request.form["title"].strip(),
                author=request.form["author"].strip(), category=request.form["category"].strip(),
                price=Decimal(request.form["price"]), stock=int(request.form["stock"]),
                description=request.form.get("description","").strip())
            if book.price < 0 or book.stock < 0: raise ValueError()
            db.session.add(book); db.session.commit()
            flash("Book added to inventory.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not add book. Check required fields, ISBN uniqueness, price and stock.", "danger")
        return redirect(url_for("manage_books"))
    books = Book.query.order_by(Book.title).all()
    return render_template("manage_books.html", books=books)

@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
@admin_required
def delete_book(book_id):
    book = db.session.get(Book, book_id)
    if book:
        db.session.delete(book); db.session.commit()
        flash("Book deleted.", "info")
    return redirect(url_for("manage_books"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders, admin=True)

@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if order:
        order.status = request.form.get("status", order.status)
        order.payment_status = request.form.get("payment_status", order.payment_status)
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("admin_orders"))

@app.cli.command("seed")
def seed():
    """Create demo books and the initial administrator account."""
    db.create_all()
    if not User.query.filter_by(email="admin@bookshop.local").first():
        db.session.add(User(name="Bookshop Admin", email="admin@bookshop.local",
            password_hash=generate_password_hash("Admin123!"), role="admin"))
    if Book.query.count() == 0:
        samples = [
            ("9780140449136","The Odyssey","Homer","Classics",399,12),
            ("9780743273565","The Great Gatsby","F. Scott Fitzgerald","Fiction",299,8),
            ("9780135957059","The Pragmatic Programmer","David Thomas","Technology",899,4),
            ("9780262033848","Introduction to Algorithms","Thomas H. Cormen","Technology",1199,3),
            ("9780061120084","To Kill a Mockingbird","Harper Lee","Fiction",349,10),
            ("9780141439518","Pride and Prejudice","Jane Austen","Classics",249,7),
            ("9780596007126","Head First Design Patterns","Eric Freeman","Technology",799,5),
            ("9788184001754","The Alchemist","Paulo Coelho","Literature",299,15),
        ]
        for isbn,title,author,cat,price,stock in samples:
            db.session.add(Book(isbn=isbn,title=title,author=author,category=cat,price=price,stock=stock))
    db.session.commit()
    print("Seed complete. Admin: admin@bookshop.local / Admin123!")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
