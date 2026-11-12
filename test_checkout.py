import unittest

from checkout import apply_student_discount


class StudentDiscountTests(unittest.TestCase):
    def test_student_discount(self):
        self.assertAlmostEqual(apply_student_discount(100, True), 90)

    def test_non_student_pays_original_price(self):
        self.assertEqual(apply_student_discount(100, False), 100)

    def test_another_total(self):
        self.assertAlmostEqual(apply_student_discount(50, True), 45)


if __name__ == '__main__':
    unittest.main()
