# -*- coding: utf-8 -*-

import logging
from pykick import Pykick
import pymongo
import time
import datetime
import os
import sys

kick = Pykick(loglevel=logging.INFO)

class Update(object):
    '''
     A module to use the Pykick class together with a mongodb database.

     Call the class with a valid mongodb host and specify the database and projects.

     Parameters:
        - host: host ip, default is 'localhost'
        - port: mongodb server port, default is 27015
        - database: db to use, default is 'kickstarter'
        - collection: collection to use, default is 'projects'

    '''

    def __init__(self, host = 'localhost', port = 27017, uri = None, db = 'kickstarter', collection = 'projects', loglevel = logging.INFO, logfile='./logs/pykick.log'):


        self.logger = logging.getLogger("pykick.update")
        self.logger.setLevel(logging.INFO)

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
        
        self.logger.addHandler(ch)
        self.logger.addHandler(fh)

        # Set up the connection to the mongodb collection
        connection = self.__mongodb_connect(host=host, port=port, uri = uri)
        db = connection[db]
        self.collection = db[collection]

    def __to_datetime(self, obj):
        # if the obj was already datetime, do nothing
        if type(obj) == datetime.datetime:
            return obj
        # otherwise convert to datetime
        else:
            return datetime.datetime.fromtimestamp(obj)


    def __mongodb_connect(self, host, port, uri):
        if uri:
            try:
                return pymongo.MongoClient(uri)
            except (pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError) as e:
                print "Failed to connect to server {}".format(host, port, e)
        else:
            try:
                return pymongo.MongoClient(host=host, port=port)
            except (pymongo.errors.ConnectionFailure, pymongo.errors.ServerSelectionTimeoutError) as e:
                print "Failed to connect to server {}".format(host, port, e)
                
    def __convert_project_dates(self, project):
        '''
            convert all the timestamps to datetime objects, that can be handled by mongodb
        '''

        project['created_at'] = self.__to_datetime(project['created_at'])
        project['launched_at'] = self.__to_datetime(project['launched_at'])
        project['deadline'] = self.__to_datetime(project['deadline'])
        project['state_changed_at'] = self.__to_datetime(project['state_changed_at'])

        return project

    def __fix_floats(self, project, keys = ['goal', 'static_usd_rate', 'pledged', 'usd_pledged']):
        '''
            Convert fields that should be floats to floats.
        '''
        for key in keys:
            project[key] = float(project[key])
        return project

    def get_all_projects(self):
        '''
        Scans through all category ids and inserts
        the projects found into the mongodb database

        '''

        # Scan through the category ids that are known from our records ('categories.txt')
        with open('./lib/categories.txt', 'r') as f:
            cats =  f.readlines()
        cat_ids = [int(cat.split(',')[0]) for cat in cats]

        # Get projects for every category id available
        sorts = ['newest', 'end_date']

        # additionally split up by most prominent countries to get more projects
        woe_ids = [2347563, 2459115, 24865675, 24865671, 24865673, 23424977]
        for woe_id in woe_ids:
            for category_id in cat_ids[::-1]:
                for state in ['live','successful','failed']:
                    for sort in sorts:
                        options = {
                        'format' : 'json',
                        'category_id' : str(category_id),
                        'sort' : sorts,
                        'woe_id'
                        'state' : state
                        }

                    # Logging which id we are scanning
                        self.logger.info("scanning category ID: %s"  % (category_id))

                        for project in kick.get(options=options):
                            if project:
                                self.insert_to_database(project)


  
    def get_newest_projects(self):
        '''
        Inserts / updates the 4000 newest 'live' projects in the mongodb collection
        '''

        for project in kick.get_newest(options={'state' : 'live'}):
            if project:
                self.insert_to_database(project)


    def update_live_projects(self):
        '''
        Update all live projects presently in the database
        '''

        # find all projects in the database, that have an url field (they should all have)
        live_projects = [c for c in self.collection.find({'state' : 'live'}, {'urls' : 1})]

        total = len(live_projects)
        self.logger.info('Found %s live projects' % total)


        for i, project in enumerate(live_projects):
            self.logger.info("scanning project %s of: %s"  %(i+1, total))

            url = project['urls']['web']['project']

            project = kick.get_project(url)
            if project:
                self.insert_to_database(project)
            else:
                self.logger.critical('received empty project! url: %s' % url)
  
    def update_creator_data(self):
        '''
            Go through all projects in the database and
            scrape information about the creators if available.
        '''
        for project in self.collection.find({'creator.Backed': {'$exists' : False}}):
            self.logger.info('Updating creator info for project: %s', project['slug'])
            url = project['creator']['urls']['web']['user']
            data = kick.get_creator_data(url)
            if data:
                data = {'creator.'+key : value for key,value in data.items()}
                self.collection.update({'_id' : project['_id']},
                           {'$set' : data})
            else:
                self.logger.info('Failed to get creator info for project: %s', project['slug'])


    def insert_to_database(self, project):
        '''
            Insert / update a project in the database
        '''

        # Change the id field to _id for mongodb
        id_ = project['id']

        # Time when we updated this project (now)
        project['updated'] = datetime.datetime.utcnow()

        # convert all project dates to datetime objects
        project = self.__convert_project_dates(project)

        # fix the floats in the project
        project = self.__fix_floats(project)


        # Get the record form the collection, if it already exist
        in_db = self.collection.find({'id' : id_})

        # count is zero if the project is new
        if in_db.count() == 0:
            self.collection.insert(project)
            self.logger.info('New project found: %s' % project['slug'])
            old_state = project['state']
        # otherwise, let's get the old state
        else:
            old_state = in_db.next()['state']


        # if the state of the project changed from live to something else, set it to 1
        project['state_changed']  = 1 if (old_state!=project['state'] and old_state == 'live') else 0

        if old_state=='live':
            # if the state is still alive, append the newest status to the status array in the record.

            # Make a record of the current status, this will be *appended* to the record in the db
            # and used to track the amount $ pledged over time
            status = {'goal' : project['goal'],
                    'time' : project['updated'],
                    'pledged' : project['pledged'],
                    'usd_pledged' : project['usd_pledged'],
                    'backers_count' : project['backers_count'],
                    'state' : project['state']}

            #  update the project / will insert it if not in the db yet
            self.collection.update({'id' : id_},
                              { '$push': { 'status': status}})

            # set the new projects data. This has to happen in two separate steps, old mongodb versions don't like it otherwise
            self.collection.update({'id' : id_},
                               {'$set' : project})
            self.logger.info('Updated live project: %s' % project['slug'])

        else:
            # if it is an old project, don't push a new status update. This shouldn't happen usually.
            self.collection.update({'id' : id_},
                                  {'$set' : project})
            self.logger.info('Updated finished project: %s' % project['slug'])



