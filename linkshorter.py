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
from bottle import route, redirect, template, get, post, request, HTTPError, error

import base36
import database
import shorturl

# for debiggung
bottle.app().catchall = 0

# load the config-file
config = ConfigParser.ConfigParser()
config.read('config.cfg')

###############################################################################
# init database ###############################################################
###############################################################################

db = DB(config.get("database", "mysql_host"),
        config.get("database", "mysql_user"),
        config.get("database", "mysql_password"),
        config.get("database", "mysql_database"))

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
        return template("index", helper=Helper)

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
    return template('add', helper=Helper)

@post('/add/')
def add_post():
    ''' this will get the get-variables and then call the addLinkToDb-method '''
    auth = request.forms.get('auth')
    link = request.forms.get('link')
    if len(link.strip()) == 0:
        return template('error', message="Please enter an URL!", helper=Helper)
    else:
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
        return template('error', message="uh, oh, it's a four-oh-four!", helper=Helper)

@error(403)
def error403(error):
    ''' handler for 403-errors '''
    if is_API_call():
        return {"status":"403", "message":"Forbidden"}
    else:
        return template('error', message="seems like you are doing something you are not allowed to do?",
                        helper=Helper)

@error(500)
def error500(error):
    ''' handler for 500-errors '''
    if is_API_call():
        return {"status":"500", "message":"Internal Server Error"}
    else:
        return template('error', message="something went terrible wrong!", helper=Helper)

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

    if not Helper.auth_enabled() or (auth in config.get("general", "auth_hashes").rsplit(',')):
        surl = ShortURL.get_or_create_from_URL(link)
        if surl:
            if is_API_call():
                return {"status":"200", "message":"Success", "shortUrl":surl.get_surl()}
            else:
                return template("success", link=surl.get_surl(), helper=Helper)
        else:
            raise HTTPError(code=500)
    else:
        raise HTTPError(code=403)

def is_API_call():
    ''' just a little helper which checks if it's an api call or not '''
    if bottle.request.fullpath.startswith("/api/"):
        return True
    else:
        return False

#################################################################################
# View helper ###################################################################
#################################################################################

class Helper(object):
    ''' a collection of view helpers '''

    @staticmethod
    def auth_enabled():
        ''' helper to check if auth is enabled '''
        if config.has_option("general", "auth_hashes") and \
           config.get("general", "auth_hashes"):
            return True
        else:
            return False

    @staticmethod
    def piwik_enabled():
        ''' helper to check if Piwik is enabled '''

        if config.has_section("piwik") and config.has_option("piwik", "domain") \
           and config.has_option("piwik", "site_id") and config.get("piwik", "domain") \
           and config.get("piwik", "site_id"):
            return True
        else:
            return False

    @staticmethod
    def get_piwik_args():
        ''' helper to return the arguments for the _piwik.html template '''

        if Helper.piwik_enabled():
            return {"domain": config.get("piwik", "domain"),
                    "site_id": config.get("piwik", "site_id")}
        else:
            return {"domain": None, "site_id": None}

# WSGI
application = bottle.default_app()
