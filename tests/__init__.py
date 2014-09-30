# -*- coding: utf-8 -*-
"""
    __init__

    Collect all tests here

    :copyright: (c) 2014 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
import unittest

from .test_banner import TestBanner, TestGetHtml
from .test_cms import TestCMS


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestBanner),
        unittest.TestLoader().loadTestsFromTestCase(TestGetHtml),
        unittest.TestLoader().loadTestsFromTestCase(TestCMS),
    ])
    return test_suite
