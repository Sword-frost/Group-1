import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from webapp import app as shop


class WebShopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.path.dirname(__file__))
        self.previous_db = shop.DB_PATH
        shop.DB_PATH = os.path.join(self.temp.name, 'shop.db')
        shop.init_db()
        shop.app.config['TESTING'] = True
        self.client = shop.app.test_client()

    def tearDown(self):
        shop.DB_PATH = self.previous_db
        self.temp.cleanup()

    def register(self, username='Alice', password='Abc1!x', number=''):
        return self.client.post('/register', data={
            'username': username, 'password': password,
            'confirm': password, 'student_number': number,
        })

    def login(self, username='Alice'):
        self.client.post('/login', data={'username': username, 'password': 'Abc1!x'})

    def order(self, student=False):
        self.register(number='123456789012' if student else '')
        self.login()
        self.client.post('/cart/add/1', data={'quantity': 1})
        return self.client.post('/checkout')

    def test_registration_rules(self):
        for password in ('Ab1!x', 'abc1!x', 'ABC1!X', 'Abc!!x', 'Abc123'):
            self.assertEqual(self.register(password=password).status_code, 200)
        self.assertEqual(self.register(username='A').status_code, 200)
        self.assertEqual(self.register(number='123').status_code, 200)
        self.assertEqual(self.register(username='Al').status_code, 302)

    def test_student_discount_and_demo_payment(self):
        self.assertTrue(self.order(student=True).location.endswith('/payment/1'))
        with closing(sqlite3.connect(shop.DB_PATH)) as db:
            self.assertEqual(db.execute('SELECT total, status FROM orders').fetchone(),
                             (179.1, 'Awaiting demo payment'))
        response = self.client.get('/payment/1')
        self.assertIn(b'WeChat Pay', response.data)
        self.assertIn(b'Alipay', response.data)
        self.assertEqual(self.client.post('/payment/1', data={'method': 'other'}).status_code, 400)
        self.client.post('/payment/1', data={'method': 'wechat'})
        self.client.post('/payment/1', data={'method': 'alipay'})
        with closing(sqlite3.connect(shop.DB_PATH)) as db:
            self.assertEqual(db.execute('SELECT status FROM orders').fetchone()[0], 'Demo paid')
            self.assertEqual(db.execute('SELECT stock FROM products WHERE id=1').fetchone()[0], 49)

    def test_regular_total_and_order_access(self):
        self.order()
        with closing(sqlite3.connect(shop.DB_PATH)) as db:
            self.assertEqual(db.execute('SELECT total FROM orders').fetchone()[0], 199)
        self.client.get('/logout')
        self.register(username='Bob')
        self.login('Bob')
        self.assertEqual(self.client.get('/payment/1').status_code, 404)
        self.assertEqual(self.client.post('/payment/1', data={'method':'alipay'}).status_code, 404)

    def test_qr_payloads(self):
        self.register()
        self.login()
        for method, payload in [('wechat', '微信支付'), ('alipay', '支付宝支付')]:
            with patch.object(shop.qrcode.QRCode, 'add_data', autospec=True,
                              side_effect=shop.qrcode.QRCode.add_data) as add_data:
                response = self.client.get('/payment/qr/' + method + '.svg')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'<svg', response.data)
                self.assertEqual(add_data.call_args.args[1], payload)

    def test_english_catalog_and_pages(self):
        for path in ('/', '/register', '/login'):
            text = self.client.get(path).get_data(as_text=True)
            self.assertFalse(any('\u4e00' <= char <= '\u9fff' for char in text))


if __name__ == '__main__':
    unittest.main()
