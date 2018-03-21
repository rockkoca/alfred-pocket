#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from whoosh.index import create_in, open_dir
from whoosh.fields import *
from whoosh.analysis import RegexAnalyzer
import os
import urllib2
import logging
import time
import re
import threading

logging.basicConfig(filename='fulltext.log', level=logging.INFO)


class FullText(object):
    indexdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'indexdir/')
    index_name = 'alfred-pocket'
    if not os.path.exists(indexdir):
        os.mkdir(indexdir)
    instance = None
    extract_text = re.compile(r'<.*?>(.*?)</.*?>', re.MULTILINE)
    extract_title = re.compile(r'<title[^>]*.*?>(.*?)</title>', re.I)
    remove_p_tag = re.compile(r'<(/*)(p|strong|b)>', re.I)
    remove_a_tag = re.compile(r'<a.*?>.*?</a>', re.I)
    remove_script_tag = re.compile(r'<script.*?>([^<>]*?)</script>', re.MULTILINE)
    remove_comments = re.compile(r'<!--.*?-->', re.MULTILINE)
    remove_all_tags = re.compile(r'<[^>]*>', re.I)
    remove_linebreak = re.compile(r'(\n)|(\r\n)', re.I)
    lock = threading.Lock()

    def __init__(self):

        analyzer = RegexAnalyzer(ur"([\u4e00-\u9fa5])|(\w+(\.?\w+)*)")
        schema = Schema(title=TEXT(stored=True, analyzer=analyzer), path=ID(stored=True),
                        content=TEXT(stored=True, analyzer=analyzer))
        try:
            self.ix = open_dir(self.indexdir, schema=schema, indexname=self.index_name)
        except Exception as e:
            print(e)
            self.ix = create_in(self.indexdir, schema=schema, indexname=self.index_name)
        self.searcher = self.ix.searcher()

    @staticmethod
    def get_instance():
        if FullText.instance is None:
            FullText.instance = FullText()
        return FullText.instance

    def add_document(self, title=u'', url=u'', content=u''):
        if not title and url:
            return
        with self.lock:
            writer = self.ix.writer()
            writer.add_document(title=title, path=url, content="%s, %s" % (title, content))
            writer.commit()

    def search(self, q, key='content'):
        assert key in {'content', 'url', 'title'}
        if key == 'url':
            key = 'path'
        results_list = []
        with self.ix.searcher() as searcher:
            results = searcher.find(key, q)
            for line in results:
                item = {
                    'title': line['title'],
                    'url': line['path'],
                    'content': line['content']
                }
                results_list.append(item)
            return results_list

    @staticmethod
    def has_link(url):
        url = unicode(url, "utf-8") if not isinstance(url, unicode) else url
        return FullText.get_instance().search(url, key='url')

    def add_page(self, url, title=None):
        logging.info(str(url))
        url = FullText.convert_to_unicode(url)
        if FullText.get_instance().search(url, key='url'):
            return
        title = FullText.convert_to_unicode(title)
        try:
            html = FullText.get_html(url)
            page = FullText.get_text_from_html(html)
            if 'err' in page:
                logging.info(str(page['err']))
            self.add_document(title or page['title'], url, page['body'])

            return True
        except urllib2.HTTPError, e:
            print e.fp.read()
            logging.info(e.fp.read())
        except Exception as e:
            logging.info(e)
            print(e)
        return False

    def del_page(self, url):
        with self.lock:
            writer = self.ix.writer()
            writer.delete_by_term('path', FullText.convert_to_unicode(url))
            writer.commit()

    @staticmethod
    def get_html(url):
        ua_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/60.0.3112.113 Safari/537.36",
            "Referer": 'https://www.google.com'
        }
        try:
            request = urllib2.Request(url, headers=ua_headers)
            html = urllib2.urlopen(request).read()
        except urllib2.HTTPError, e:
            print e.fp.read()
            logging.info(e.fp.read())
        except Exception as e:
            logging.info(e)
            print(e)
        else:
            return html

    @staticmethod
    def get_text_from_html(html):
        try:
            html = FullText.remove_linebreak.sub('', html)
            title = re.findall(FullText.extract_title, html)
            html = re.sub(FullText.remove_a_tag, '', html)
            # TODO removing scripts from some dynamic websites like quora.com will remove all useful text
            # TODO using headless browser requires too much resources
            # html = re.sub(FullText.remove_script_tag, '', html)
            html = re.sub(FullText.remove_comments, '', html)

            html = FullText.remove_all_tags.sub('', html)

            return {
                'title': FullText.convert_to_unicode(' '.join(title)),
                'body': FullText.convert_to_unicode(html)
            }
        except Exception as e:
            return {
                'title': u'',
                'body': u'',
                'err': str(e)
            }

    @staticmethod
    def convert_to_unicode(text):
        return unicode(text, "utf-8") if not isinstance(text, unicode) and text is not None else text


if __name__ == '__main__':
    url = u'https://www.zhihu.com/question/20186320'
    FullText.get_instance().del_page(url)
    FullText.get_instance().add_page(url)
    start = time.time()
    for article in FullText.get_instance().search(u'有自己的图片服务器'):
        print(article['content'])
    print(time.time() - start)