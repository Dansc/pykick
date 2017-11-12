import argparse

class Args:
    def __init__(self):
        self.parser = argparse.ArgumentParser( formatter_class=argparse.RawTextHelpFormatter)
        self.parser.add_argument('-db', '--db', type=str, 
                                help='The mongodb database collection.', 
                                default='kickstarter')
        self.parser.add_argument('-p', '--port', type=int, 
                                 help='The mongodb database port.', 
                                 default=27017)
        self.parser.add_argument('-uri', '--uri', type=str,
                                 default = '',
                                 help='Mongodb URI')
        self.parser.add_argument('-host', '--host', type=str, 
                                    default='localhost', 
                                    help='The mongodb database host.')
        self.parser.add_argument('-l', '--logfile', type=str, 
                                    help='The path to the log file.', 
                                    default='../logs/pykick.log')
        self.parser.add_argument('func', choices = ['get_all', 'get_newest', 'update_records', 'update_creator'], help='''get_all - try to get all projects from kickstarter, takes several hours!
get_newest - get the newest live projects.
update_records - will update  all live projects in the local database.
update_creator - will update information about the project creators.''')

    def get_args(self, args=None):
        return self.parser.parse_args(args)