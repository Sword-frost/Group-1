# 简易网购程序（纯 Python）

按 `test.txt` 那几行需求做的：**登录界面**（账号 / 密码 / 是否学生 / 余额）+ **购买界面**（商品 / 购物清单 / 学生折扣 / 扣费 / 余额不足提示）。

不需要数据库、不需要联网、不需要装任何第三方库。

---

## 怎么跑

**方式一：PyCharm（最省事）**

打开这个文件夹 → 右键 `main.py` → Run 'main'。PyCharm 会自己找到 Python 解释器。

**方式二：命令行**

```powershell
cd "C:\Users\ASUS TX\Documents\deepseek-harness\default-workspace\shop_app"
python main.py
```

⚠️ 你这台机器上 `python` 还没加进 PATH，直接用会报「无法识别」。两种解法：

```powershell
# 解法 A：用 py 启动器
py main.py

# 解法 B：写全路径
& 'C:\Users\ASUS TX\AppData\Local\Programs\Python\Python314\python.exe' main.py
```

想一劳永逸就把 `C:\Users\ASUS TX\AppData\Local\Programs\Python\Python314\` 加进系统环境变量 PATH。

---

## 怎么用

**登录界面**

```
[1] 登录    [2] 注册    [0] 退出
```

注册时填账号、密码，再用 `y/n` 回答是不是学生。新用户送 100 元余额。

**购买界面**

```
输入商品编号加入购物车    d 删除    c 结算    q 退出登录
```

| 输入 | 作用 |
|---|---|
| 数字 `1`~`4` | 把这个编号的商品加入购物车（会再问数量） |
| `d` | 从购物清单里删一项 |
| `c` | 结算：显示小计、学生优惠、应付，确认后扣款 |
| `q` | 退出登录，回主菜单 |

结算流程：算小计 → 学生减 10% → 和余额比 → 够就扣款、减库存、出订单号和小票；不够就提示「还差多少元」，什么都不改。

**数据存在 `data.json`**：账号、余额、库存、历史订单都在里面。删掉这个文件，一切重置。

---

## 文件结构

```
shop_app/
  main.py              入口，python main.py
  shop/
    models.py          数据结构：User / Product / CartItem / Order
    pricing.py         算钱：小计、折扣、应付（纯函数）
    auth.py            密码加盐哈希
    store.py           数据存取（JSON 文件）
    checkout.py        结算：校验 → 算钱 → 扣款 → 减库存 → 出订单
    cli.py             命令行界面：登录界面 + 购买界面
  tests/
    test_pricing.py    算钱的测试
    test_checkout.py   结算的测试（重点测「失败时不能改数据」）
```

界面只负责「问」和「显示」，所有判断都在 `pricing` / `checkout` 里。以后换成 Streamlit 网页，这两个文件一行都不用改——这就是把逻辑和界面分开的好处。

---

## 跑测试

```powershell
cd "C:\Users\ASUS TX\Documents\deepseek-harness\default-workspace\shop_app"
py -m unittest discover -s tests -t . -v
```

当前 13 个测试全过。

---

## 刻意做对的五个地方

1. **金额全是「分」的整数**，没有浮点。`0.1 + 0.2 != 0.3` 这种坑直接绕开，折扣也是整数四舍五入到分。
2. **订单存价格快照**。下单时把单价抄进订单里，之后商品改价不影响历史订单（`test_order_keeps_price_snapshot` 就在验这个）。
3. **失败不改数据**。`checkout()` 先把所有校验做完，全过了才动余额和库存；中途报错就原样返回。不会出现「钱扣了、订单没生成」。
4. **密码只存哈希**。`sha256(盐 + 密码)`，`data.json` 里看不到明文密码。（真实项目该用 bcrypt/argon2。）
5. **金额按商品表现价重算**，不信界面传来的数字——这是电商防薅羊毛的基本功。

---

## 已知的简化（真实系统不这么干）

- 学生标记由用户自己勾选，没有审核 → 真实系统要验证学籍
- 数据存 JSON 文件，没有事务、没有并发控制 → 真实系统用数据库事务
- 余额只能减少，没有充值入口
- 没有退款、没有订单列表页面（订单存在 `data.json` 的 `orders` 里）
- 密码哈希用标准库 sha256，不是专门的慢哈希

---

## 下一步可以加什么

按性价比排：

1. **订单列表**：登录后能看自己买过什么
2. **充值**：加个 `r` 指令，方便测余额边界
3. **改成 Streamlit 网页**：套一层界面，核心代码不动
4. **换 SQLite**：把 `store.py` 换成数据库，学事务
5. **管理员**：上架商品、改价、看所有订单
