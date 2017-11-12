A simple module to scan the [kickstarter](http://www.kickstarter.com) API for projects
and insert them into a mongodb database. Requires connection to a mongodb server.

**pykick.py** handles contacting the API, the pagination of the response
and extracting data from individual projects pages.

**update.py** handles updating a MongoDB database with the projects found.
Requires pymongo as a driver for MongoDB.

## Usage

```python
from pykick.pykick import Pykick
from pykick import update
import pymongo

kick = update.Update(host='localhost', database='kickstarter', collection='projects')

kick.get_all_projects()
```

This will update / create a database with all projects that can be reached.
Each individual response to a query is limited to 4000 projects, so the module will scan through all
known category ids to retrieve as many past projects as possible.

Alternatively run `/bin/pykick` directly with one of the following options:  

```
get_all - try to get all projects from kickstarter, takes several hours!
get_newest - get the newest live projects.
update_records - will update  all live projects in the local db.
update_creator - will update information about the project creators.
```

Optionally: specify the mongodb server with the following arguments.

```
-host, --host - Mongodb server ip (default: localhost)
-p, --port -  Mongodb server port (default: 27017)
-db, --db - daatabase to use (default: kickstarter)
-uri, --uri - Mongodb server uri
```

E.g., the following command would update all records in the database 'kickstarter' on the mongodb server running on localhost under port 27018:

```
/bin/pykick -p 27018 --db kickstarter update_records
```
