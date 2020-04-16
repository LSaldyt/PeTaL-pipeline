from petal.pipeline.module_utils.module import Module
from ..libraries.natural_language.hitlist import HitList

from pprint import pprint
from collections import defaultdict
from bisect import bisect_left

import pickle, os

LEXICON_PATH = 'data/lexicon'
INDEX_PATH   = 'data/index'

class InvertedIndexCreator(Module):
    '''
    Create an inverted index from hitlists
    '''
    def __init__(self, in_label='HitList', out_label=None, connect_labels=None, name='InvertedIndexCreator'):
        Module.__init__(self, in_label, out_label, connect_labels, name, page_batches=True)

        self.index   = defaultdict(list)
        self.lexicon = set()

    def save(self):
        with open(INDEX_PATH, 'wb') as outfile:
            pickle.dump(self.index, outfile)
        with open(LEXICON_PATH, 'wb') as outfile:
            pickle.dump(self.lexicon, outfile)

    def load(self):
        if os.path.isfile(INDEX_PATH):
            with open(INDEX_PATH, 'rb') as infile:
                self.index = pickle.load(infile)
        if os.path.isfile(LEXICON_PATH):
            with open(LEXICON_PATH, 'rb') as infile:
                self.lexicon = pickle.load(infile)

    def process(self, previous):
        data = previous.data
        hitlist = HitList(data['source_uuid'])
        hitlist.load()
        for word in hitlist.words:
            self.lexicon.add(word)

            sections, counts = hitlist.word_hitlist(word)
            self.index[word].append(counts + (hitlist.uuid,))
        print('Creating inverted index..', flush=True)
        pprint(self.index)

    def process_batch(self, batch):
        print('INDEXER', flush=True)
        self.load()
        for item in batch.items:
            self.process(item)
        print('Ran indexer', flush=True)
        self.save()
