# -*- coding: utf-8 -*-
'''

    nereid_cms test_banner

    :copyright: (c) 2010-2013 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import unittest

from lxml import objectify
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from nereid.testing import NereidTestCase
from trytond.transaction import Transaction


class TestBanner(NereidTestCase):
    """Test Banners"""

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cms')

        self.Currency = POOL.get('currency.currency')
        self.Site = POOL.get('nereid.website')
        self.BannerCategory = POOL.get('nereid.cms.banner.category')
        self.Banner = POOL.get('nereid.cms.banner')
        self.Folder = POOL.get('nereid.static.folder')
        self.File = POOL.get('nereid.static.file')
        self.Company = POOL.get('company.company')
        self.NereidUser = POOL.get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.NereidWebsite = POOL.get('nereid.website')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')

        self.templates = {
            'home.jinja':
            '''
                {% for banner in get_banner_category("test-banners").banners %}
                    {{ banner.get_html()|safe }}
                {% endfor %}
            ''',
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
            'company': company,
        }])
        registered_party, = self.Party.create([{
            'name': 'Registered User'
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': registered_party,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': company,
        }])

        # Create website
        url_map, = self.UrlMap.search([], limit=1)
        en_us, = self.Language.search([('code', '=', 'en_US')])
        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id
        }])
        return self.NereidWebsite.create([{
            'name': 'localhost',
            'url_map': url_map,
            'company': company,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'currencies': [('add', [usd.id])],
        }])[0]

    def test_0010_banner_categ(self):
        """All banners in published state.

        The banners attribute of the banner category returns all the banners
        irrespective of the status. The attribute published_banners must only
        return the active banners.

        This test creates four banner of which two are later archived, and the
        test ensures that there are only two published banners
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            banner_categ1, = self.BannerCategory.create([{
                'name': 'CAT-A'
            }])
            banner_categ2, = self.BannerCategory.create([{
                'name': 'CAT-B'
            }])

            self.Banner.create([{
                'name': 'CAT-A1',
                'category': banner_categ1,
                'type': 'custom_code',
                'custom_code': 'Custom code A1',
                'state': 'archived'
            }])
            self.Banner.create([{
                'name': 'CAT-A2',
                'category': banner_categ1,
                'type': 'custom_code',
                'custom_code': 'Custom code A2',
                'state': 'published'
            }])
            self.Banner.create([{
                'name': 'CAT-B1',
                'category': banner_categ2,
                'type': 'custom_code',
                'custom_code': 'Custom code B1',
                'state': 'archived'
            }])
            self.Banner.create([{
                'name': 'CAT-B2',
                'category': banner_categ2,
                'type': 'custom_code',
                'custom_code': 'Custom code B2',
                'state': 'published'
            }])

            self.assertEqual(len(banner_categ1.banners), 2)
            self.assertEqual(len(banner_categ1.banners), 2)
            self.assertEqual(len(banner_categ1.published_banners), 1)
            self.assertEqual(len(banner_categ1.published_banners), 1)

    def test_0020_banner_image(self):
        """
        Test the image type banner created using static files
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            site = self.setup_defaults()

            category, = self.BannerCategory.create([{
                'name': 'test-banners',
                'website': site
            }])
            folder, = self.Folder.create([{
                'description': 'image',
                'folder_name': 'image'
            }])
            file, = self.File.create([{
                'name': 'logo',
                'folder': folder,
            }])
            self.Banner.create([{
                'name': 'Test Image Banner',
                'category': category,
                'type': 'image',
                'file': file,
                'state': 'published'
            }])

            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/')
                html = objectify.fromstring(response.data)
                self.assertEqual(
                    html.find('img').get('src'),
                    '/static-file/image/logo'
                )

    def test_0030_remote_image(self):
        """
        Test the remote image type banner
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            site = self.setup_defaults()
            category, = self.BannerCategory.create([{
                'name': 'test-banners',
                'website': site
            }])
            self.Banner.create([{
                'name': 'Test Remote Image Banner',
                'category': category,
                'type': 'remote_image',
                'remote_image_url': 'http://some/remote/url',
                'state': 'published'
            }])

            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/')
                html = objectify.fromstring(response.data)
                self.assertEqual(
                    html.find('img').get('src'),
                    'http://some/remote/url'
                )

    def test_0040_custom_code(self):
        """
        Test the custom code
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            site = self.setup_defaults()

            category, = self.BannerCategory.create([{
                'name': 'test-banners',
                'website': site
            }])
            self.Banner.create([{
                'name': 'Test Remote Image Banner',
                'category': category,
                'type': 'custom_code',
                'custom_code': 'some ultra complex custom code',
                'state': 'published'
            }])

            app = self.get_app()
            with app.test_client() as c:
                response = c.get('/')
                self.assertTrue(
                    'some ultra complex custom code' in response.data,
                )


class TestGetHtml(NereidTestCase):
    """Test Get Html for Banners
    """

    def setUp(self):
        trytond.tests.test_tryton.install_module('nereid_cms')

        self.Currency = POOL.get('currency.currency')
        self.Banner = POOL.get('nereid.cms.banner')
        self.BannerCategory = POOL.get('nereid.cms.banner.category')
        self.File = POOL.get('nereid.static.file')
        self.Folder = POOL.get('nereid.static.folder')
        self.Company = POOL.get('company.company')
        self.NereidUser = POOL.get('nereid.user')
        self.UrlMap = POOL.get('nereid.url_map')
        self.Language = POOL.get('ir.lang')
        self.NereidWebsite = POOL.get('nereid.website')
        self.Party = POOL.get('party.party')
        self.Locale = POOL.get('nereid.website.locale')

        self.templates = {
            'home.jinja':
            '''
                {% for b in get_banner_category('Category A').banners -%}
                {{ b.get_html()|safe }}
                {%- endfor %}
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
            'company': company,
        }])
        registered_party, = self.Party.create([{
            'name': 'Registered User'
        }])
        self.registered_user, = self.NereidUser.create([{
            'party': registered_party,
            'display_name': 'Registered User',
            'email': 'email@example.com',
            'password': 'password',
            'company': company,
        }])

        # Create website
        url_map, = self.UrlMap.search([], limit=1)
        en_us, = self.Language.search([('code', '=', 'en_US')])
        self.locale_en_us, = self.Locale.create([{
            'code': 'en_US',
            'language': en_us.id,
            'currency': usd.id
        }])
        return self.NereidWebsite.create([{
            'name': 'localhost',
            'url_map': url_map,
            'company': company,
            'application_user': USER,
            'default_locale': self.locale_en_us.id,
            'currencies': [('add', [usd.id])],
        }])[0]

    def test_0010_get_html(self):
        """
        Get Html for banners with type `image`.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            site = self.setup_defaults()

            banner_category, = self.BannerCategory.create([{
                'name': 'Category A',
                'website': site,
            }])

            image, = self.Folder.create([{
                'description': 'image',
                'folder_name': 'image'
            }])
            file, = self.File.create([{
                'name': 'logo',
                'folder': image,
            }])
            self.Banner.create([{
                'name': 'Test Banner1',
                'category': banner_category,
                'type': 'image',
                'file': file,
                'state': 'published'
            }])

            app = self.get_app()
            with app.test_client() as c:
                rv = c.get('/')
                html = objectify.fromstring(rv.data)
                self.assertEqual(
                    html.find('img').get('src'),
                    '/static-file/image/logo'
                )

    def test_0020_get_html(self):
        """
        Get Html for banners with type `remote_image`.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            banner_category, = self.BannerCategory.create([{
                'name': 'Category B'
            }])

            banner, = self.Banner.create([{
                'name': 'Test Banner2',
                'category': banner_category,
                'type': 'remote_image',
                'remote_image_url':
                    'http://profile.ak.fbcdn.net/hprofile-ak-snc4'
                    '/187819_122589627793765_7532740_n.jpg',
                'state': 'published'
            }])
            rv = banner.get_html()
            html = objectify.fromstring(rv)
            self.assertEqual(
                html.find('img').get('src'), banner.remote_image_url
            )

    def test_0030_get_html(self):
        """
        Get Html for banners with type `custom_code`.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            banner_category, = self.BannerCategory.create([{
                'name': 'Category C'
            }])

            banner, = self.Banner.create([{
                'name': 'Test Banner3',
                'category': banner_category,
                'type': 'custom_code',
                'custom_code': 'Custom code for Test Banner3',
                'state': 'published'
            }])
            rv = banner.get_html()
            self.assertEqual(rv, banner.custom_code)


def suite():
    "Nereid CMS Banners test suite"
    test_suite = unittest.TestSuite()
    test_suite.addTests([
        unittest.TestLoader().loadTestsFromTestCase(TestBanner),
        unittest.TestLoader().loadTestsFromTestCase(TestGetHtml),
    ])
    return test_suite


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
