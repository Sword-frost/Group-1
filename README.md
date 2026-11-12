# Project-123

简易购物系统：浏览商品、注册登录、购物车、结算和订单。注册时可选填 12 位数字学号，结算自动打九折；学号仅检查格式。

网页界面现为英文。新账号用户名至少 2 个字符；密码至少 6 个字符，并包含英文大写字母、小写字母、数字和特殊符号（如 `!`、`@`）。

结算后进入演示支付页。WeChat Pay 和 Alipay 二维码分别只编码“微信支付”和“支付宝支付”，不会发起真实付款。点击完成演示按钮后，订单标记为 Demo paid。

测试命令：`python -m unittest test_webapp -v`。

## 运行网页版

需要 Python 3 和 pip。在项目根目录的终端执行：

```bash
python -m venv .venv
```

Windows 下激活环境：

```powershell
.venv\Scripts\Activate.ps1
```

macOS 或 Linux 下使用 `source .venv/bin/activate`。然后执行：

```bash
python -m pip install -r webapp/requirements.txt
python webapp/app.py
```

浏览器打开 http://127.0.0.1:5000/。首次运行会在 webapp 目录自动创建数据库并添加示例商品。注册新账号即可使用；留空学号为普通用户。

`shop.py` 是原项目附带的独立命令行版本。学生折扣功能位于网页版。

本项目供本地演示和学习使用，不包含真实支付或学生身份核验，不适合直接部署到公网。
