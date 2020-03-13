import glob
import os
import time
import pickle
import random
from uuid import uuid4
from pprint import pprint
from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup

from ..utils.module import Module

TOOLS_URL  = "http://airfoiltools.com"
SEARCH_URL = "http://airfoiltools.com/search/airfoils"

def scrape_airfoil_list():
    raw_html = get(SEARCH_URL).content
    html = BeautifulSoup(raw_html, 'html.parser')
    airfoilURLList = html.findAll("table", {"class": "listtable"})
    tableRows = airfoilURLList[0].findAll("tr")
    urls = []
    names = []
    for row in tableRows: # Search through all tables 
        airfoil_link = row.find(lambda tag: tag.name=="a" and tag.has_attr('href'))
        if (airfoil_link):
            urls.append(TOOLS_URL + airfoil_link['href'])
            names.append(airfoil_link.text.replace("\\", "_").replace("/","_"))
    return zip(urls, names)

def scrape_airfoil_coords(page, name):
    lednicerDAT = page.replace("details","lednicerdatfile")
    raw_html = get(lednicerDAT,True).content
    soup = BeautifulSoup(raw_html,'lxml')
    coord_file = 'data/airfoil_data/' + name + '_coords.pkl'
    lines = soup.text.split('\n')[3:]

    in_first = True
    first  = []
    second = []
    for line in lines:
        pair = tuple(map(float, line.split()))
        if line == '':
            in_first = False
            continue
        if in_first:
            first.append(pair)
        else:
            second.append(pair)

    with open(coord_file, 'wb') as outfile:
        pickle.dump((first, second), outfile)
    return coord_file

def parse_detail_lines(lines):
    details = dict()

    xtrf_cells = lines[0].split()
    details['xtrf_top']    = float(xtrf_cells[2])
    details['xtrf_bottom'] = float(xtrf_cells[4])

    regime_cells = lines[1].split()
    details['mach'] = float(regime_cells[2])

    column_names = lines[3].split()
    column_dicts = {k : [] for k in column_names}
    for line in lines[5:]:
        for key, cell in zip(column_names, line.split()):
            column_dicts[key].append(float(cell))
    details['data'] = column_dicts
    return details

def parse_details(details_page,name):
    raw_html=get(details_page).content
    html = BeautifulSoup(raw_html, 'html.parser')
    details_table = html.findAll("table", {"class": "details"})
    table_links = details_table[0].findAll("a")
    polar = table_links[2]['href']
    polar_html = get(TOOLS_URL + polar,True).content.decode('utf-8')
    lines = polar_html.split('\n')[7:]
    return parse_detail_lines(lines)

def parse_airfoil(url, name):    
    details = []
    html = BeautifulSoup(get(url).content, 'html.parser')
    polar_list = html.findAll("table", {"class": "polar"})
    for row in polar_list[0].findAll('tr'): # Search through all rows
        columns = row.findAll('td')
        if (columns) and (len(columns)>4):
            Re    = float(columns[2].text.replace(',',''))
            Ncrit = float(columns[3].text.replace(',',''))
            data_link = columns[7].find(lambda tag: tag.name=="a" and tag.has_attr('href'))
            details_page = TOOLS_URL + data_link['href']
            details_dict = parse_details(details_page, name)
            details_dict['Re']    = Re
            details_dict['Ncrit'] = Ncrit
            details.append(details_dict)
    return details

class Airfoils(Module):
    def __init__(self, in_label=None, out_label='Airfoil', connect_labels=None, name='Airfoils'):
        Module.__init__(self, in_label, out_label, connect_labels, name)

    def process(self):
        for url, name in scrape_airfoil_list():
            details    = parse_airfoil(url, name)
            coord_file = scrape_airfoil_coords(url, name)
            for detail_page in details:
                detail_file = 'data/airfoil_data/{}_{}_{}.pkl'.format(name, detail_page['Re'], detail_page['Ncrit'])
                with open(detail_file, 'wb') as outfile:
                    pickle.dump(detail_page.pop('data'), outfile)
                yield self.default_transaction({'name' : name, 'detail_file': detail_file, 'coord_file' : coord_file, **detail_page})
