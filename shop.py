# -*- coding: utf-8 -*-
"""
简易购物系统（类似淘宝的简化版）
- 用户注册 / 登录
- 商品浏览 / 搜索
- 购物车（加购、改数量、删除）
- 下单结算
- 查看订单
数据通过 JSON 文件持久化，程序退出后数据不丢失。
"""

import json
import os
import hashlib
import getpass
from datetime import datetime

# ------------------------- 数据文件 -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")        # 用户数据
PRODUCTS_FILE = os.path.join(BASE_DIR, "products.json")  # 商品数据
CARTS_FILE = os.path.join(BASE_DIR, "carts.json")        # 购物车数据
ORDERS_FILE = os.path.join(BASE_DIR, "orders.json")      # 订单数据


# ------------------------- 文件读写工具 -------------------------
def load_json(path, default):
    """读取 JSON 文件，不存在或损坏时返回默认值"""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default


def save_json(path, data):
    """把数据写入 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def hash_password(password):
    """对密码做简单的加盐哈希（仅演示用，正式系统请用更安全方案）"""
    return hashlib.sha256(("shop_salt_" + password).encode("utf-8")).hexdigest()


# ------------------------- 默认数据 -------------------------
DEFAULT_PRODUCTS = [
    {"id": 1, "name": "无线蓝牙耳机", "price": 199.0, "stock": 50, "category": "数码"},
    {"id": 2, "name": "机械键盘", "price": 329.0, "stock": 30, "category": "数码"},
    {"id": 3, "name": "保温杯", "price": 59.0, "stock": 100, "category": "家居"},
    {"id": 4, "name": "运动鞋", "price": 299.0, "stock": 40, "category": "服饰"},
    {"id": 5, "name": "双肩背包", "price": 129.0, "stock": 60, "category": "服饰"},
    {"id": 6, "name": "台灯", "price": 89.0, "stock": 20, "category": "家居"},
    {"id": 7, "name": "充电宝 20000mAh", "price": 139.0, "stock": 80, "category": "数码"},
    {"id": 8, "name": "咖啡杯", "price": 39.0, "stock": 120, "category": "家居"},
]


# ------------------------- 用户模块 -------------------------
def register(users):
    print("\n===== 注册 =====")
    username = input("请输入用户名：").strip()
    if not username:
        print("用户名不能为空！")
        return None
    if username in users:
        print("该用户名已被注册！")
        return None
    password = getpass.getpass("请输入密码：").strip()
    if len(password) < 4:
        print("密码至少 4 位！")
        return None
    users[username] = {"password": hash_password(password), "created_at": str(datetime.now())}
    save_json(USERS_FILE, users)
    print(f"注册成功，欢迎 {username}！")
    return username


def login(users):
    print("\n===== 登录 =====")
    username = input("请输入用户名：").strip()
    password = getpass.getpass("请输入密码：").strip()
    user = users.get(username)
    if user and user["password"] == hash_password(password):
        print(f"登录成功，欢迎回来 {username}！")
        return username
    print("用户名或密码错误！")
    return None


# ------------------------- 商品模块 -------------------------
def show_products(products, keyword=None):
    """显示商品列表，可带关键字过滤"""
    print("\n===== 商品列表 =====")
    print(f"{'编号':<6}{'商品名称':<20}{'价格':<10}{'库存':<8}{'分类':<8}")
    print("-" * 52)
    shown = 0
    for p in products:
        if keyword and keyword not in p["name"] and keyword not in p["category"]:
            continue
        print(f"{p['id']:<6}{p['name']:<20}{p['price']:<10.1f}{p['stock']:<8}{p['category']:<8}")
        shown += 1
    if shown == 0:
        print("没有找到相关商品。")
    return products


def search_products(products):
    keyword = input("请输入搜索关键字（商品名或分类）：").strip()
    show_products(products, keyword if keyword else None)


# ------------------------- 购物车模块 -------------------------
def add_to_cart(username, carts, products):
    """把商品加入购物车"""
    show_products(products)
    try:
        pid = int(input("请输入要加入购物车的商品编号："))
    except ValueError:
        print("输入无效！")
        return
    product = next((p for p in products if p["id"] == pid), None)
    if product is None:
        print("商品不存在！")
        return
    if product["stock"] <= 0:
        print("该商品已售罄！")
        return

    cart = carts.setdefault(username, [])
    for item in cart:
        if item["product_id"] == pid:
            if item["quantity"] + 1 > product["stock"]:
                print("库存不足！")
                return
            item["quantity"] += 1
            save_json(CARTS_FILE, carts)
            print(f"已将《{product['name']}》加入购物车，当前数量 {item['quantity']}。")
            return
    cart.append({"product_id": pid, "quantity": 1})
    save_json(CARTS_FILE, carts)
    print(f"已将《{product['name']}》加入购物车。")


def show_cart(username, carts, products):
    """显示购物车内容，返回总金额"""
    cart = carts.get(username, [])
    print("\n===== 我的购物车 =====")
    if not cart:
        print("购物车是空的。")
        return 0.0

    total = 0.0
    print(f"{'编号':<6}{'商品名称':<20}{'单价':<10}{'数量':<8}{'小计':<10}")
    print("-" * 54)
    for item in cart:
        product = next((p for p in products if p["id"] == item["product_id"]), None)
        if product is None:
            continue
        subtotal = product["price"] * item["quantity"]
        total += subtotal
        print(f"{product['id']:<6}{product['name']:<20}{product['price']:<10.1f}"
              f"{item['quantity']:<8}{subtotal:<10.1f}")
    print("-" * 54)
    print(f"总计：{total:.1f} 元")
    return total


def manage_cart(username, carts, products):
    """购物车管理菜单：修改数量 / 删除"""
    show_cart(username, carts, products)
    cart = carts.get(username, [])
    if not cart:
        return

    print("\n1. 修改数量  2. 删除商品  0. 返回")
    choice = input("请选择：").strip()
    if choice == "1":
        try:
            pid = int(input("请输入商品编号："))
            qty = int(input("请输入新数量："))
        except ValueError:
            print("输入无效！")
            return
        product = next((p for p in products if p["id"] == pid), None)
        for item in cart:
            if item["product_id"] == pid:
                if qty <= 0:
                    cart.remove(item)
                    print("已删除该商品。")
                elif product and qty > product["stock"]:
                    print("数量超过库存！")
                else:
                    item["quantity"] = qty
                    print("数量已更新。")
                save_json(CARTS_FILE, carts)
                return
        print("购物车中没有该商品。")
    elif choice == "2":
        try:
            pid = int(input("请输入要删除的商品编号："))
        except ValueError:
            print("输入无效！")
            return
        for item in cart:
            if item["product_id"] == pid:
                cart.remove(item)
                save_json(CARTS_FILE, carts)
                print("已删除该商品。")
                return
        print("购物车中没有该商品。")
    elif choice == "0":
        return
    else:
        print("无效选择！")


# ------------------------- 订单模块 -------------------------
def checkout(username, carts, products, orders):
    """结算下单：把购物车商品生成订单并扣减库存"""
    cart = carts.get(username, [])
    if not cart:
        print("购物车是空的，无法结算。")
        return

    total = show_cart(username, carts, products)
    print(f"\n应付款：{total:.1f} 元")
    confirm = input("确认下单吗？(y/n)：").strip().lower()
    if confirm != "y":
        print("已取消下单。")
        return

    # 再次校验库存
    for item in cart:
        product = next((p for p in products if p["id"] == item["product_id"]), None)
        if product is None:
            print(f"商品（id={item['product_id']}）不存在，下单失败。")
            return
        if item["quantity"] > product["stock"]:
            print(f"《{product['name']}》库存不足（剩余 {product['stock']}），下单失败。")
            return

    # 扣减库存
    for item in cart:
        product = next(p for p in products if p["id"] == item["product_id"])
        product["stock"] -= item["quantity"]
    save_json(PRODUCTS_FILE, products)

    # 生成订单
    order = {
        "order_id": int(datetime.now().timestamp()),
        "username": username,
        "items": [dict(item) for item in cart],   # 深拷贝，避免被后续修改
        "total": total,
        "status": "已支付",
        "created_at": str(datetime.now()),
    }
    orders.setdefault(username, []).append(order)
    save_json(ORDERS_FILE, orders)

    # 清空购物车
    carts[username] = []
    save_json(CARTS_FILE, carts)

    print(f"\n下单成功！订单号：{order['order_id']}，实付 {total:.1f} 元。")


def show_orders(username, orders, products):
    """显示当前用户的历史订单"""
    user_orders = orders.get(username, [])
    print("\n===== 我的订单 =====")
    if not user_orders:
        print("还没有订单。")
        return
    for o in user_orders:
        print("-" * 54)
        print(f"订单号：{o['order_id']}   状态：{o['status']}   时间：{o['created_at']}")
        for item in o["items"]:
            product = next((p for p in products if p["id"] == item["product_id"]), None)
            name = product["name"] if product else "（商品已下架）"
            print(f"   {name} x {item['quantity']}")
        print(f"   总金额：{o['total']:.1f} 元")
    print("-" * 54)


# ------------------------- 主程序 -------------------------
def main():
    users = load_json(USERS_FILE, {})
    products = load_json(PRODUCTS_FILE, DEFAULT_PRODUCTS)
    carts = load_json(CARTS_FILE, {})
    orders = load_json(ORDERS_FILE, {})
    # 首次运行写入默认商品
    save_json(PRODUCTS_FILE, products)

    current_user = None
    print("欢迎使用简易购物系统！")

    # 登录 / 注册循环
    while current_user is None:
        print("\n1. 登录  2. 注册  0. 退出")
        choice = input("请选择：").strip()
        if choice == "1":
            current_user = login(users)
        elif choice == "2":
            current_user = register(users)
        elif choice == "0":
            print("感谢使用，再见！")
            return
        else:
            print("无效选择！")

    # 已登录的主菜单循环
    while True:
        print(f"\n===== 主菜单（当前用户：{current_user}） =====")
        print("1. 浏览商品  2. 搜索商品  3. 加入购物车")
        print("4. 查看购物车  5. 结算下单  6. 我的订单  0. 退出登录")
        choice = input("请选择：").strip()

        if choice == "1":
            show_products(products)
        elif choice == "2":
            search_products(products)
        elif choice == "3":
            add_to_cart(current_user, carts, products)
        elif choice == "4":
            manage_cart(current_user, carts, products)
        elif choice == "5":
            checkout(current_user, carts, products, orders)
        elif choice == "6":
            show_orders(current_user, orders, products)
        elif choice == "0":
            print("已退出登录。")
            current_user = None
            break
        else:
            print("无效选择！")

    # 退出登录后，重新进入登录/注册循环（可换账号）
    main()


if __name__ == "__main__":
    main()
