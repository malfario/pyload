#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.

    @author: RaNaN
"""

from threading import Lock
from random import choice

from module.common.json_layer import json
from module.utils import lock

class AccountManager:
    """manages all accounts"""

    def __init__(self, core):
        """Constructor"""

        self.core = core
        self.lock = Lock()

        self.loadAccounts()

    def loadAccounts(self):
        """loads all accounts available"""

        self.accounts = {}

        for plugin, loginname, activated, password, options in self.core.db.loadAccounts():
            # put into options as used in other context
            options = json.loads(options) if options else {}
            options["activated"] = activated

            self.createAccount(plugin, loginname, password, options)

        return

    def saveAccounts(self):
        """save all account information"""

        data = []
        for name, plugin in self.accounts.iteritems():
            data.extend([(name, acc.loginname, acc.activated, acc.password, json.dumps(acc.options)) for acc in
                                                                                                     plugin.itervalues()])
        self.core.db.saveAccounts(data)

    def createAccount(self, plugin, loginname, password, options):
        klass = self.core.pluginManager.loadClass("accounts", plugin)
        if not klass:
            self.core.log.warning(_("Unknown account plugin %s") % plugin)
            return

        if plugin not in self.accounts:
            self.accounts[plugin] = {}

        self.core.log.debug("Create account %s:%s" % (plugin, loginname))

        self.accounts[plugin][loginname] = klass(self, loginname, password, options)


    @lock
    def updateAccount(self, plugin, user, password=None, options={}):
        """add or update account"""
        if plugin in self.accounts and user in self.accounts[plugin]:
            acc = self.accounts[plugin][user]
            updated = acc.update(password, options)

            self.saveAccounts()
            if updated: acc.scheduleRefresh(force=True)
        else:
            self.createAccount(plugin, user, password, options)
            self.saveAccounts()

        self.sendChange()

    @lock
    def removeAccount(self, plugin, user):
        """remove account"""
        if plugin in self.accounts and user in self.accounts[plugin]:
            del self.accounts[plugin][user]
            self.core.db.removeAccount(plugin, user)
            self.sendChange()
        else:
            self.core.log.debug("Remove non existing account %s %s" % (plugin, user))


    @lock
    def getAccountForPlugin(self, plugin):
        if plugin in self.accounts:
            accs = [x for x in self.accounts[plugin].values() if x.isUsable()]
            if accs: return choice(accs)

        return None

    @lock
    def getAllAccounts(self, refresh=False):
        """ Return account info, refresh afterwards if needed

        :param refresh:
        :return:
        """
        if refresh:
            self.core.scheduler.addJob(0, self.core.accountManager.getAllAccounts)

        # load unavailable account info
        for p_dict in self.accounts.itervalues():
            for acc in p_dict.itervalues():
                acc.getAccountInfo()

        return self.accounts

    def refreshAllAccounts(self):
        """ Force a refresh of every account """
        for p in self.accounts.itervalues():
            for acc in p.itervalues():
                acc.getAccountInfo(True)


    def sendChange(self):
        self.core.eventManager.dispatchEvent("accountsUpdated")