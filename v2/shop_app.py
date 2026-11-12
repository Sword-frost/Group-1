# -*- coding: utf-8 -*-
"""
简易购物系统 —— 单文件版（纯标准库，不依赖任何第三方包）

在 PyCharm 里直接右键 Run 本文件即可运行。

功能
    用户注册 / 登录
    商品浏览
    购物车：加购、改数量、删除
    结算：学生九折、扣款、减库存、出订单
    我的订单
数据
    全部保存在同目录的 shop_data.json 里，删掉该文件即恢复出厂设置。
自检
    命令行执行  python shop.py --selftest  会跑一遍核心逻辑的自测。
"""

import hashlib
import json
import os
import secrets
import sys
from datetime import datetime

# ---------------------------------------------------------------- 常量

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "shop_data.json")

INITIAL_BALANCE = 10000          # 注册赠送 100.00 元，单位：分
STUDENT_DISCOUNT_PERCENT = 10    # 学生九折 = 优惠 10%
MAX_RECHARGE_CENTS = 5000000     # 单次最多充值 50000.00 元，单位：分

# 初始化商品：名称、单价（分）、库存
DEFAULT_PRODUCTS = [
    ("中性笔", 500, 100),
    ("笔记本", 1500, 30),
    ("保温杯", 8900, 12),
    ("双肩包", 12900, 5),
    ("机械键盘", 39900, 3),
    ("显示器", 89900, 2),
]


class CheckoutError(Exception):
    """结算失败。抛出时保证数据没有被改动。"""


# ---------------------------------------------------------------- 小工具

