# -*- coding: utf-8 -*-
'''

    nereid_cms

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''

from trytond.pool import Pool
from .cms import (
    CMSLink, Menu, MenuItem, BannerCategory, Banner, ArticleCategory,
    Article, ArticleAttribute, Website, NereidStaticFile,
)


def register():
    """
    Register classes
    """
    Pool.register(
        CMSLink,
        Menu,
        MenuItem,
        BannerCategory,
        Banner,
        ArticleCategory,
        Article,
        ArticleAttribute,
        NereidStaticFile,
        Website,
        module='nereid_cms', type_='model'
    )
