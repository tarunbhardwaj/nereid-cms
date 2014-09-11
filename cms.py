# -*- coding: utf-8 -*-
'''

    Nereid CMS

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''
import time
from string import Template

from nereid import context_processor
from nereid import (
    render_template, current_app, cache, request, login_required, jsonify,
    redirect, flash, abort, route
)
from nereid.helpers import slugify, url_for, key_from_list
from nereid.contrib.pagination import Pagination
from nereid.contrib.sitemap import SitemapIndex, SitemapSection
from werkzeug.utils import secure_filename
from nereid.ctx import has_request_context

from trytond.pyson import Eval, Not, Equal, Bool, In
from trytond.model import ModelSQL, ModelView, fields, Workflow
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend

__all__ = [
    'CMSLink', 'Menu', 'MenuItem', 'BannerCategory', 'Banner', 'Website',
    'ArticleCategory', 'Article', 'ArticleAttribute', 'NereidStaticFile',
    'ArticleCategoryRelation',
]
__metaclass__ = PoolMeta


class CMSLink(ModelSQL, ModelView):
    """
    CMS link

    (c) 2010 Tryton Project
    """
    __name__ = 'nereid.cms.link'

    name = fields.Char('Name', required=True, translate=True, select=True)
    model = fields.Selection('models_get', 'Model', required=True, select=True)
    priority = fields.Integer('Priority')

    @classmethod
    def __setup__(cls):
        super(CMSLink, cls).__setup__()
        cls._order.insert(0, ('priority', 'ASC'))

    @staticmethod
    def default_priority():
        return 5

    @staticmethod
    def models_get():
        Model = Pool().get('ir.model')
        res = []
        for model in Model.search([]):
            res.append((model.model, model.name))
        return res


class Menu(ModelSQL, ModelView):
    "Nereid CMS Menu"
    __name__ = 'nereid.cms.menu'

    name = fields.Char('Name', required=True)
    unique_identifier = fields.Char(
        'Unique Identifier', required=True, select=True
    )
    description = fields.Text('Description')
    website = fields.Many2One('nereid.website', 'WebSite')
    active = fields.Boolean('Active')

    model = fields.Many2One('ir.model', 'Tryton Model', required=True)
    children_field = fields.Many2One(
        'ir.model.field', 'Children',
        depends=['model'],
        domain=[
            ('model', '=', Eval('model')),
            ('ttype', '=', 'one2many')
        ], required=True
    )
    uri_field = fields.Many2One(
        'ir.model.field', 'URI Field',
        depends=['model'],
        domain=[
            ('model', '=', Eval('model')),
            ('ttype', '=', 'char')
        ], required=True
    )
    title_field = fields.Many2One(
        'ir.model.field', 'Title Field',
        depends=['model'],
        domain=[
            ('model', '=', Eval('model')),
            ('ttype', '=', 'char')
        ], required=True
    )
    identifier_field = fields.Many2One(
        'ir.model.field', 'Identifier Field',
        depends=['model'],
        domain=[
            ('model', '=', Eval('model')),
            ('ttype', '=', 'char')
        ], required=True
    )

    @staticmethod
    def default_active():
        """
        By Default the Menu is active
        """
        return True

    @classmethod
    def __setup__(cls):
        super(Menu, cls).__setup__()
        cls._sql_constraints += [
            ('unique_identifier', 'UNIQUE(unique_identifier, website)',
                'The Unique Identifier of the Menu must be unique.'),
        ]

    def _menu_item_to_dict(self, menu_item):
        """
        :param menu_item: Active record of the menu item
        """
        if hasattr(menu_item, 'reference') and getattr(menu_item, 'reference'):
            model, id = getattr(menu_item, 'reference').split(',')
            if int(id):
                reference, = Pool().get(model)(int(id))
                uri = url_for(
                    '%s.render' % reference.__name__, uri=reference.uri
                )
            else:
                uri = getattr(menu_item, self.uri_field.name)
        else:
            uri = getattr(menu_item, self.uri_field.name)
        return {
            'name': getattr(menu_item, self.title_field.name),
            'uri': uri,
        }

    def _generate_menu_tree(self, menu_item):
        """
        :param menu_item: Active record of the root menu_item
        """
        result = {'children': []}
        result.update(self._menu_item_to_dict(menu_item))

        # If children exist iteratively call _generate_..
        children = getattr(menu_item, self.children_field.name)
        if children:
            for child in children:
                result['children'].append(
                    self._generate_menu_tree(child))
        return result

    @classmethod
    @context_processor('menu_for')
    def menu_for(cls, identifier, ident_field_value, objectified=False):
        """
        Returns a dictionary of menu tree

        :param identifier: The unique identifier from which the menu
                has to be chosen
        :param ident_field_value: The value of the field that has to be
                looked up on model with search on ident_field
        :param objectified: The value returned is the active record of
                the menu identified rather than a tree.
        """
        # First pick up the menu through identifier
        try:
            menu, = cls.search([
                ('unique_identifier', '=', identifier),
                ('website', '=', request.nereid_website.id),
            ])

        except ValueError:
            current_app.logger.error(
                "Menu %s could not be identified" % identifier)
            abort(404)

        # Get the data from the model
        MenuItem = Pool().get(menu.model.model)
        try:
            root_menu_item, = MenuItem.search(
                [(menu.identifier_field.name, '=', ident_field_value)],
                limit=1)
        except ValueError:
            current_app.logger.error(
                "Menu %s could not be identified" % ident_field_value)
            abort(500)

        if objectified:
            return root_menu_item

        cache_key = key_from_list([
            Transaction().cursor.dbname,
            Transaction().user,
            Transaction().language,
            identifier, ident_field_value,
            'nereid.cms.menu.menu_for',
        ])
        rv = cache.get(cache_key)
        if rv is None:
            rv = menu._generate_menu_tree(root_menu_item)
            cache.set(cache_key, rv, 60 * 60)
        return rv

    @fields.depends('name', 'unique_identifier')
    def on_change_name(self):
        res = {}
        if self.name and not self.unique_identifier:
            res['unique_identifier'] = slugify(self.name)
        return res


class MenuItem(ModelSQL, ModelView):
    "Nereid CMS Menuitem"
    __name__ = 'nereid.cms.menuitem'
    _rec_name = 'unique_name'

    title = fields.Char(
        'Title', required=True, select=True, translate=True
    )
    unique_name = fields.Char('Unique Name', required=True, select=True)
    link = fields.Char('Link')
    use_url_builder = fields.Boolean('Use URL Builder')
    url_for_build = fields.Many2One(
        'nereid.url_rule', 'Rule',
        depends=['use_url_builder'],
        states={
            'required': Equal(Bool(Eval('use_url_builder')), True),
            'invisible': Not(Equal(Bool(Eval('use_url_builder')), True)),
        }
    )
    values_to_build = fields.Char(
        'Values', depends=['use_url_builder'],
        states={
            'required': Equal(Bool(Eval('use_url_builder')), True),
            'invisible': Not(Equal(Bool(Eval('use_url_builder')), True)),
        }
    )
    full_url = fields.Function(fields.Char('Full URL'), 'get_full_url')
    parent = fields.Many2One('nereid.cms.menuitem', 'Parent Menuitem',)
    child = fields.One2Many(
        'nereid.cms.menuitem', 'parent', string='Child Menu Items'
    )
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence', required=True, select=True)

    reference = fields.Reference('Reference', selection='links_get')

    def get_full_url(self, name):
        # TODO
        return ''

    @staticmethod
    def links_get():
        CMSLink = Pool().get('nereid.cms.link')
        links = [(x.model, x.name) for x in CMSLink.search([])]
        links.append([None, ''])
        return links

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_values_to_build():
        return '{ }'

    @classmethod
    def __setup__(cls):
        super(MenuItem, cls).__setup__()
        cls._error_messages.update({
            'wrong_recursion':
            'Error ! You can not create recursive menuitems.',
        })
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def validate(cls, menus):
        super(MenuItem, cls).validate(menus)
        cls.check_recursion(menus)

    @fields.depends('name', 'unique_name')
    def on_change_title(self):
        res = {}
        if self.title and not self.unique_name:
            res['unique_name'] = slugify(self.title)
        return res

    def get_rec_name(self, name):
        def _name(menuitem):
            if menuitem.parent:
                return _name(menuitem.parent) + ' / ' + menuitem.title
            else:
                return menuitem.title
        return _name(self)


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
    reference = fields.Reference('Reference', selection='links_get')

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

    @staticmethod
    def links_get():
        CMSLink = Pool().get('nereid.cms.link')
        return [('', '')] + [(x.model, x.name) for x in CMSLink.search([])]

    @staticmethod
    def default_type():
        return 'image'

    @staticmethod
    def default_state():
        if 'published' in Transaction().context:
            return 'published'
        return 'draft'


class ArticleCategory(ModelSQL, ModelView):
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
            Article, [('category', '=', category.id)], page,
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
            ('category', '=', self.id)
        ])
        return map(int, articles)


class Article(Workflow, ModelSQL, ModelView):
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
    reference = fields.Reference('Reference', selection='links_get')
    description = fields.Text('Short Description')
    attributes = fields.One2Many(
        'nereid.cms.article.attribute', 'article', 'Attributes'
    )
    category = fields.Many2Many(
        'nereid.cms.category-article', 'article', 'category', 'Category',
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

    @staticmethod
    def links_get():
        CMSLink = Pool().get('nereid.cms.link')
        return [('', '')] + [(x.model, x.name) for x in CMSLink.search([])]

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
