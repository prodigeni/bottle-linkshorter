"""
Little linkshorter I'm using at dsx.cc

Copyright (C) 2011  Dennis Schubert <software@dsx.cc>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# import os and sys to change the working-dir and add the app-folder to sys
# path, so we can use local libs...
import os
import sys

path = os.path.dirname(__file__)
os.chdir(path)
if path not in sys.path:
    sys.path.append(path)

import ConfigParser
import hashlib
import MySQLdb
import bottle
from base36 import *
from bottle import route, redirect, template, get, post, request, HTTPError, error

# for debiggung
bottle.app().catchall = 0

# load the config-file
config = ConfigParser.ConfigParser()
config.read('config.cfg')


################################################################################
# database abstraction #########################################################
################################################################################

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


###############################################################################
# init database ###############################################################
###############################################################################

db = DB(config.get("database", "mysql_host"),
        config.get("database", "mysql_user"),
        config.get("database", "mysql_password"),
        config.get("database", "mysql_database"))

###############################################################################
# models ######################################################################
###############################################################################


class ShortURL(object):
    ''' a small model for shortend URLs '''
    
    lid = None
    ''' the lid for an URL '''

    url = None
    ''' the URL for a lid '''

    def __init__(self, url, lid=None):
        ''' if lid isn't given creates a new entry '''
        
        if lid != None:
            self.lid = lid
            self.url = url
        else:
            self = ShortURL.get_or_create_from_url(url)
    
    @staticmethod
    def from_lid(lid):
        ''' if there's an URL for lid returns a ShortURL instance for it, else None '''
        
        url = db.fetch_one("SELECT target FROM links WHERE ID=%i LIMIT 1;" % base36decode(lid))[0]
        if url:
            return ShortURL(url, lid)
        else:
            return None
    
    @staticmethod
    def from_URL(url):
        ''' if url is in the database returns a ShortURL instance for it, else None '''
        
        id = db.fetch_one("SELECT ID FROM links WHERE target='%s';" % db.escape(url))
        if id and id[0]:
            return ShortURL(url, base36encode(id[0]))
        else:
            return None
    
    @staticmethod
    def get_or_create_from_URL(url):
        ''' if url is already in the database returns a ShortURL instance for it, else creates it and does the same '''
        
        surl = ShortURL.from_URL(url)
        if surl:
            return surl
        else:
            db.execute("INSERT INTO links (target) VALUES ('%s');" % db.escape(url))
            return ShortURL.from_URL(url)
    
    def get_surl(self):
        ''' get the full shortened URL '''
        
        return config.get("general", "link_root_url")+self.lid
    
    def get_url(self):
        ''' return the URL '''
        
        return self.url
    
    def get_lid(self):
        ''' return the lid '''
        
        return self.lid


###############################################################################
# website-stuff ###############################################################
###############################################################################

@route('/')
def index():
    ''' this will redirect to the redirect-target or output the index-page '''    
    if config.has_option("general", "index_redirect") and \
       config.get("general", "index_redirect"):
        redirect(config.get("general", "index_redirect"))
    else:
        return template("index")
    
@route('/:lid#[a-z0-9]+#')
def goto_link(lid):
    ''' get the target-url and redirect '''
    surl = ShortURL.from_lid(lid)
    if surl:
        redirect(surl.url)
    else:
        raise HTTPError(code=404)

@get('/add/')
def add_form():
    ''' this will just show the add-formular '''
    return template('add', auth_enabled=auth_enabled)

@post('/add/')
def add_post():
    ''' this will get the get-variables and then call the addLinkToDb-method '''
    auth = request.forms.get('auth')
    link = request.forms.get('link')
    return add_link_to_DB(link, auth)

###############################################################################
# api-stuff ###################################################################
###############################################################################

@route('/api/add/:url#.+#')
@route('/api/add/:auth#[a-z0-9]+#/:url#.+#')
def api_add(url, auth = ""):
    ''' addLinkToDb for the get-api. Note that we are replacing :/ with :// here,
        thats some kind of apache "bug" '''
    return add_link_to_DB(url.replace(':/', '://'), auth)

@route('/api/get/:url#.+#')
@route('/api/get/:lid#[a-z0-9]+#')
@route('/api/get/' + config.get("general", "link_root_url").replace('://', '\:/') + ':lid#[a-z0-9]+#')
def api_get(url = "", lid = ""):
    ''' this will get the link-id AND the target. it'll search for target
        and the link-id '''
    if url:
        url = url.replace(':/', '://')
        surl = ShortURL.from_URL(url)
        if surl:
            return {"status":"200", "message":"Success", "shortUrl":surl.get_surl(), "target":surl.get_url()}
        else:
            raise HTTPError(code=404)
    elif lid:
        surl = ShortURL.from_lid(lid)
        if surl:
            return {"status":"200", "message":"Success", "shortUrl":surl.get_surl(), "target":surl.get_url()}
        else:
            raise HTTPError(code=404)
    else:
        raise HTTPError(code=404)

###############################################################################
# error handlers ##############################################################
###############################################################################

@error(404)
def error404(error):
    ''' handler for 404-errors '''
    if is_API_call():
        return {"status":"404", "message":"Not Found"}
    else:
        return template('error', message="uh, oh, it's a four-oh-four!")

@error(403)
def error403(error):
    ''' handler for 403-errors '''
    if is_API_call():
        return {"status":"403", "message":"Forbidden"}
    else:
        return template('error', message="seems like you are doing something you are not allowed to do?")

@error(500)
def error500(error):
    ''' handler for 500-errors '''
    if is_API_call():
        return {"status":"500", "message":"Internal Server Error"}
    else:
        return template('error', message="something went terrible wrong!")

###############################################################################
# additional functions ########################################################
###############################################################################

def add_link_to_DB(link, auth = ""):
    ''' this will add the url to the database, but only if it's not in there
        if it's in there, just output the short link. '''

    # we only need a sha1-generator, if it's NOT an api-call, api-calls will already
    # have the hash in there
    if not is_API_call():
        h = hashlib.new('sha1')
        h.update(auth)
        auth = h.hexdigest()
    
    # Get sure there's a protocol
    if not ":/" in link:
        link = "http://"+link
    
    if not auth_enabled() or (auth in config.get("general", "auth_hashes").rsplit(',')):
        surl = ShortURL.get_or_create_from_URL(link)
        if surl:
            if is_API_call():
                return {"status":"200", "message":"Success", "shortUrl":surl.get_surl()}
            else:
                return template("success", link=surl.get_surl())
        else:
            return raise HTTPError(code=500)
    else:
        raise HTTPError(code=403)

def is_API_call():
    ''' just a little helper which checks if it's an api call or not '''
    if bottle.request.fullpath.startswith("/api/"):
        return True
    else:
        return False

def auth_enabled():
    ''' helper to check if auth is enabled '''
    if config.has_option("general", "auth_hashes") and \
       config.get("general", "auth_hashes"):
        return True
    else:
        return False

# WSGI
application = bottle.default_app()
