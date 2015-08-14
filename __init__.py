# -*- coding: utf-8 -*-
'''

    nereid_cms


'''

from trytond.pool import Pool
from .cms import (
    MenuItem, BannerCategory, Banner, ArticleCategory,
    Article, ArticleAttribute, Website, NereidStaticFile,
    ArticleCategoryRelation,
)
from user import NereidUser


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
        NereidUser,
        module='nereid_cms', type_='model'
    )
