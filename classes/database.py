"""
Copyright (C) 2011 Dennis Schubert <software@dsx.cc>
This file is licensed under the GNU General Public License.
See the LICENSE-file.
"""

class DB(object):
    ''' a smalll database abstraction to eliminate lost connections '''

    conn = None
    ''' the MySQLdb connection instance '''

    cur = None
    ''' the MySQLdb cursor instance '''

    retries = int(config.get("database", "mysql_connection_retries"))
    ''' number of retries for a failed operation '''

    def __init__(self, host, user, password, database):
        ''' initialize the object '''
        self.host = host
        self.user = user
        self.password = password
        self.database = database

        self._init_connection()

    def _init_connection(self):
        ''' initializes the connection '''

        if self.retries < 1:
            raise DBConnectionFailed()
        try:
            self.conn = MySQLdb.connect(host=self.host, user=self.user,
                                        passwd=self.password, db=self.database,
                                        connect_timeout=int(config.get("database", "mysql_connection_timeout")))
            self.cur = self.conn.cursor()
            self.retries = int(config.get("database", "mysql_connection_retries"))
        except:
            self.retries -= 1
            print("WARNING: MySQL connection died, trying to reinit...")
            self._init_connection()

    def escape(self, obj):
        ''' autodetect input and escape it for use in a SQL statement '''

        try:
            if isinstance(obj, str):
                return self.conn.escape_string(obj)
            else:
                return obj
        except MySQLdb.OperationalError:
            print("WARNING: MySQL connection died, trying to reinit...")
            self._init_connection()
            return self.escape(obj)

    def execute(self, sql):
        ''' execute the SQL statement and return the cursor '''

        try:
            self.cur.execute(sql)
            return self.cur
        except MySQLdb.OperationalError:
            print("WARNING: MySQL connection died, trying to reinit...")
            self._init_connection()
            return self.execute(sql)

    def fetch_one(self, sql):
        ''' execute the SQL statement and return one row if there's a result, return None if there's no result '''

        cur = self.execute(sql)
        if cur.rowcount:
            return cur.fetchone()
        else:
            return None

#TODO: probably make this a HTTPError
class DBConnectionFailed(Exception):
    ''' happens when a database operation continually fails '''