def yuan(cents):
    """分 -> '12.30' 形式的字符串（整数运算，不碰浮点）"""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return "{}{}.{:02d}".format(sign, cents // 100, cents % 100)


def parse_yuan(text):
    """'99.5' -> 9950 分；格式不对返回 None（允许千分位逗号与首尾空格）"""
    text = (text or "").strip().replace(",", "").replace("，", "")
    if not text:
        return None
    if text.count(".") > 1:
        return None
    if "." in text:
        whole, frac = text.split(".")
        whole = whole or "0"
        if not whole.isdigit() or not frac.isdigit() or len(frac) > 2:
            return None
        return int(whole) * 100 + int((frac + "00")[:2])
    if text.isdigit():
        return int(text) * 100
    return None


def disp_width(text):
    """显示宽度：中文/全角算 2 格"""
    width = 0
    for ch in text:
        width += 2 if ord(ch) > 0x2E80 else 1
    return width


def pad(text, width):
    """按显示宽度左对齐补空格"""
    return text + " " * max(0, width - disp_width(text))


def money_column(cents, width=12):
    """右对齐的金额列，例如 '     359.10 元'"""
    text = yuan(cents) + " 元"
    return " " * max(0, width - disp_width(text)) + text


def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 算钱

def discount_cents(amount_cents, is_student):
    """学生优惠金额（分）。按 10% 四舍五入到分，全整数运算。"""
    if not is_student or amount_cents <= 0:
        return 0
    return (amount_cents * STUDENT_DISCOUNT_PERCENT + 50) // 100


def total_cents(amount_cents, is_student):
    """应付金额（分）"""
    return amount_cents - discount_cents(amount_cents, is_student)


# ---------------------------------------------------------------- 数据存取

def _seed_data():
    return {
        "users": {},
        "products": [
            {"id": i + 1, "name": name, "price": price, "stock": stock}
            for i, (name, price, stock) in enumerate(DEFAULT_PRODUCTS)
        ],
        "carts": {},
        "orders": [],
    }


def load_data(path):
    """读取数据文件；不存在或损坏时返回初始数据"""
    if not os.path.exists(path):
        return _seed_data()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        print("数据文件读取失败，已重置为初始数据。")
        return _seed_data()

    for key, value in _seed_data().items():     # 补齐缺失的字段
        data.setdefault(key, value)
    return data


class Store:
    """负责「数据 + 规则」，不碰任何界面输入输出"""

    def __init__(self, path=None, data=None):
        self.path = path
        self.data = data if data is not None else load_data(path)

    # ---- 基础读写

    def save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def user(self, username):
        return self.data["users"].get(username)

    def products(self):
        return self.data["products"]

    def find_product(self, product_id):
        for product in self.data["products"]:
            if product["id"] == product_id:
                return product
        return None

    def cart(self, username):
        """{商品id(字符串): 数量}"""
        return self.data["carts"].setdefault(username, {})

    # ---- 用户

    def register(self, username, password, is_student):
        username = username.strip()
        if not (3 <= len(username) <= 20):
            raise ValueError("用户名要 3~20 个字符。")
        if username in self.data["users"]:
            raise ValueError("这个用户名已经被注册了。")
        if len(password) < 4:
            raise ValueError("密码至少 4 位。")
        salt = secrets.token_hex(8)
        self.data["users"][username] = {
            "salt": salt,
            "hash": hash_password(password, salt),
            "is_student": bool(is_student),
            "balance": INITIAL_BALANCE,
        }
        self.cart(username)
        self.save()
        return self.data["users"][username]

    def login(self, username, password):
        user = self.data["users"].get(username.strip())
        if user is None:
            raise ValueError("用户名不存在。")
        if hash_password(password, user["salt"]) != user["hash"]:
            raise ValueError("密码错误。")
        return user

    # ---- 充值

    def recharge(self, username, amount_cents):
        """充值。返回一条充值记录，同时留一份在用户数据里"""
        if amount_cents <= 0:
            raise ValueError("充值金额要大于 0。")
        if amount_cents > MAX_RECHARGE_CENTS:
            raise ValueError("单次最多充值 {} 元。".format(yuan(MAX_RECHARGE_CENTS)))
        user = self.data["users"][username]
        user["balance"] += amount_cents
        record = {
            "id": "R" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(secrets.randbelow(10000)).zfill(4),
            "amount": amount_cents,
            "balance_after": user["balance"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        user.setdefault("topups", []).append(record)
        self.save()
        return record

    def topups_of(self, username):
        return self.data["users"][username].get("topups", [])

    # ---- 购物车

    def add_to_cart(self, username, product_id, qty):
        product = self.find_product(product_id)
        if product is None:
            raise ValueError("没有这个商品。")
        if qty <= 0:
            raise ValueError("数量要大于 0。")
        cart = self.cart(username)
        current = cart.get(str(product_id), 0)
        if current + qty > product["stock"]:
            raise ValueError("{}库存只剩 {} 件。".format(product["name"], product["stock"]))
        cart[str(product_id)] = current + qty
        self.save()

    def set_qty(self, username, product_id, qty):
        cart = self.cart(username)
        if str(product_id) not in cart:
            raise ValueError("购物车里没有这个商品。")
        product = self.find_product(product_id)
        if qty <= 0:
            cart.pop(str(product_id))
        else:
            if product is not None and qty > product["stock"]:
                raise ValueError("{}库存只剩 {} 件。".format(product["name"], product["stock"]))
            cart[str(product_id)] = qty
        self.save()

    def remove_from_cart(self, username, product_id):
        cart = self.cart(username)
        if str(product_id) not in cart:
            raise ValueError("购物车里没有这个商品。")
        cart.pop(str(product_id))
        self.save()

    def cart_lines(self, username):
        """[(商品dict, 数量, 小计分)]，已下架的商品会被跳过"""
        lines = []
        for pid, qty in list(self.cart(username).items()):
            product = self.find_product(int(pid))
            if product is None:
                continue
            lines.append((product, qty, product["price"] * qty))
        return lines

    # ---- 结算

    def checkout(self, username):
        """先全量校验，全部通过才改数据；任何一步失败都不留下痕迹"""
        user = self.data["users"][username]
        lines = self.cart_lines(username)
        if not lines:
            raise CheckoutError("购物车是空的。")

        amount = 0
        for product, qty, line_total in lines:
            if qty <= 0:
                raise CheckoutError("「{}」的数量不对。".format(product["name"]))
            if product["stock"] < qty:
                raise CheckoutError(
                    "{}库存不足：只剩 {} 件。".format(product["name"], product["stock"])
                )
            amount += line_total

        discount = discount_cents(amount, user["is_student"])
        payable = amount - discount

        if payable > user["balance"]:
            raise CheckoutError("余额不足：还差 {} 元。".format(yuan(payable - user["balance"])))

        # ---- 校验通过，开始改数据（这段之后不会再失败）
        for product, qty, _ in lines:
            product["stock"] -= qty
        user["balance"] -= payable
        self.data["carts"][username] = {}

        order = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S") + "-" + str(secrets.randbelow(10000)).zfill(4),
            "user": username,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": [
                {"name": p["name"], "price": p["price"], "qty": q, "line_total": t}
                for p, q, t in lines
            ],
            "amount": amount,
            "discount": discount,
            "total": payable,
        }
        self.data["orders"].append(order)
        self.save()
        return order

    def orders_of(self, username):
        return [o for o in self.data["orders"] if o["user"] == username]


# ---------------------------------------------------------------- 界面

class App:
    def __init__(self, store):
        self.store = store
        self.username = None

    # ---- 输入小工具

    @staticmethod
    def ask(prompt):
        return input(prompt)

    @staticmethod
    def ask_int(prompt):
        text = input(prompt).strip()
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def ask_yes(prompt, default=True):
        text = input(prompt).strip().lower()
        if not text:
            return default
        return text in ("y", "yes", "是", "1")

    # ---- 主流程

    def run(self):
        self.banner()
        while True:
            if self.username is None:
                if not self.login_menu():
                    break
            else:
                if not self.shop_menu():
                    self.username = None
        print("\n再见。")

    def banner(self):
        print("=" * 46)
        print("        简易购物系统  v1.0（单文件版）")
        print("=" * 46)

    def login_menu(self):
        print("\n[1] 登录    [2] 注册    [0] 退出")
        choice = input("请选择：").strip()
        if choice == "1":
            self.do_login()
        elif choice == "2":
            self.do_register()
        elif choice == "0":
            return False
        else:
            print("没有这个选项。")
        return True

    def do_login(self):
        username = input("用户名：")
        password = input("密码：")
        try:
            self.store.login(username, password)
        except ValueError as exc:
            print(exc)
            return
        self.username = username.strip()
        print("\n欢迎回来，{}。".format(self.username))

    def do_register(self):
        username = input("设置账号：")
        password = input("设置密码：")
        student = self.ask_yes("是否学生？(y/n)：", default=False)
        try:
            self.store.register(username, password, student)
        except ValueError as exc:
            print(exc)
            return
        self.username = username.strip()
        print("注册成功，赠送初始余额 {} 元。".format(yuan(INITIAL_BALANCE)))

    def shop_menu(self):
        user = self.store.user(self.username)
        print("\n===== {} | 余额 {} 元{} =====".format(
            self.username,
            yuan(user["balance"]),
            " | 学生" if user["is_student"] else "",
        ))
        print("[1] 商品列表  [2] 加入购物车  [3] 查看购物车")
        print("[4] 修改数量  [5] 删除商品    [6] 结算")
        print("[7] 我的订单  [8] 充值      [0] 退出登录")
        choice = input("请选择：").strip()

        if choice == "1":
            self.show_products()
        elif choice == "2":
            self.do_add()
        elif choice == "3":
            self.show_cart()
        elif choice == "4":
            self.do_set_qty()
        elif choice == "5":
            self.do_remove()
        elif choice == "6":
            self.do_checkout()
        elif choice == "7":
            self.show_orders()
        elif choice == "8":
            self.do_recharge()
        elif choice == "0":
            return False
        else:
            print("没有这个选项。")
        return True

    # ---- 各功能

    def show_products(self):
        print("\n商品列表：")
        print("  {}".format(pad("编号", 6) + pad("商品", 14) + pad("单价", 14) + "库存"))
        for product in self.store.products():
            flag = "" if product["stock"] > 0 else "（售罄）"
            print("  {}{}{}{}".format(
                pad(str(product["id"]), 6),
                pad(product["name"], 14),
                pad(yuan(product["price"]) + " 元", 14),
                "{:>3} 件{}".format(product["stock"], flag),
            ))

    def do_add(self):
        self.show_products()
        pid = self.ask_int("\n商品编号：")
        if pid is None:
            print("编号要是数字。")
            return
        qty = self.ask_int("数量：")
        if qty is None:
            print("数量要是数字。")
            return
        try:
            self.store.add_to_cart(self.username, pid, qty)
        except ValueError as exc:
            print(exc)
            return
        product = self.store.find_product(pid)
        print("已加入购物车：{} × {}".format(product["name"], qty))

    def show_cart(self):
        lines = self.store.cart_lines(self.username)
        if not lines:
            print("\n购物车是空的。")
            return
        user = self.store.user(self.username)
        amount = sum(t for _, _, t in lines)
        discount = discount_cents(amount, user["is_student"])
        payable = amount - discount

        print("\n---------- 购物车 ----------")
        print("  {}".format(pad("编号", 6) + pad("商品", 14) + pad("单价", 13) + "数量 / 小计"))
        for product, qty, line_total in lines:
            print("  {}{}{} × {:<3}= {}".format(
                pad(str(product["id"]), 6),
                pad(product["name"], 14),
                money_column(product["price"], 12),
                qty,
                money_column(line_total),
            ))
        print("-" * 36)
        print("  {}{}".format(pad("小计：", 10), money_column(amount)))
        if discount:
            print("  {}{}".format(pad("学生优惠：", 10), money_column(-discount)))
        print("  {}{}".format(pad("应付：", 10), money_column(payable)))
        print("  {}{}".format(pad("余额：", 10), money_column(user["balance"])))

    def do_set_qty(self):
        self.show_cart()
        if not self.store.cart_lines(self.username):
            return
        pid = self.ask_int("\n商品编号（改成 0 等于删除）：")
        if pid is None:
            print("编号要是数字。")
            return
        qty = self.ask_int("新数量：")
        if qty is None:
            print("数量要是数字。")
            return
        try:
            self.store.set_qty(self.username, pid, qty)
        except ValueError as exc:
            print(exc)
            return
        print("已更新。")

    def do_remove(self):
        self.show_cart()
        if not self.store.cart_lines(self.username):
            return
        pid = self.ask_int("\n要删除的商品编号：")
        if pid is None:
            print("编号要是数字。")
            return
        try:
            self.store.remove_from_cart(self.username, pid)
        except ValueError as exc:
            print(exc)
            return
        print("已删除。")

    def do_recharge(self):
        user = self.store.user(self.username)
        print("\n当前余额 {} 元；单次最多充 {} 元。".format(
            yuan(user["balance"]), yuan(MAX_RECHARGE_CENTS)
        ))
        amount = parse_yuan(input("充值金额（元，直接回车放弃）："))
        if amount is None:
            print("金额格式不对，像 100 或 99.5 这样写。")
            return
        if amount == 0:
            print("已取消。")
            return
        try:
            record = self.store.recharge(self.username, amount)
        except ValueError as exc:
            print(exc)
            return
        print("\n充值成功：+{} 元，当前余额 {} 元。".format(
            yuan(record["amount"]), yuan(record["balance_after"])
        ))

    def do_checkout(self):
        self.show_cart()
        if not self.store.cart_lines(self.username):
            return
        if not self.ask_yes("\n确认付款？(y/n)：", default=True):
            print("已取消。")
            return
        try:
            order = self.store.checkout(self.username)
        except CheckoutError as exc:
            print("\n{}".format(exc))
            if "余额不足" in str(exc):
                print("可以先按 [8] 充值，再回来结算。")
            return
        self.print_receipt(order)

    def print_receipt(self, order):
        print("\n" + "=" * 44)
        print("  订单号：{}".format(order["id"]))
        print("  账号：  {}".format(order["user"]))
        print("-" * 44)
        for item in order["items"]:
            print("  {}{}× {:<3} = {} 元".format(
                pad(item["name"], 14), pad(yuan(item["price"]) + " 元 ", 11), item["qty"], yuan(item["line_total"])
            ))
        print("-" * 44)
        print("  {}{}".format(pad("小计：", 10), money_column(order["amount"])))
        if order["discount"]:
            print("  {}{}".format(pad("学生优惠：", 10), money_column(-order["discount"])))
        print("  {}{}".format(pad("应付：", 10), money_column(order["total"])))
        print("=" * 44)
        print("付款成功，余额还剩 {} 元。".format(yuan(self.store.user(order["user"])["balance"])))

    def show_orders(self):
        orders = self.store.orders_of(self.username)
        if not orders:
            print("\n还没有订单。")
        else:
            print("\n我的订单：")
            for order in reversed(orders):
                names = "、".join("{}×{}".format(i["name"], i["qty"]) for i in order["items"])
                print("  {}  {}  应付 {} 元".format(order["created_at"], order["id"], yuan(order["total"])))
                print("      {}".format(names))

        topups = self.store.topups_of(self.username)
        if topups:
            print("\n充值记录（最近 5 条）：")
            for record in reversed(topups[-5:]):
                print("  {}  +{} 元  余额 {} 元".format(
                    record["created_at"], yuan(record["amount"]), yuan(record["balance_after"])
                ))


# ---------------------------------------------------------------- 自检

def selftest():
    """不碰磁盘，纯内存跑一遍核心规则；返回进程退出码"""
    results = []

    def check(name, func):
        try:
            func()
            results.append((name, True, ""))
        except AssertionError as exc:
            results.append((name, False, str(exc) or "断言失败"))
        except Exception as exc:                      # noqa: BLE001
            results.append((name, False, "{}: {}".format(type(exc).__name__, exc)))

    def fresh():
        return Store(data=_seed_data())

    def t_no_discount_for_normal_user():
        assert discount_cents(1500, False) == 0
        assert total_cents(1500, False) == 1500

    def t_student_90_percent():
        assert discount_cents(1500, True) == 150
        assert total_cents(1500, True) == 1350

    def t_discount_rounds_to_cent():
        assert discount_cents(5, True) == 1          # 0.5 分 -> 1 分
        assert discount_cents(4, True) == 0

    def t_register_and_login():
        store = fresh()
        user = store.register("alice", "pw123", True)
        assert user["is_student"] is True
        assert user["balance"] == INITIAL_BALANCE
        store.login("alice", "pw123")
        try:
            store.login("alice", "wrong")
        except ValueError:
            pass
        else:
            raise AssertionError("错误密码竟然登录成功")

    def t_reject_duplicate_user():
        store = fresh()
        store.register("alice", "pw123", False)
        try:
            store.register("alice", "other", False)
        except ValueError:
            pass
        else:
            raise AssertionError("重名注册没有被拒绝")

    def t_checkout_success():
        store = fresh()
        store.register("bob", "pw123", True)
        store.add_to_cart("bob", 2, 1)               # 笔记本 15.00
        order = store.checkout("bob")
        assert order["amount"] == 1500
        assert order["discount"] == 150
        assert order["total"] == 1350
        assert store.user("bob")["balance"] == INITIAL_BALANCE - 1350
        assert store.find_product(2)["stock"] == 30 - 1
        assert store.cart_lines("bob") == []

    def t_insufficient_balance_changes_nothing():
        store = fresh()
        store.register("carol", "pw123", True)
        store.add_to_cart("carol", 5, 1)             # 机械键盘 399.00，余额不够
        before_balance = store.user("carol")["balance"]
        before_stock = store.find_product(5)["stock"]
        try:
            store.checkout("carol")
        except CheckoutError as exc:
            assert "余额不足" in str(exc)
        else:
            raise AssertionError("余额不足竟然结算成功")
        assert store.user("carol")["balance"] == before_balance
        assert store.find_product(5)["stock"] == before_stock
        assert store.cart_lines("carol")                    # 购物车要保留
        assert store.orders_of("carol") == []

    def t_insufficient_stock_changes_nothing():
        store = fresh()
        store.register("dave", "pw123", False)
        store.find_product(5)["stock"] = 1
        store.data["carts"]["dave"] = {"5": 2}       # 绕过界面直接塞一个超量购物车
        before_balance = store.user("dave")["balance"]
        try:
            store.checkout("dave")
        except CheckoutError as exc:
            assert "库存不足" in str(exc)
        else:
            raise AssertionError("库存不足竟然结算成功")
        assert store.user("dave")["balance"] == before_balance
        assert store.find_product(5)["stock"] == 1

    def t_cannot_exceed_stock_when_adding():
        store = fresh()
        store.register("erin", "pw123", False)
        try:
            store.add_to_cart("erin", 5, 99)
        except ValueError:
            pass
        else:
            raise AssertionError("加购超过库存没有被拦住")

    def t_order_keeps_price_snapshot():
        store = fresh()
        store.register("frank", "pw123", False)
        store.add_to_cart("frank", 1, 2)             # 中性笔 5.00 × 2
        store.checkout("frank")
        store.find_product(1)["price"] = 99900       # 事后涨价
        assert store.orders_of("frank")[0]["items"][0]["price"] == 500

    def t_empty_cart_rejected():
        store = fresh()
        store.register("gina", "pw123", False)
        try:
            store.checkout("gina")
        except CheckoutError:
            pass
        else:
            raise AssertionError("空购物车竟然能结算")

    def t_parse_yuan():
        assert parse_yuan("100") == 10000
        assert parse_yuan("99.5") == 9950
        assert parse_yuan("0.01") == 1
        assert parse_yuan(" 12.34 ") == 1234
        assert parse_yuan("1,000") == 100000
        assert parse_yuan("abc") is None
        assert parse_yuan("-5") is None
        assert parse_yuan("1.234") is None
        assert parse_yuan("") is None

    def t_recharge_adds_balance():
        store = fresh()
        store.register("hana", "pw123", False)
        record = store.recharge("hana", 5000)
        assert record["amount"] == 5000
        assert record["balance_after"] == INITIAL_BALANCE + 5000
        assert store.user("hana")["balance"] == INITIAL_BALANCE + 5000
        assert len(store.topups_of("hana")) == 1

    def t_recharge_rejects_bad_amount():
        store = fresh()
        store.register("ivan", "pw123", False)
        for bad in (0, -100, MAX_RECHARGE_CENTS + 1):
            try:
                store.recharge("ivan", bad)
            except ValueError:
                pass
            else:
                raise AssertionError("非法金额 {} 竟然充值成功".format(bad))
        assert store.user("ivan")["balance"] == INITIAL_BALANCE

    def t_recharge_then_checkout():
        store = fresh()
        store.register("jane", "pw123", True)
        store.add_to_cart("jane", 5, 1)              # 机械键盘 399.00，余额 100 不够
        try:
            store.checkout("jane")
        except CheckoutError:
            pass
        else:
            raise AssertionError("余额不足竟然结算成功")
        store.recharge("jane", 30000)                # 充 300.00
        order = store.checkout("jane")
        assert order["amount"] == 39900
        assert order["discount"] == 3990
        assert order["total"] == 35910
        assert store.user("jane")["balance"] == INITIAL_BALANCE + 30000 - 35910

    def t_remove_from_cart():
        store = fresh()
        store.register("kate", "pw123", False)
        store.add_to_cart("kate", 1, 2)
        store.add_to_cart("kate", 2, 1)
        store.remove_from_cart("kate", 1)
        lines = store.cart_lines("kate")
        assert len(lines) == 1 and lines[0][0]["id"] == 2
        try:
            store.remove_from_cart("kate", 1)
        except ValueError:
            pass
        else:
            raise AssertionError("删不存在的商品竟然成功")
        assert store.find_product(1)["stock"] == 100   # 删购物车不该动库存

    check("非学生不打折", t_no_discount_for_normal_user)
    check("学生九折", t_student_90_percent)
    check("折扣四舍五入到分", t_discount_rounds_to_cent)
    check("注册与登录", t_register_and_login)
    check("拒绝重名注册", t_reject_duplicate_user)
    check("正常结算：扣款/减库存/清购物车", t_checkout_success)
    check("余额不足：数据一点不动", t_insufficient_balance_changes_nothing)
    check("库存不足：数据一点不动", t_insufficient_stock_changes_nothing)
    check("加购不能超过库存", t_cannot_exceed_stock_when_adding)
    check("订单保存价格快照", t_order_keeps_price_snapshot)
    check("空购物车不能结算", t_empty_cart_rejected)
    check("解析充值金额", t_parse_yuan)
    check("充值增加余额", t_recharge_adds_balance)
    check("拒绝非法充值金额", t_recharge_rejects_bad_amount)
    check("充值后能买得起", t_recharge_then_checkout)
    check("删除购物车商品", t_remove_from_cart)

    print("自检结果：")
    failed = 0
    for name, ok, message in results:
        print("  [{}] {}{}".format("通过" if ok else "失败", pad(name, 30), message))
        failed += 0 if ok else 1
    print("\n{} 项全部通过。".format(len(results)) if not failed
          else "\n{} 项失败。".format(failed))
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------- 入口

def force_utf8():
    """PyCharm / 管道下控制台默认可能是 GBK，统一切到 UTF-8，避免中文变问号"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force_utf8()
    if "--selftest" in argv:
        return selftest()

    store = Store(DATA_PATH)
    try:
        App(store).run()
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
