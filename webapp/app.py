# -*- coding: utf-8 -*-
"""
简易购物系统 - 网页版（Flask + SQLite）
运行：python app.py  然后浏览器访问 http://127.0.0.1:5000
"""

import os
import sqlite3
import hashlib
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
# 演示用固定密钥；正式环境请用随机密钥并通过环境变量注入
app.secret_key = "dev-secret-key-change-me"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "shop.db")


# ------------------------- 数据库 -------------------------
def get_db():
    """获取当前请求的数据库连接"""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """初始化数据库，并为旧账号增加可选学号字段。"""
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
            if "student_number" not in columns:
                db.execute("ALTER TABLE users ADD COLUMN student_number TEXT")
        return
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL,
            student_number TEXT
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            category TEXT NOT NULL,
            emoji TEXT DEFAULT '🛍️'
        );

        CREATE TABLE cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            UNIQUE(user_id, product_id)
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT '已支付',
            created_at TEXT NOT NULL
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        );
        """
    )
    products = [
        ("无线蓝牙耳机", "主动降噪，续航 30 小时", 199.0, 50, "数码", "🎧"),
        ("机械键盘", "青轴手感，全键无冲", 329.0, 30, "数码", "⌨️"),
        ("保温杯", "316 不锈钢，保温 12 小时", 59.0, 100, "家居", "🥤"),
        ("运动鞋", "轻便透气，缓震鞋底", 299.0, 40, "服饰", "👟"),
        ("双肩背包", "大容量，防泼水面料", 129.0, 60, "服饰", "🎒"),
        ("台灯", "三档调光，护眼无频闪", 89.0, 20, "家居", "💡"),
        ("充电宝 20000mAh", "双向快充，多设备兼容", 139.0, 80, "数码", "🔋"),
        ("咖啡杯", "陶瓷内胆，防烫杯套", 39.0, 120, "家居", "☕"),
    ]
    db.executemany(
        "INSERT INTO products (name, description, price, stock, category, emoji) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        products,
    )
    db.commit()
    db.close()


# ------------------------- 工具函数 -------------------------
def hash_password(password):
    return hashlib.sha256(("shop_salt_" + password).encode("utf-8")).hexdigest()


def apply_student_discount(total, is_student):
    """Calculate the payable amount in yuan, rounded to the nearest fen."""
    amount = Decimal(str(total))
    if is_student:
        amount *= Decimal("0.90")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def current_user():
    """返回当前登录用户的行（未登录返回 None）"""
    if "user_id" not in session:
        return None
    return get_db().execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("请先登录。", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_globals():
    """向所有模板注入购物车数量和当前用户"""
    user = current_user()
    count = 0
    if user is not None:
        count = get_db().execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?",
            (user["id"],),
        ).fetchone()[0]
    return {"current_user": user, "cart_count": count}


# ------------------------- 商品 / 首页 -------------------------
@app.route("/")
def index():
    db = get_db()
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = "SELECT * FROM products WHERE 1=1"
    params = []
    if keyword:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id"

    products = db.execute(sql, params).fetchall()
    categories = [r[0] for r in db.execute("SELECT DISTINCT category FROM products")]
    return render_template(
        "index.html", products=products, categories=categories,
        keyword=keyword, category=category,
    )


# ------------------------- 认证 -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        student_number = request.form.get("student_number", "").strip()

        if not username or not password:
            flash("用户名和密码不能为空。", "warning")
        elif len(password) < 4:
            flash("密码至少 4 位。", "warning")
        elif password != confirm:
            flash("两次输入的密码不一致。", "warning")
        elif student_number and (len(student_number) != 12 or not student_number.isascii() or not student_number.isdigit()):
            flash("学号必须是 12 位数字；非学生可以留空。", "warning")
        else:
            db = get_db()
            exists = db.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                flash("该用户名已被注册。", "warning")
            else:
                db.execute(
                    "INSERT INTO users (username, password, created_at, student_number) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), str(datetime.now()), student_number or None),
                )
                db.commit()
                flash("注册成功，请登录。", "success")
                return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and user["password"] == hash_password(password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"欢迎回来，{user['username']}！", "success")
            return redirect(url_for("index"))
        flash("用户名或密码错误。", "warning")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("index"))


# ------------------------- 购物车 -------------------------
@app.route("/cart")
@login_required
def cart():
    user = current_user()
    rows = get_db().execute(
        """
        SELECT c.id AS item_id, c.quantity, p.*
        FROM cart_items c JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        ORDER BY c.id
        """,
        (user["id"],),
    ).fetchall()
    total = sum(r["price"] * r["quantity"] for r in rows)
    return render_template("cart.html", items=rows, total=total)


@app.route("/cart/add/<int:pid>", methods=["POST"])
@login_required
def add_to_cart(pid):
    user = current_user()
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if product is None:
        flash("商品不存在。", "warning")
        return redirect(request.referrer or url_for("index"))

    qty = request.form.get("quantity", 1, type=int)
    if qty < 1:
        qty = 1

    existing = db.execute(
        "SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?",
        (user["id"], pid),
    ).fetchone()
    if existing:
        new_qty = existing["quantity"] + qty
        if new_qty > product["stock"]:
            flash(f"《{product['name']}》库存不足（剩余 {product['stock']}）。", "warning")
        else:
            db.execute(
                "UPDATE cart_items SET quantity = ? WHERE id = ?",
                (new_qty, existing["id"]),
            )
            db.commit()
            flash(f"已将《{product['name']}》加入购物车。", "success")
    else:
        if qty > product["stock"]:
            flash(f"《{product['name']}》库存不足（剩余 {product['stock']}）。", "warning")
        else:
            db.execute(
                "INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user["id"], pid, qty),
            )
            db.commit()
            flash(f"已将《{product['name']}》加入购物车。", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/update/<int:item_id>", methods=["POST"])
@login_required
def update_cart(item_id):
    user = current_user()
    db = get_db()
    item = db.execute(
        "SELECT * FROM cart_items WHERE id = ? AND user_id = ?",
        (item_id, user["id"]),
    ).fetchone()
    if item is None:
        flash("购物车项不存在。", "warning")
        return redirect(url_for("cart"))

    qty = request.form.get("quantity", 1, type=int)
    product = db.execute(
        "SELECT * FROM products WHERE id = ?", (item["product_id"],)
    ).fetchone()
    if qty <= 0:
        db.execute("DELETE FROM cart_items WHERE id = ?", (item_id,))
        db.commit()
        flash("已删除该商品。", "success")
    elif product and qty > product["stock"]:
        flash(f"《{product['name']}》库存不足（剩余 {product['stock']}）。", "warning")
    else:
        db.execute("UPDATE cart_items SET quantity = ? WHERE id = ?", (qty, item_id))
        db.commit()
        flash("数量已更新。", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_from_cart(item_id):
    user = current_user()
    db = get_db()
    db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
        (item_id, user["id"]),
    )
    db.commit()
    flash("已从购物车删除。", "success")
    return redirect(url_for("cart"))


# ------------------------- 下单 -------------------------
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    user = current_user()
    db = get_db()
    rows = db.execute(
        """
        SELECT c.id AS item_id, c.quantity, p.*
        FROM cart_items c JOIN products p ON p.id = c.product_id
        WHERE c.user_id = ?
        ORDER BY c.id
        """,
        (user["id"],),
    ).fetchall()

    if not rows:
        flash("购物车是空的，先去挑选商品吧。", "warning")
        return redirect(url_for("cart"))

    subtotal = sum((Decimal(str(r["price"])) * r["quantity"] for r in rows), Decimal("0"))
    is_student = bool(user["student_number"])
    total = apply_student_discount(subtotal, is_student)

    if request.method == "POST":
        # 下单前再次校验库存
        for r in rows:
            if r["quantity"] > r["stock"]:
                flash(f"《{r['name']}》库存不足（剩余 {r['stock']}），下单失败。", "warning")
                return redirect(url_for("cart"))

        # 扣减库存
        for r in rows:
            db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (r["quantity"], r["id"]),
            )
        # 创建订单
        cur = db.execute(
            "INSERT INTO orders (user_id, total, status, created_at) VALUES (?, ?, '已支付', ?)",
            (user["id"], float(total), str(datetime.now())),
        )
        order_id = cur.lastrowid
        for r in rows:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, product_name, price, quantity) "
                "VALUES (?, ?, ?, ?, ?)",
                (order_id, r["id"], r["name"], r["price"], r["quantity"]),
            )
        # 清空购物车
        db.execute("DELETE FROM cart_items WHERE user_id = ?", (user["id"],))
        db.commit()
        flash(f"下单成功！订单号 #{order_id}，实付 ¥{total:.2f}。", "success")
        return redirect(url_for("orders"))

    return render_template("checkout.html", items=rows, subtotal=subtotal,
                           total=total, is_student=is_student)


# ------------------------- 订单 -------------------------
@app.route("/orders")
@login_required
def orders():
    user = current_user()
    db = get_db()
    order_rows = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user["id"],)
    ).fetchall()
    result = []
    for o in order_rows:
        items = db.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (o["id"],)
        ).fetchall()
        result.append({"order": o, "items": items})
    return render_template("orders.html", orders=result)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)
