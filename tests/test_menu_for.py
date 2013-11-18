# -*- coding: utf-8 -*-
'''

    nereid_cms test_menu_for

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import unittest
from ast import literal_eval

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from nereid.testing import NereidTestCase
from trytond.transaction import Transaction


class TestMenuFor(NereidTestCase):
    """Test menu_for"""

    def get_template_source(self, name):
        """
        Return templates
        """
        return self.templates.get(name)

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

        party1, = self.Party.create([{
            'name': 'Registered User'
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': party1.id,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': company.id,
        }])

        # Create website
        url_map, = self.UrlMap.search([], limit=1)
        en_us, = self.Language.search([('code', '=', 'en_US')])
        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id
        }])
        self.site1, = self.NereidWebsite.create([{
            'name': 'localhost',
            'url_map': url_map.id,
            'company': company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'guest_user': guest_user,
            'currencies': [('set', [usd.id])],
        }])

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cms')
        trytond.tests.test_tryton.install_module('product')

        self.Currency = POOL.get('currency.currency')
        self.Company = POOL.get('company.company')
        self.NereidUser = POOL.get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.NereidWebsite = POOL.get('nereid.website')
        self.Party = POOL.get('party.party')
        self.Menu = POOL.get('nereid.cms.menu')
        self.Locale = POOL.get('nereid.website.locale')

        self.templates = {
            'home.jinja':
                '{{ menu_for("identifier", "Category1")|safe }}',
        }

    def test_0010_menu_for(self):
        """Two different website, having same unique identifier in
        nereid.cms.menu
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            ProductCategory = POOL.get('product.category')
            Model = POOL.get('ir.model')
            ModelField = POOL.get('ir.model.field')

            ProductCategory.create([{
                'name': 'Category1'
            }])
            model = Model.search([
                ('model', '=', 'product.category')
            ])
            fields = ModelField.search([
                ('ttype', '=', 'char'),
                ('model', '=', model[0])
            ])
            children_field = ModelField.search([
                ('ttype', '=', 'one2many'),
                ('model', '=', model[0])
            ])
            self.Menu.create([{
                'name': 'menu1',
                'unique_identifier': 'identifier',
                'website': self.site1.id,
                'model': model[0].id,
                'children_field': children_field[0].id,
                'uri_field': fields[0].id,
                'title_field': fields[0].id,
                'identifier_field': fields[0].id
            }])

            with app.test_client() as c:
                response = c.get('/')
                rv = literal_eval(response.data)
            self.assertTrue(rv['uri'], 'category-name')


def suite():
    suite = unittest.TestSuite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestMenuFor)
    )
    return suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
