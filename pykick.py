import sys
from lib.pykick import Pykick
from lib import update
from lib import arguments


def main():
	args = arguments.Args()	
	args = vars(args.get_args())
	kick_updater = update.Update(host=args['host'], db=args['db'], uri=args['uri'], port=args['port'])
	
	funcs = {
	'get_all' : kick_updater.get_all_projects,
	'get_newest' : kick_updater.get_newest_projects,
	'update_records' : kick_updater.update_live_projects,
	'update_creator' : kick_updater.update_creator_data
 	}
 	funcs[args['func']]()
	pass 


if __name__ == '__main__':
    sys.exit(main())