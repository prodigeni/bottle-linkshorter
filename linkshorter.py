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

MYSQL_HOST = "localhost"
MYSQL_USER = "internal"
MYSQL_PASSWORD = "HXHXLsafLCxAyefT"
MYSQL_DATABASE = "internal_linkshorter"

ROOT_URL = "http://dsx.cc/"

AUTH_HASHES = ['your sha1 hashes of the passwords'] 

# import os and sys to change the working-dir and add the app-folder to sys
# path, so we can use local libs...
import os
import sys

path = os.path.dirname(__file__)
os.chdir(path)
if path not in sys.path:
    sys.path.append(path)

import MySQLdb
import hashlib
import bottle
from base36 import *
from bottle import route, redirect, template, get, post, request

# for debiggung
bottle.app().catchall = 0

mysqlConn = MySQLdb.connect(host=MYSQL_HOST, user=MYSQL_USER, passwd=MYSQL_PASSWORD, db=MYSQL_DATABASE)
mysqlCur = mysqlConn.cursor()

@route('/')
def index():
    redirect("http://w.dsx.cc/")
    
@route('/:lid#[a-z0-9]+#')
def gotoLink(lid):
    mysqlCur.execute("SELECT target FROM links WHERE ID=%i LIMIT 1;" % base36decode(lid))
    if mysqlCur.rowcount:
        url = mysqlCur.fetchone()
        redirect(url[0])
    else:
        return "404"

@get('/add/')
def addForm():
    return template('add_template')

@post('/add/')
def addPost():
    auth = request.forms.get('auth')
    link = request.forms.get('link')
    
    h = hashlib.new('sha1')
    h.update(auth)
    auth = h.hexdigest()
    
    if auth in authHashes:
        mysqlCur.execute("SELECT count(*) FROM links WHERE target='%s';" % link)
        count = mysqlCur.fetchone()
        count = count[0]
        if not count:
            mysqlCur.execute("INSERT INTO links (target) VALUES ('%s');" % link)
        mysqlCur.execute("SELECT ID FROM links WHERE target='%s';" % link)
        if mysqlCur.rowcount:
            base32url = mysqlCur.fetchone()
            base32url = base36encode(base32url[0])
            return ROOT_URL + base32url
        else:
            return "oops!"
    else:
        return "403"

@route('/add/:key#[a-z0-9]+#/:url#.*#')
def add(key, url):
    return url

application = bottle.default_app()