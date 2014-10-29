# -*- coding: utf-8 -*-
'''

    nereid_cms

    :copyright: (c) 2010-2014 by Openlabs Technologies & Consulting (P) Ltd.
    :license: GPLv3, see LICENSE for more details

'''

from trytond.pool import Pool
from .cms import (
    MenuItem, BannerCategory, Banner, ArticleCategory,
    Article, ArticleAttribute, Website, NereidStaticFile,
    ArticleCategoryRelation,
)


def register():
    """
    Register classes
    """
    Pool.register(
        MenuItem,
        BannerCategory,
        Banner,
        ArticleCategory,
        Article,
        ArticleAttribute,
        NereidStaticFile,
        Website,
        ArticleCategoryRelation,
        module='nereid_cms', type_='model'
    )
