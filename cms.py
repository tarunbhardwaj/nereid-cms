# -*- coding: utf-8 -*-
'''

    Nereid CMS

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import time
from string import Template
import pytz
from datetime import datetime

from nereid import context_processor
from nereid import (
    render_template, request, login_required, jsonify, redirect, flash,
    abort, route
)
from nereid.helpers import slugify, url_for
from nereid.contrib.pagination import Pagination
from nereid.contrib.sitemap import SitemapIndex, SitemapSection
from werkzeug.utils import secure_filename
from werkzeug.contrib.atom import AtomFeed
from nereid.ctx import has_request_context

from trytond.pyson import Eval, Not, Equal, In
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend

try:
    from docutils.core import publish_parts
except ImportError:
    publish_parts = None

try:
    from markdown import markdown
except ImportError:
    markdown = None

__all__ = [
    'MenuItem', 'BannerCategory', 'Banner', 'Website',
    'ArticleCategory', 'Article', 'ArticleAttribute', 'NereidStaticFile',
    'ArticleCategoryRelation',
]
__metaclass__ = PoolMeta


class CMSMenuItemMixin(object):
    "Basic Mixin for cms menu item"

    def get_absolute_url(self, *args, **kwargs):
        """
        Return url for menu item
        """
        raise NotImplementedError(
            "Method 'get_absolute_url' is not implemented in %s" % self.__name__
        )

    def get_children(self, max_depth):
        """
        Return serialized menu_item for current menu_item children
        """
        return []

    def get_menu_item(self, max_depth):
        """
        Return huge dictionary with serialized menu item

        {
            title: <display name>,
            target: <href target>,
            link: <url>,  # if type_ is `static`
            children: [   # direct children or record children
                <menu_item children>,
                ...
            ],
            record: <instance of record>  # if type_ is `record`
        }
        """
        raise NotImplementedError(
            "Method 'get_menu_item' is not implemented in %s" % self.__name__
        )


class MenuItem(ModelSQL, ModelView, CMSMenuItemMixin):
    "Nereid CMS Menuitem"
    __name__ = 'nereid.cms.menuitem'
    _rec_name = 'title'

    type_ = fields.Selection([
        ('view', 'View'),
        ('static', 'Static'),
        ('record', 'Record'),
    ], 'Type', required=True, select=True)
    active = fields.Boolean('Active', select=True)
    title = fields.Char(
        'Title', required=True, select=True, translate=True, depends=['type_'],
        states={
            'required': Eval('type_') == 'static',
        }
    )
    link = fields.Char(
        'Link', states={
            'required': Eval('type_') == 'static',
            'invisible': Eval('type_') != 'static',
        }, depends=['type_']
    )
    target = fields.Selection([
        ('_self', 'Self'),
        ('_blank', 'Blank'),
    ], 'Target', required=True)

    parent = fields.Many2One(
        'nereid.cms.menuitem', 'Parent Menuitem', states={
            'required': Eval('type_') != 'view',
        }, depends=['type_'], select=True
    )
    child = fields.One2Many(
        'nereid.cms.menuitem', 'parent', string='Child Menu Items'
    )

    sequence = fields.Integer('Sequence', required=True, select=True)
    record = fields.Reference(
        'Record', selection='allowed_models', states={
            'required': Eval('type_') == 'record',
            'invisible': Eval('type_') != 'record',
        }, depends=['type_'],
    )

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        sql_table = cls.__table__()

        super(MenuItem, cls).__register__(module_name)

        table = TableHandler(cursor, cls, module_name)
        if table.column_exist('reference'):  # pragma: no cover
            table.not_null_action('unique_name', 'remove')

            # Delete the newly created record column
            table.drop_column('record')

            # Rename the reference column as record
            table.column_rename('reference', 'record', True)

            # The value of type depends on existence of record
            cursor.execute(*sql_table.update(
                columns=[sql_table.type_],
                values=['record'],
                where=(sql_table.record != None)  # noqa
            ))

    @classmethod
    def allowed_models(cls):
        return [
            (None, ''),
            ('nereid.cms.article.category', 'CMS Article Category'),
            ('nereid.cms.article', 'CMS Article'),
        ]

    @staticmethod
    def default_type_():
        return 'static'

    @staticmethod
    def default_target():
        return '_self'

    @staticmethod
    def default_sequence():
        return 10

    @staticmethod
    def default_active():
        return True

    @classmethod
    def __setup__(cls):
        super(MenuItem, cls).__setup__()
        cls._error_messages.update({
            'recursion_error':
            'Error ! You can not create recursive menuitems.',
        })
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def validate(cls, menus):
        super(MenuItem, cls).validate(menus)
        cls.check_recursion(menus)

    def get_rec_name(self, name):
        def _name(menuitem):
            if menuitem.parent:
                return _name(menuitem.parent) + ' / ' + menuitem.title
            else:
                return menuitem.title
        return _name(self)

    def get_menu_item(self, max_depth):
        """
        Return huge dictionary with serialized menu item

        {
            title: <display name>,
            target: <href target>,
            link: <url>,  # if type_ is `static`
            children: [   # direct children or record children
                <menu_item children>,
                ...
            ],
            record: <instance of record>  # if type_ is `record`
        }
        """
        res = {
            'title': self.title,
            'target': self.target,
            'type_': self.type_,
        }
        if self.type_ == 'static':
            res['link'] = self.link

        if self.type_ == 'record':
            res['record'] = self.record
            res['link'] = self.record.get_absolute_url()

        if max_depth:
            res['children'] = self.get_children(max_depth=max_depth - 1)

        if self.type_ == 'record' and not res.get('children') and max_depth:
            res['children'] = self.record.get_children(
                max_depth=max_depth - 1
            )
        return res

    def get_children(self, max_depth):
        """
        Return serialized menu_item for current menu_item children
        """
        children = self.search([
            ('parent', '=', self.id),
            ('active', '=', True)
        ])
        return [
            child.get_menu_item(max_depth=max_depth - 1) for child in children
        ]

    def get_absolute_url(self, *args, **kwargs):
        """
        Return url for menu item
        """
        if self.type_ == 'record':
            return self.record.get_absolute_url(*args, **kwargs)
        return self.link


class BannerCategory(ModelSQL, ModelView):
    """Collection of related Banners"""
    __name__ = 'nereid.cms.banner.category'

    name = fields.Char('Name', required=True, select=True)
    banners = fields.One2Many(
        'nereid.cms.banner', 'category', 'Banners',
        context={'published': True}
    )
    website = fields.Many2One('nereid.website', 'WebSite', select=True)
    published_banners = fields.Function(
        fields.One2Many(
            'nereid.cms.banner', 'category', 'Published Banners'
        ), 'get_published_banners'
    )

    @classmethod
    @context_processor('get_banner_category')
    def get_banner_category(cls, uri, silent=True):
        """Returns the browse record of the article category given by uri
        """
        category = cls.search([
            ('name', '=', uri),
            ('website', '=', request.nereid_website.id)
        ], limit=1)
        if not category and not silent:
            raise RuntimeError("Banner category %s not found" % uri)
        return category[0] if category else None

    def get_published_banners(self, name):
        """
        Get the published banners.
        """
        NereidBanner = Pool().get('nereid.cms.banner')
        res = []
        banners = NereidBanner.search([
            ('state', '=', 'published'),
            ('category', '=', self.id)
        ])
        for banner in NereidBanner.browse(banners):
            res.append(banner.id)
        return res


class Banner(Workflow, ModelSQL, ModelView):
    """Banner for CMS."""
    __name__ = 'nereid.cms.banner'

    name = fields.Char('Name', required=True, select=True)
    description = fields.Text('Description')
    category = fields.Many2One(
        'nereid.cms.banner.category', 'Category', required=True, select=True
    )
    sequence = fields.Integer('Sequence', select=True)

    # Type related data
    type = fields.Selection([
        ('image', 'Image'),
        ('remote_image', 'Remote Image'),
        ('custom_code', 'Custom Code'),
    ], 'Type', required=True)
    file = fields.Many2One(
        'nereid.static.file', 'File',
        states={
            'required': Equal(Eval('type'), 'image'),
            'invisible': Not(Equal(Eval('type'), 'image'))
        }
    )
    remote_image_url = fields.Char(
        'Remote Image URL',
        states={
            'required': Equal(Eval('type'), 'remote_image'),
            'invisible': Not(Equal(Eval('type'), 'remote_image'))
        }
    )
    custom_code = fields.Text(
        'Custom Code', translate=True,
        states={
            'required': Equal(Eval('type'), 'custom_code'),
            'invisible': Not(Equal(Eval('type'), 'custom_code'))
        }
    )

    # Presentation related Data
    height = fields.Integer(
        'Height',
        states={
            'invisible': Not(In(Eval('type'), ['image', 'remote_image']))
        }
    )
    width = fields.Integer(
        'Width',
        states={
            'invisible': Not(In(Eval('type'), ['image', 'remote_image']))
        }
    )
    alternative_text = fields.Char(
        'Alternative Text', translate=True,
        states={
            'invisible': Not(In(Eval('type'), ['image', 'remote_image']))
        }
    )
    click_url = fields.Char(
        'Click URL', translate=True,
        states={
            'invisible': Not(In(Eval('type'), ['image', 'remote_image']))
        }
    )

    state = fields.Selection([
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('archived', 'Archived')
    ], 'State', required=True, select=True, readonly=True)
    reference = fields.Reference('Reference', selection='allowed_models')

    @classmethod
    def __setup__(cls):
        super(Banner, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._transitions |= set((
                ('draft', 'published'),
                ('archived', 'published'),
                ('published', 'archived'),
        ))
        cls._buttons.update({
            'archive': {
                'invisible': Eval('state') != 'published',
            },
            'publish': {
                'invisible': Eval('state') == 'published',
            }
        })

    @classmethod
    @ModelView.button
    @Workflow.transition('archived')
    def archive(cls, banners):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('published')
    def publish(cls, banners):
        pass

    def get_html(self):
        """Return the HTML content"""
        StaticFile = Pool().get('nereid.static.file')

        banner = self.read(
            [self], [
                'type', 'click_url', 'file',
                'remote_image_url', 'custom_code', 'height', 'width',
                'alternative_text', 'click_url'
            ]
        )[0]

        if banner['type'] == 'image':
            # replace the `file` in the dictionary with the complete url
            # that is required to render the image based on static file
            file = StaticFile(banner['file'])
            banner['file'] = file.url
            image = Template(
                u'<a href="$click_url">'
                u'<img src="$file" alt="$alternative_text"'
                u' width="$width" height="$height"/>'
                u'</a>'
            )
            return image.substitute(**banner)
        elif banner['type'] == 'remote_image':
            image = Template(
                u'<a href="$click_url">'
                u'<img src="$remote_image_url" alt="$alternative_text"'
                u' width="$width" height="$height"/>'
                u'</a>')
            return image.substitute(**banner)
        elif banner['type'] == 'custom_code':
            return banner['custom_code']

    @classmethod
    def allowed_models(cls):
        MenuItem = Pool().get('nereid.cms.menuitem')

        return MenuItem.allowed_models()

    @staticmethod
    def default_type():
        return 'image'

    @staticmethod
    def default_state():
        if 'published' in Transaction().context:
            return 'published'
        return 'draft'


class ArticleCategory(ModelSQL, ModelView, CMSMenuItemMixin):
    "Article Categories"
    __name__ = 'nereid.cms.article.category'
    _rec_name = 'title'

    title = fields.Char(
        'Title', size=100, translate=True, required=True, select=True
    )
    unique_name = fields.Char(
        'Unique Name', required=True, select=True,
        help='Unique Name is used as the uri.'
    )
    active = fields.Boolean('Active', select=True)
    description = fields.Text('Description', translate=True)
    template = fields.Char('Template', required=True)
    articles = fields.Many2Many(
        'nereid.cms.category-article', 'category', 'article', 'Article',
        context={'published': True}
    )

    # Article Category can have a banner
    banner = fields.Many2One('nereid.cms.banner', 'Banner')
    sort_order = fields.Selection([
        ('older_first', 'Older First'),
        ('recent_first', 'Recent First'),
    ], 'Sort Order')
    published_articles = fields.Function(
        fields.One2Many(
            'nereid.cms.article', 'category', 'Published Articles'
        ), 'get_published_articles'
    )
    articles_per_page = fields.Integer('Articles per Page', required=True)

    @staticmethod
    def default_sort_order():
        return 'recent_first'

    @staticmethod
    def default_active():
        'Return True'
        return True

    @staticmethod
    def default_template():
        return 'article-category.jinja'

    @classmethod
    def __setup__(cls):
        super(ArticleCategory, cls).__setup__()
        cls._sql_constraints += [
            ('unique_name', 'UNIQUE(unique_name)',
                'The Unique Name of the Category must be unique.'),
        ]

    @fields.depends('title', 'unique_name')
    def on_change_title(self):
        res = {}
        if self.title and not self.unique_name:
            res['unique_name'] = slugify(self.title)
        return res

    @staticmethod
    def default_articles_per_page():
        return 10

    @classmethod
    @route('/article-category/<uri>/')
    @route('/article-category/<uri>/<int:page>')
    def render(cls, uri, page=1):
        """
        Renders the category
        """
        Article = Pool().get('nereid.cms.article')

        # Find in cache or load from DB
        try:
            category, = cls.search([('unique_name', '=', uri)])
        except ValueError:
            abort(404)

        order = []
        if category.sort_order == 'recent_first':
            order.append(('write_date', 'DESC'))
        elif category.sort_order == 'older_first':
            order.append(('write_date', 'ASC'))

        articles = Pagination(
            Article, [('categories', '=', category.id)], page,
            category.articles_per_page, order=order
        )
        return render_template(
            category.template, category=category, articles=articles)

    @classmethod
    @context_processor('get_article_category')
    def get_article_category(cls, uri, silent=True):
        """Returns the browse record of the article category given by uri
        """
        category = cls.search([('unique_name', '=', uri)], limit=1)
        if not category and not silent:
            raise RuntimeError("Article category %s not found" % uri)
        return category[0] if category else None

    @classmethod
    @route('/sitemaps/article-category-index.xml')
    def sitemap_index(cls):
        index = SitemapIndex(cls, [])
        return index.render()

    @classmethod
    @route('/sitemaps/article-category-<int:page>.xml')
    def sitemap(cls, page):
        sitemap_section = SitemapSection(cls, [], page)
        sitemap_section.changefreq = 'daily'
        return sitemap_section.render()

    def get_absolute_url(self, **kwargs):
        return url_for(
            'nereid.cms.article.category.render',
            uri=self.unique_name, **kwargs
        )

    def get_published_articles(self, name):
        """
        Get the published articles.
        """
        NereidArticle = Pool().get('nereid.cms.article')

        articles = NereidArticle.search([
            ('state', '=', 'published'),
            ('categories', '=', self.id)
        ])
        return map(int, articles)

    def get_children(self, max_depth):
        """
        Return serialized menu_item for current menu_item children
        """
        NereidArticle = Pool().get('nereid.cms.article')

        articles = NereidArticle.search([
            ('state', '=', 'published'),
            ('categories', '=', self.id)
        ])
        return [
            article.get_menu_item(max_depth=max_depth - 1)
            for article in articles
        ]

    def serialize(self, purpose=None):
        """
        Article category serialize method
        """
        if purpose == 'atom':
            return {
                'term': self.unique_name,
            }
        elif hasattr(super(ArticleCategory, self), 'serialize'):
            return super(ArticleCategory, self).serialize(purpose=purpose)

    @classmethod
    @route('/article-category/<uri>.atom')
    def atom_feed(cls, uri):
        """
        Returns atom feed for articles published under a particular category.
        """
        Article = Pool().get('nereid.cms.article')

        try:
            category, = cls.search([
                ('unique_name', '=', uri),
            ], limit=1)
        except ValueError:
            abort(404)

        feed = AtomFeed(
            "Articles by Category %s" % category.unique_name,
            feed_url=request.url, url=request.host_url
        )
        for article_id in category.published_articles:
            feed.add(**Article(article_id).serialize(purpose='atom'))

        return feed.get_response()


class Article(Workflow, ModelSQL, ModelView, CMSMenuItemMixin):
    "CMS Articles"
    __name__ = 'nereid.cms.article'
    _rec_name = 'uri'

    uri = fields.Char('URI', required=True, select=True, translate=True)
    title = fields.Char('Title', required=True, select=True, translate=True)
    content = fields.Text('Content', required=True, translate=True)
    template = fields.Char('Template', required=True)
    active = fields.Boolean('Active', select=True)
    image = fields.Many2One('nereid.static.file', 'Image')
    employee = fields.Many2One('company.employee', 'Employee')
    author = fields.Many2One('nereid.user', 'Author')
    published_on = fields.Date('Published On')
    publish_date = fields.Function(
        fields.Char('Publish Date'), 'get_publish_date'
    )
    sequence = fields.Integer('Sequence', required=True, select=True)
    reference = fields.Reference('Reference', selection='allowed_models')
    description = fields.Text('Short Description')
    attributes = fields.One2Many(
        'nereid.cms.article.attribute', 'article', 'Attributes'
    )
    categories = fields.Many2Many(
        'nereid.cms.category-article', 'article', 'category', 'Categories',
    )
    content_type = fields.Selection(
        'content_type_selection', 'Content Type',
        required=True
    )
    # Article can have a banner
    banner = fields.Many2One('nereid.cms.banner', 'Banner')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived')
    ], 'State', required=True, select=True, readonly=True)

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        table = TableHandler(cursor, cls, module_name)

        if not table.column_exist('employee'):
            table.column_rename('author', 'employee')

        super(Article, cls).__register__(module_name)

    @classmethod
    def __setup__(cls):
        super(Article, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._transitions |= set((
                ('draft', 'published'),
                ('published', 'draft'),
                ('published', 'archived'),
                ('archived', 'draft'),
        ))
        cls._buttons.update({
            'archive': {
                'invisible': Eval('state') != 'published',
            },
            'publish': {
                'invisible': Eval('state').in_(['published', 'archived']),
            },
            'draft': {
                'invisible': Eval('state') == 'draft',
            }
        })

    @classmethod
    def content_type_selection(cls):
        """
        Returns a selection for content_type.
        """
        default_types = [
            ('html', 'HTML'),
            ('plain', 'Plain Text')
        ]

        if markdown:
            default_types.append(('markdown', 'Markdown'))
        if publish_parts:
            default_types.append(('rst', 'reStructured TeXT'))

        return default_types

    @classmethod
    def default_content_type(cls):
        """
        Default content_type.
        """
        return 'plain'

    def __html__(self):
        """
        Uses content_type field to generate html content.
        Concept from Jinja2's Markup class.
        """
        if self.content_type == 'rst':
            if publish_parts:
                res = publish_parts(self.content, writer_name='html')
                return res['html_body']
            self.raise_user_error(
                "`docutils` not installed, to render rst articles."
            )
        if self.content_type == 'markdown':
            if markdown:
                return markdown(self.content)
            self.raise_user_error(
                "`markdown` not installed, to render markdown article."
            )
        return self.content

    @classmethod
    @ModelView.button
    @Workflow.transition('archived')
    def archive(cls, articles):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('published')
    def publish(cls, articles):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, articles):
        pass

    @classmethod
    def allowed_models(cls):
        MenuItem = Pool().get('nereid.cms.menuitem')

        return MenuItem.allowed_models()

    @staticmethod
    def default_active():
        return True

    @fields.depends('title', 'uri')
    def on_change_title(self):
        res = {}
        if self.title and not self.uri:
            res['uri'] = slugify(self.title)
        return res

    @staticmethod
    def default_template():
        return 'article.jinja'

    @staticmethod
    def default_employee():
        User = Pool().get('res.user')

        if 'employee' in Transaction().context:
            return Transaction().context['employee']

        user = User(Transaction().user)
        if user.employee:
            return user.employee.id

        if has_request_context() and request.nereid_user.employee:
            return request.nereid_user.employee.id

    @staticmethod
    def default_author():
        if has_request_context():
            return request.nereid_user.id

    @staticmethod
    def default_published_on():
        Date = Pool().get('ir.date')
        return Date.today()

    @classmethod
    @route('/article/<uri>')
    def render(cls, uri):
        """
        Renders the template
        """
        try:
            article, = cls.search([
                ('uri', '=', uri),
                ('state', '=', 'published'),
            ])
        except ValueError:
            abort(404)
        return render_template(article.template, article=article)

    @classmethod
    @route('/sitemaps/article-index.xml')
    def sitemap_index(cls):
        index = SitemapIndex(cls, [])
        return index.render()

    @classmethod
    @route('/sitemaps/article-<int:page>.xml')
    def sitemap(cls, page):
        sitemap_section = SitemapSection(cls, [], page)
        sitemap_section.changefreq = 'daily'
        return sitemap_section.render()

    @classmethod
    def get_publish_date(cls, records, name):
        """
        Return publish date to render on view
        """
        res = {}
        for record in records:
            res[record.id] = str(record.published_on)
        return res

    def get_absolute_url(self, **kwargs):
        return url_for(
            'nereid.cms.article.render', uri=self.uri, **kwargs
        )

    @staticmethod
    def default_state():
        if 'published' in Transaction().context:
            return 'published'
        return 'draft'

    def get_menu_item(self, max_depth):
        """
        Return huge dictionary with serialized article category for menu item

        {
            title: <display name>,
            link: <url>,
            record: <instance of record>  # if type_ is `record`
        }
        """
        return {
            'record': self,
            'title': self.title,
            'link': self.get_absolute_url(),
        }

    def atom_id(self):
        """
        Returns an atom ID for the article
        """
        return (
            'tag:' + request.nereid_website.name + ',' +
            self.publish_date + ':Article/' + str(self.id)
        )

    def atom_publish_date(self):
        """
        Returns the article's publish date with timezone set as UTC
        """
        return pytz.utc.localize(
            datetime.combine(self.published_on, datetime.min.time())
        )

    def serialize(self, purpose=None):
        """
        Serialize Article records
        """
        if purpose == 'atom':
            # The keys in the dictionary returned are used by Werkzeug's
            # AtomFeed class.
            return {
                'id': self.atom_id(),
                'title': self.title,
                'author': (
                    self.author.serialize(purpose=purpose) if self.author
                    else None
                ),
                'content': self.content,
                'content_type': (
                    'text' if self.content_type == 'plain' else 'html'
                ),
                'link': {
                    'rel': 'alternate',
                    'type': 'text/html',
                    'href': self.get_absolute_url(external=True),
                },
                'category': [
                    category.serialize(purpose=purpose)
                    for category in self.categories
                ],
                'published': self.atom_publish_date(),
                'updated': self.write_date or self.atom_publish_date(),
            }
        elif hasattr(super(Article, self), 'serialize'):
            return super(Article, self).serialize(purpose=purpose)

    @classmethod
    @route('/article/all.atom')
    def atom_feed(cls):
        """
        Renders the atom feed for all articles.
        """
        feed = AtomFeed(
            "All Articles", feed_url=request.url, url=request.host_url
        )
        for article in cls.search([
            ('state', '=', 'published')
        ]):
            feed.add(**article.serialize(purpose='atom'))

        return feed.get_response()


class ArticleAttribute(ModelSQL, ModelView):
    "Articles Attribute"
    __name__ = 'nereid.cms.article.attribute'
    _rec_name = 'value'

    name = fields.Selection([
        ('', None),
        ('google+', 'Google+'),
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('github', 'Github'),
        ('linked-in', 'Linked-in'),
        ('blogger', 'Blogger'),
        ('tumblr', 'Tumblr'),
        ('website', 'Website'),
        ('phone', 'Phone'),
    ], 'Name', required=True, select=True)
    value = fields.Char('Value', required=True)
    article = fields.Many2One(
        'nereid.cms.article', 'Article', ondelete='CASCADE', required=True,
        select=True,
    )


class NereidStaticFile:
    "Nereid Static File"
    __name__ = 'nereid.static.file'

    def serialize(self):
        """
        Serialize this object
        """
        return {
            'name': self.name,
            'get_url': self.url,
        }


class Website:
    "Nereid Website"
    __name__ = 'nereid.website'

    cms_static_folder = fields.Many2One(
        'nereid.static.folder', "CMS Static Folder", ondelete='RESTRICT',
        select=True,
    )

    @classmethod
    @route('/cms/upload/<upload_type>', methods=['POST'])
    @login_required
    def cms_static_upload(cls, upload_type):
        """
        Upload the file for cms
        """
        StaticFile = Pool().get("nereid.static.file")

        file = request.files['file']
        if file:
            static_file = StaticFile.create({
                'folder': request.nereid_website.cms_static_folder,
                'name': '_'.join([
                    str(int(time.time())),
                    secure_filename(file.filename),
                ]),
                'type': upload_type,
                'file_binary': file.read(),
            })
            if request.is_xhr:
                return jsonify(success=True, item=static_file.serialize())

            flash("File uploaded")
        if request.is_xhr:
            return jsonify(success=False)
        return redirect(request.referrer)

    @classmethod
    @route('/cms/browse', methods=['POST'])
    @route('/cms/browse/<int:page>', methods=['GET'])
    @login_required
    def cms_static_list(cls, page=1):
        """
            Return JSON with list of all files inside cms static folder
        """
        StaticFile = Pool().get("nereid.static.file")

        files = Pagination(
            StaticFile, [
                ('folder', '=', request.nereid_website.cms_static_folder.id)
            ], page, 10
        )
        return jsonify(items=[
            item.serialize() for item in files
        ])


class ArticleCategoryRelation(ModelSQL):
    """
    Relationshiop between article and category
    """
    __name__ = 'nereid.cms.category-article'

    category = fields.Many2One(
        'nereid.cms.article.category', 'Category', select=True
    )
    article = fields.Many2One(
        'nereid.cms.article', 'Article', select=True
    )
