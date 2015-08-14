# -*- coding: utf-8 -*-
'''

    Nereid User
    user.py


'''
from trytond.pool import Pool, PoolMeta

from nereid import route, request, abort
from werkzeug.contrib.atom import AtomFeed

__all__ = ['NereidUser']
__metaclass__ = PoolMeta


class NereidUser:
    __name__ = 'nereid.user'

    def serialize(self, purpose=None):
        """
        Downstream implementation of serialize() which adds serialization for
        atom feeds.
        """
        if purpose == 'atom':
            return {
                'name': self.display_name,
                'email': self.email or None,
            }
        elif hasattr(super(NereidUser, self), 'serialize'):
            return super(NereidUser, self).serialize(purpose=purpose)

    @classmethod
    @route('/article-author/<int:id>.atom')
    def atom_feed(cls, id):
        """
        Returns the atom feed for all articles published under a certain author
        """
        Article = Pool().get('nereid.cms.article')

        try:
            articles = Article.search([
                ('author', '=', id),
                ('state', '=', 'published'),
            ])
        except:
            abort(404)

        feed = AtomFeed(
            "Articles by Author %s" % cls(id).display_name,
            feed_url=request.url, url=request.host_url
        )
        for article in articles:
            feed.add(**article.serialize(purpose='atom'))

        return feed.get_response()
