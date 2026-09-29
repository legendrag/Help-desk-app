"""Database session store that keeps the expiry loaded with the session row.

Ticket-list 304 handling uses ``loaded_expire_date`` to skip a sliding-expiry
write when the row is still fresh. Auth payload, save, and delete behavior
match Django's database backend.
"""

from django.contrib.sessions.backends.db import SessionStore as DatabaseSessionStore


class SessionStore(DatabaseSessionStore):
    def __init__(self, session_key=None):
        super().__init__(session_key)
        self.loaded_expire_date = None

    def load(self):
        session = self._get_session_from_db()
        if session is None:
            self.loaded_expire_date = None
            return {}
        self.loaded_expire_date = session.expire_date
        return self.decode(session.session_data)

    async def aload(self):
        session = await self._aget_session_from_db()
        if session is None:
            self.loaded_expire_date = None
            return {}
        self.loaded_expire_date = session.expire_date
        return self.decode(session.session_data)
