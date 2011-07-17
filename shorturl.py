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

        url = db.fetch_one("SELECT target FROM links WHERE ID=%i LIMIT 1;" % base36decode(lid))
        if url and url[0]:
            return ShortURL(url[0], lid)
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

