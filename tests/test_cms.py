# -*- coding: utf-8 -*-
'''

    nereid_cms test_cms

    :copyright: (c) 2010-2015 by Openlabs Technologies & Consulting (P) Ltd.
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
        self.Language = POOL.get('ir.lang')
        self.Website = POOL.get('nereid.website')
        self.ArticleAttribute = POOL.get('nereid.cms.article.attribute')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')
        self.MenuItem = POOL.get('nereid.cms.menuitem')

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
        self.Website.create([{
            'name': 'localhost',
            'company': company.id,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'currencies': [('add', [usd.id])],
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
            'categories': [('add', [article_categ.id])],
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

    def test_0090_article_states(self):
        """All articles in published state.

        The articles attribute of the article category returns all the articles
        irrespective of the status. The attribute published_articles must only
        return the active articles.

        This test creates four articles of which two are later archived, and
        the test ensures that there are only two published articles
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            article_categ1, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ1',
            }])
            article_categ2, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ2',
            }])

            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article1',
                'content': 'Test Content',
                'sequence': 10,
                'categories': [('add', [article_categ1.id])],
                'state': 'archived'
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article2',
                'content': 'Test Content',
                'sequence': 20,
                'categories': [('add', [article_categ1.id])],
                'state': 'published'
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article3',
                'content': 'Test Content',
                'sequence': 30,
                'categories': [('add', [article_categ2.id])],
                'state': 'archived'
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article4',
                'content': 'Test Content',
                'sequence': 40,
                'categories': [('add', [article_categ2.id])],
                'state': 'published'
            }])

            self.assertEqual(len(article_categ1.articles), 2)
            self.assertEqual(len(article_categ2.articles), 2)
            self.assertEqual(len(article_categ1.published_articles), 1)
            self.assertEqual(len(article_categ2.published_articles), 1)

    def test_0010_article_category(self):
        "Successful rendering of an article_category page"
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/article-category/test-categ/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, '1')

    def test_0020_article(self):
        "Successful rendering of an article page"
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            # Publish the article first
            article, = self.Article.search([
                ('uri', '=', 'test-article')
            ])
            self.Article.publish([article])

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
                'categories': [('add', [article_category.id])],
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

    def test_0055_article_content(self):
        """
        Tests that the article has been rendered properly.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            article_category, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ',
            }])

            article1, = self.Article.create([{
                'title': 'Test Article',
                'uri': 'Test Article',
                'content': 'Test Content',
                'content_type': 'plain',
                'sequence': 10,
                'categories': [('add', [article_category.id])],
                'attributes': [
                    ('create', [{
                        'name': 'google+',
                        'value': 'abc',
                    }])
                ]
            }])

            # Plain content.
            self.assertEqual(article1.__html__(), article1.content)

            # HTML content.
            article1.content = '<html><body><p>A paragraph.</p></body></html>'
            article1.content_type = 'html'

            self.assertEqual(article1.__html__(), article1.content)

            # Markdown content.
            article1.content = '**This is strong in markdown**'
            article1.content_type = 'markdown'
            article1.save()

            self.assertIn(
                '<strong>This is strong in markdown</strong>',
                article1.__html__()
            )

            article1.content = '`A blockquote`'
            article1.save()

            self.assertIn(
                '<p><code>A blockquote</code></p>',
                article1.__html__()
            )

            # RST content.
            article1.content = '*This is emphasis in rst*'
            article1.content_type = 'rst'
            article1.save()

            self.assertIn(
                '<em>This is emphasis in rst</em>',
                article1.__html__()
            )

    def test_0060_atom_feeds(self):
        """
        Tests that the render of atom xml feeds is working correctly.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()
            app = self.get_app()

            article_categ1, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ1',
            }])
            article_categ2, = self.ArticleCategory.create([{
                'title': 'Test Categ',
                'unique_name': 'test-categ2',
            }])

            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article1',
                'content': 'Test Content',
                'sequence': 10,
                'categories': [('add', [article_categ1.id])],
                'state': 'published',
                'author': self.registered_user.id,
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article2',
                'content': 'Test Content',
                'sequence': 20,
                'categories': [('add', [article_categ1.id])],
                'state': 'published',
                'author': self.registered_user.id,
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article3',
                'content': 'Test Content',
                'sequence': 30,
                'categories': [('add', [article_categ2.id])],
                'state': 'archived',
                'author': self.registered_user.id,
            }])
            self.Article.create([{
                'title': 'Test Article',
                'uri': 'test-article4',
                'content': 'Test Content',
                'sequence': 40,
                'categories': [('add', [article_categ2.id])],
                'state': 'published',
                'author': self.registered_user.id,
            }])

            with app.test_client() as c:
                # Try rendering all articles.
                rv = c.get('/article/all.atom')
                self.assertEqual(
                    rv.data.count('<entry'),
                    len(self.Article.search([('state', '=', 'published')]))
                )

                rv = c.get(
                    '/article-category/%s.atom' % article_categ1.unique_name
                )
                self.assertEqual(
                    rv.data.count('<entry'),
                    len(article_categ1.published_articles)
                )

                rv = c.get('/article-author/%d.atom' % self.registered_user.id)
                self.assertEqual(
                    rv.data.count('<entry'),
                    len(self.Article.search([
                        ('author', '=', self.registered_user.id),
                        ('state', '=', 'published'),
                    ]))
                )

                # Try rendering for a category that does not exist.
                rv = c.get('/article-category/%d.atom' % 70)
                self.assertEqual(rv.status_code, 404)


def suite():
    "CMS test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestCMS)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
