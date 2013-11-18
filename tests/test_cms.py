# -*- coding: utf-8 -*-
'''

    nereid_cms test_cms

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT, \
    test_view, test_depends
from nereid.testing import NereidTestCase
from trytond.transaction import Transaction


class TestCMS(NereidTestCase):
    """Test CMS"""

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cms')

        self.Currency = POOL.get('currency.currency')
        self.ArticleCategory = POOL.get('nereid.cms.article.category')
        self.Article = POOL.get('nereid.cms.article')
        self.Folder = POOL.get('nereid.static.folder')
        self.File = POOL.get('nereid.static.file')
        self.Company = POOL.get('company.company')
        self.NereidUser = POOL.get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.Website = POOL.get('nereid.website')
        self.ArticleAttribute = POOL.get('nereid.cms.article.attribute')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')

        self.templates = {
            'home.jinja':
            '''{% for banner in get_banner_category("test-banners").banners %}
            {{ banner.get_html(banner.id)|safe }}
            {% endfor %}
            ''',
            'article-category.jinja': '{{ articles|length }}',
            'article.jinja': '{{ article.content }}',
        }

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
        url_map, = self.UrlMap.search([], limit=1)
        self.Website.create([{
            'name': 'localhost',
            'url_map': url_map,
            'company': company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'guest_user': guest_user,
            'currencies': [('set', [usd.id])],
        }])

        # Create an article category
        article_categ, = self.ArticleCategory.create([{
            'title': 'Test Categ',
            'unique_name': 'test-categ',
        }])

        self.Article.create([{
            'title': 'Test Article',
            'uri': 'test-article',
            'content': 'Test Content',
            'sequence': 10,
            'category': article_categ,
        }])

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('nereid_cms')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test_0010_article_category(self):
        "Successful rendering of an article_category page"
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/article-category/test-categ')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, '1')

    def test_0020_article(self):
        "Successful rendering of an article page"
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/article/test-article')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, 'Test Content')

    def test_0030_sitemapindex(self):
        '''
        Successful index rendering
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app(DEBUG=True)
            with app.test_client() as c:
                response = c.get('/sitemaps/article-category-index.xml')
                self.assertEqual(response.status_code, 200)

    def test_0040_category_sitemap(self):
        '''
        Successful rendering artical catagory sitemap
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/sitemaps/article-category-1.xml')
                self.assertEqual(response.status_code, 200)

    def test_0050_article_attribute(self):
        '''
        Test creating and deleting an Article with attributes
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT):
            article_category, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ',
            }])

            article1, = self.Article.create([{
                'title': 'Test Article',
                'uri': 'Test Article',
                'content': 'Test Content',
                'sequence': 10,
                'category': article_category.id,
                'attributes': [
                    ('create', [{
                        'name': 'google+',
                        'value': 'abc',
                    }])
                ]
            }])
            # Checks an article is created with attributes
            self.assert_(article1.id)
            self.assertEqual(self.ArticleAttribute.search([], count=True), 1)
            # Checks that if an article is deleted then respective attributes
            # are also deleted.
            self.Article.delete([article1])
            self.assertEqual(self.ArticleAttribute.search([], count=True), 0)


def suite():
    "CMS test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestCMS)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
