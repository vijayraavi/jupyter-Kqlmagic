# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

import os
from datetime import datetime, timedelta


from .display import Display
from .constants import Constants, CryptoParam, SsoStorageParam, SsoEnvVarParam
from .log import logger


class DictDbStorage(object):

    last_clear_time = datetime.utcnow()

    def __init__(self, db, options: dict, state=None):
        self.authority = options.get(SsoStorageParam.AUTHORITY)
        self.db = db or {}
        self.gc_ttl_in_secs = options.get(SsoStorageParam.GC_TTL_IN_SECS, 0) 
        self._crypto_obj = options.get(SsoStorageParam.CRYPTO_OBJ)
        self.db_key = self._get_db_key(options.get(SsoStorageParam.CACHE_NAME, "sso"), self._crypto_obj.suffix, self.authority)

        self.db_key_conflict = False
        
        self.restore() #to throw warnings\errors 
        if state:
            self.save(state)


    def _get_db_key(self, cache_name: str, suffix: bytes, authority:str) -> str:
        
        sso_db_key_authority = authority[authority.find("://")+3:] if authority else ""
        if authority:
            path = os.path.join(Constants.SSO_DB_KEY_PREFIX, cache_name + str(suffix), sso_db_key_authority)
        else:
            path = os.path.join(Constants.SSO_DB_KEY_PREFIX, cache_name + str(suffix))
        return path


    def _db_gc(self):
        '''db garbage collector. remove old entries'''
        logger().debug(f"DictDbStorage(object)::_db_gc ")
        for db_key, db_value in self.db.items():
            logger().debug(f"DictDbStorage(object)::_db_gc db_key, db_value in self.db.items() {db_key}  , {db_value}  in self.db.items() ")

            if db_key.startswith(Constants.SSO_DB_KEY_PREFIX):
                state_encrypted = db_value
                if not state_encrypted:
                    continue
                time_created = state_encrypted.get("timestamp")
                logger().debug(f"DictDbStorage(object)::time_created {time_created}  timedelta(seconds=self.gc_ttl_in_secs) {timedelta(seconds=self.gc_ttl_in_secs)}")

                if (time_created + timedelta(seconds=self.gc_ttl_in_secs)) < datetime.utcnow():
                    del self.db[db_key]


    def clear_db(self):
        '''clear db. remove all entries'''
        for db_key in self.db.keys():
            logger().debug(f"DictDbStorage(object):: clear_db db_key,{db_key} ")
            logger().debug(f"DictDbStorage(object):: clear_db self db_key,{self.db_key} ")

            if db_key.startswith(self.db_key):
                logger().debug(f"DictDbStorage(object):: in startswith clear_db db_key,{db_key} ")
                del self.db[db_key]


    def save(self, state: str) -> None:
        '''save cache state in db'''
        logger().debug(f"DictDbStorage(object)::save(self, state: str) -> None state is {type(state)}")

        if not self.db_key_conflict:
            state_encrypted = self._crypto_obj.encrypt(state)  
            self.db[self.db_key] = {'data': state_encrypted, 'timestamp': datetime.utcnow()}


    def restore(self) -> str:
        '''restore cache state from db'''
        logger().debug(f"DictDbStorage(object)::restore(self) -> str")
        if self.gc_ttl_in_secs > 0 and (self.last_clear_time + timedelta(seconds=self.gc_ttl_in_secs)) < datetime.utcnow():
            self.last_clear_time = datetime.utcnow()
            self._db_gc()

        if self.db_key_conflict:
            return
        
        state_encrypted = self.db.get(self.db_key)
        if not state_encrypted:
            return

        try:
            value = self._crypto_obj.decrypt(state_encrypted.get("data"))
            return value

        except:
            try: 
                self.db_key_conflict = True

                self._crypto_obj.verify(state_encrypted) 
                Display.showWarningMessage("Warning: SSO disabled, due to cache_name conflict")

            except: #the token has bad form
                Display.showWarningMessage("Warning: SSO disabled, due to cache_name conflict (invalid data in db)")
                # del self.db[self.db_key]
