# -*- coding: utf-8 -*-

import logging
import logging.handlers
import requests
import json
import re
from bs4 import BeautifulSoup
import lxml   
import time
from datetime import datetime as dt
import os
import sys
print os.path.dirname(sys.executable)
# Suppress urrlib3 https warnings
import urllib3



DISCOVER_URL = 'https://www.kickstarter.com/discover/advanced'
CATEGORY_URL = 'https://www.kickstarter.com/discover'
PROJECT_REGEX = re.compile(r'window.current_project = \"(.+)\"')
TIMEOUT = 10.
REQUEST_LIMIT = 10

class Pykick(object):
    '''
     A simple module to access the kickstarter API and handle the pagination

        Functions:
            Pykick.get_newest will return an iterator to the 4000 newest individual projects.
            Pykick.get will return an iterator to 4000 projects
            Pykick.get_creator_data will scrape data directly from a user page on kickstarter.com. These urls are in
                                    the project json dicts.


    '''
    def __init__(self, loglevel = logging.INFO, logfile = './logs/pykick.log'):
        ''' Module to access kickstarter projects
        '''

        # create the logger instance and set loglevel
        self.logger = logging.getLogger("pykick.Pykick")
        self.logger.setLevel(loglevel)

        # check if the log folder exists, if not make it
        if not os.path.exists(os.path.dirname(logfile)):
            os.mkdir(os.path.dirname(logfile))


        # Lets make one log file per day and keep backups for a week
        fh = logging.handlers.TimedRotatingFileHandler(logfile, when='D', interval=1, backupCount=7)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        fh.setLevel(loglevel)
        ch = logging.StreamHandler()
        ch.setLevel(loglevel)
        ch.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        self.requests_counter = 0

  
    def __iter_pages(self, options):

        # Set the counters to zero
        counter = 0
        total_hits = 0
        running = True

        while running:

            # Try to get a response using requests from the discover url using options set above
            r = requests.get(DISCOVER_URL, params=options)

            if r.status_code==200:
                # Got a response, convert it to json!
                resp = r.json()

                # There is always a key total_hits, even if we exceeded the page limit, in that case projects is an empty array
                total_hits = resp['total_hits']
                # Increase the counter by the number of found projects
                counter += len(resp['projects'])

                # logging
                self.logger.info('total_hits: %s', total_hits)
                self.logger.info("Scanning page: %s"  % options['page'])
                self.logger.info("Project: %s out of %s" %(counter, total_hits))

                yield resp['projects']

            # stop the loop if there was an error, e.g. the url might be broken (in the future this should be
            # fixed the in the db)
            else:
                self.logger.critical("requests error, status code: %s" % r.status_code)
                running = False

            # stop the while loop if we reached the end (page 200) or found all projects, whatever is reached first
            if (counter == total_hits) or (options['page'] == 200):
                running = False

            # go to the next page
            options['page'] += 1

    def __iter_projects(self, options={}):

        # the default starting page is 1, this could also be changed by hand to start at a later page (maximum 200)
        options.setdefault('page', 1)
        options['format'] = 'json'

        # go through all the pages and emit individual projects
        for page in self.__iter_pages(options):
            for project in page:
                yield project


    def __handle_request(self, url):

        # try to contact the url
        try:
            r = requests.get(url, timeout = TIMEOUT)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self.logger.warning("No response, url: %s \n Error: %s" % (url, e))
            return None

        # if the status code is not 200, log the error
        if r.status_code!=200:
            self.logger.critical("No response, url: %s, status code: %s", url, r.status_code)
            return None

        else:
            return r


    def __extract_data(self, r):

        # Search for the project data in the response text and extract the json data if there is one
        project_text = PROJECT_REGEX.search(r.text).groups()
        if project_text:

            # fix some html chars for quotes, replace excess slashs
            project_text = project_text[0].replace('&quot;','"').replace('\\\\','\\')

            # if we can convert the response into a json, return it, otherwise raise an error and return None
            try:
                resp = json.loads(project_text)
                return resp
            except ValueError, e:
                self.logger.critical("Error in loading request into JSON")
                self.logger.critical(e)
                return None

        # if there was no project, return none
        else:
            self.logger.critical("No project text found on project page")
            return None

    def __extract_creator_data(self, r, url):

        # load the url text into beautifulsoup
        print url
       # print r.text
        i = 0
        try:
            soup = BeautifulSoup(r.text, 'html.parser')
            print 'no error'
            i = 1
        except:
            print 'error'

        if i == 1:
            try:
                # Try to find the nav lists and all 'a' elements within
                list_items = soup.findAll('li', {'class', 'nav--subnav__item'})
            except IndexError as e:
                # if we can't find project_nav, we raise an error
                self.logger.info('Couldnt get user page, user page deleted? %s', url)
                return None


            # create a dict for the listed data found in project_nav. This should be: backed, created and comments counts
            try:
                creator_data = {item.text.split()[0]:item.text.split()[1] for item in list_items if len(item.text.split())>1}
                self.logger.info('Updated creator data: %s', creator_data)
            except AttributeError as e:
                self.logger.warning('Failed to extract creator data: %s', list_items)
            return creator_data
        return None

    def get_newest(self,options={}):
        '''
            Returns an iterator for the newest projects at kickstarter
        '''
        options.setdefault('sort', 'newest')
        return self.get(options)


    def get(self, options = {}):
        '''
            Returns an iterator for projects that returns dicts of individual project records. By default
            the format is 'json'.
            Change this by calling the function with a dictionary with keys 'sort' and 'format' or any other
            option needed, e.g. 'category_id'.

            E.g.: options = {'sort' : 'most_funded', 'format' : 'json', 'category_id' : 3}
                    to find projects from the category 'comics' (3), sorted by funding and in json format.
        '''

        return self.__iter_projects(options)

    def get_categories(self):
        '''
            returns an updated dictionary with the main Kickstarter categories (not including subcategories)
            and the count of live projects in them.

            Scraped from the mainpage kickstarter.com
        '''
        categories = {}

        r = requests.get(CATEGORY_URL)
        if r.status_code==200:
            soup = BeautifulSoup(r.text)
        else:
            self.logger.critical("Couldn't get soupify category page %s" % CATEGORY_URL)
            self.logger.critical('requests status code: %s' % r.status_code)


        counts = soup.find_all('div', {'class' : 'h4 bold'})
        names = soup.find_all('div', {'class' : 'js-category-name category-name mobile-table full-height'})

        assert len(counts) == len(names)

        for name, count in zip(names, counts):
            c = count.contents[0].split(" ")[0].replace(",","")
            n = name.find('div', {'class' : 'h3'}).contents[0]
            categories.setdefault(n, c)

        return categories


    def get_project(self, project_url):

        '''
            Scrapes from an individual kickstarter project page what it can get.


            The project data is hidden in the response in json format. The function will search for this data, reformat and
            return it as a dictionary.

            Input: the project url. The format is https://www.kickstarter.com/projects/[project-id]/[project-name/slug?]
            Returns: a python dictionary with the project data
        '''

        # Let's try to get the project data
        r = self.__handle_request(project_url)
        if r:
            # If we got an answer, reset the requests counter and return the project
            self.requests_counter = 0
            project = self.__extract_data(r)
            return project

        else:
            # We got no response, if the request counter is still smaller than request limit, try again
            self.logger.critical('received empty project! url, trying again: %s' % project_url)
            if self.requests_counter < REQUEST_LIMIT:
                self.logger.critical("attempt %i out of %i" % (self.requests_counter, REQUEST_LIMIT))
                self.requests_counter += 1
                self.get_project(project_url)
            else:
                self.logger.critical("gave up to get project %s" % project_url)
                return None



    def get_creator_data(self, creator_url):
        '''
            Scans a kickstarter user page and returns the following data as a dictioniory:
            Returns information about a kickstarter:
                'Backed' : Number of projects backed by the user
                'Comments' : Number of comments on the personal page
                'Created' : Number of projects created by the user
        '''

        r = self.__handle_request(creator_url)

        return self.__extract_creator_data(r, creator_url)
