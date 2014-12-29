# -*- coding: utf-8 -*-
'''

    nereid_cms test_menuitem

    :copyright: (c) 2010-2015 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from trytond.transaction import Transaction
from nereid.testing import NereidTestCase


class TestMenuItem(NereidTestCase):
    """Test menu_item"""

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cms')

        self.Article = POOL.get('nereid.cms.article')
        self.ArticleCategory = POOL.get('nereid.cms.article.category')
        self.MenuItem = POOL.get('nereid.cms.menuitem')

        self.Currency = POOL.get('currency.currency')
        self.Company = POOL.get('company.company')
        self.NereidUser = POOL.get('nereid.user')
        self.Language = POOL.get('ir.lang')
        self.Website = POOL.get('nereid.website')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')

    def setup_defaults(self):
        """
        Setup the defaults
        """
        usd, = self.Currency.create([{
            'name': 'US Dollar',
            'code': 'USD',
            'symbol': '$',
        }])
        company_party, = self.Party.create([{
            'name': 'Openlabs'
        }])
        company, = self.Company.create([{
            'party': company_party,
            'currency': usd
        }])
        guest_party, = self.Party.create([{
            'name': 'Guest User',
        }])
        guest_user, = self.NereidUser.create([{
            'party': guest_party,
            'display_name': 'Guest User',
            'email': 'guest@openlabs.co.in',
            'password': 'password',
            'company': company.id,
        }])

        registered_party, = self.Party.create([{
            'name': 'Registered User'
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': registered_party,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': company.id,
        }])

        # Create locale
        en_us, = self.Language.search([('code', '=', 'en_US')])
        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id
        }])
        # Create website
        self.Website.create([{
            'name': 'localhost',
            'company': company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'currencies': [('add', [usd.id])],
        }])

    def test_0010__menuitem(self):
        """
        Test creation of menuitem
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            category, = self.ArticleCategory.create([{
                'title': 'blog',
                'unique_name': 'blog',
            }])

            article, = self.Article.create([{
                'uri': 'hello-world',
                'title': 'Hello World',
                'content': 'Test content',
                'sequence': 10,
                'state': 'published',
                'categories': [('add', [category.id])],
            }])
            main_view, = self.MenuItem.create([{
                'type_': 'view',
                'title': 'Test Title',
            }])
            menu1, menu2, menu3 = self.MenuItem.create([{
                'type_': 'static',
                'title': 'Test Title',
                'link': 'http://openlabs.co.in/',
                'parent': main_view
            }, {
                'type_': 'record',
                'title': 'About Us',
                'record': '%s,%s' % (article.__name__, article.id),
                'parent': main_view
            }, {
                'type_': 'record',
                'title': 'Blog',
                'record': '%s,%s' % (category.__name__, category.id),
                'parent': main_view
            }])

            self.assert_(menu1)
            self.assert_(menu2)
            self.assert_(menu3)

            self.setup_defaults()
            app = self.get_app()
            with app.test_request_context('/'):
                rv = main_view.get_menu_item(max_depth=10)
            for child in rv['children']:
                if child['type_'] == 'record' and child['record'] == category:
                    self.assertEqual(len(child['children']), 1)


def suite():
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestMenuItem)
    )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
