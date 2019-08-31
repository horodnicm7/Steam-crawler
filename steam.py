"""
    To install:
        pip install beautifulsoup4
        pip install pyyaml
"""

import re
import urllib.request
import yaml

from urllib import robotparser
from urllib.error import URLError, HTTPError, ContentTooShortError
from time import sleep
from bs4 import BeautifulSoup

import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='bs4')


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Bot(object, metaclass=Singleton):
    def __init__(self, url, timeout=1):
        self.set_url(url)
        self.__timeout = timeout

    def set_url(self, url):
        """
        :param url: url to scrap
        :return: None
        """
        self.__url = url
        self.__soup = BeautifulSoup(self.__url, 'html.parser')

    """
        Tries to get a valid user agent in maximum 10 attempts.
        Returns 'default-agent' if no valid agent is found.
    """
    def get_valid_user_agent(self):
        # init the robots.txt parser
        parser = robotparser.RobotFileParser()
        parser.set_url(self.__url + '/robots.txt')
        parser.read()

        # trying to get a valid agent name in less than 10 attempts
        user_agent = 'Scrappy'
        no_hops = 0
        while not parser.can_fetch(user_agent, self.__url):
            if user_agent[-1].isdigit():
                user_agent = user_agent[:-1] + str(int(user_agent[-1]) + 1)
            else:
                user_agent = user_agent + '1'

            no_hops += 1
            # error in finding a valid name
            if no_hops > 9:
                return 'default-agent'

        return user_agent

    """
        Downloads the webpage located at url. Tries 10 times to download if the
        page exists (the error code is not in [500, 600) )
    """
    def download_page(self, url, user_agent, debug=False):
        """
        :param url: url to download
        :param user_agent: user agent name
        :param debug: flag to print debug messages or not
        :return:
        """
        if debug:
            print('[DEBUG] Downloading: [' + url + '] ... ')
        page = None
        req = urllib.request.Request(url)
        req.add_header('User-agent', user_agent)

        for i in range(10):
            try:
                response = urllib.request.urlopen(req)
                page = response.read().decode('utf-8')
                break
            except (URLError, HTTPError, ContentTooShortError) as e:
                if hasattr(e, 'code'):
                    if not (e.code >= 500 and e.code < 600):
                        return None
                sleep(self.__timeout)
        return page

    """
        Returns text based on criteria.
    """
    def get_info(self, regex, tag, cls):
        """
        :param regex: regex used to parse data
        :param tag: tag to use (e.g: div, p, etc.)
        :param cls: tag unique identifier
        :return:
        """
        content = self.__soup.find(tag, cls)

        if not content:
            return None

        text = re.search(regex, str(content), re.M | re.I)
        return text.group

    """
        Method that computes the discount based on the old and the new price
    """
    @staticmethod
    def get_discount(old_price, new_price):
        return round(100 - (100 * new_price) / old_price, 2)


def scrap_deals(debug=False, timeout=0.75, retry_timeout=0.75, max_page_number=100):
    url = 'https://store.steampowered.com/'
    bot = Bot(url, timeout=retry_timeout)
    agent = bot.get_valid_user_agent()

    base_page = 'https://store.steampowered.com/search/?specials=1&page='
    page_no = 1
    while True:
        if page_no > max_page_number:
            break

        equal_pos = base_page.rfind('=')
        base_page = base_page[:equal_pos + 1] + str(page_no)

        page = bot.download_page(base_page, agent, debug=True)

        soup = BeautifulSoup(page, 'html.parser')
        data = str(soup.find('div', id='search_resultsRows'))

        soup = BeautifulSoup(data, features='html.parser')
        found = False

        for product in soup.find_all('a'):
            found = True
            product = str(product)

            try:
                raw_discount = str(BeautifulSoup(product, 'html.parser').find('div', class_='col search_price discounted responsive_secondrow'))

                raw_new_price = str(raw_discount.split('<br/>')[1]).replace('-', '0')
                matches = re.search(r'[*]*[0-9,.]*€', raw_new_price, re.M | re.I)
                new_price = float(matches.group(0)[:-1].replace(',', '.').replace('-', '0'))

                raw_old_price = BeautifulSoup(raw_discount, 'html.parser').find('strike').text.replace('-', '0')
                matches = re.search(r'[*]*[0-9,.]*€', raw_old_price, re.M | re.I)
                old_price = float(matches.group(0)[:-1].replace(',', '.'))

                name = BeautifulSoup(product, 'html.parser').find('span', class_='title').text

                print('{}\nold_price: {}\t new_price: {}\t discount: {}%\n'.format(name,
                                                                                   old_price,
                                                                                   new_price,
                                                                                   Bot.get_discount(old_price, new_price)))
            except (AttributeError, IndexError):
                if debug:
                    print('[DEBUG] Couldn\'t get info about this product\n')

        if not found:
            break
        page_no += 1
        sleep(timeout)  # to avoid a nice beautiful ban from valve
    pass


def main():
    config = None
    try:
        with open(__file__[:-3] + '_config.yaml', 'r') as stream:
            try:
                config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print('[DEBUG] Error parsing config file')
    except FileNotFoundError:
        print('[DEBUG] Config file not found')

    timeout = 0.75
    retry_timeout = 0.75
    max_page_number = 100
    if config:
        try:
            timeout = config['timeout']
            retry_timeout = config['retry-timeout']
            max_page_number = config['max-page-number']
        except KeyError:
            print('[DEBUG] Key not found in config')

    scrap_deals(debug=True, timeout=timeout, retry_timeout=retry_timeout, max_page_number=max_page_number)


main()
