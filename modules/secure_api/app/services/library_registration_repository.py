from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Settings


class LibraryRegistrationError(Exception):
    pass


class DuplicateLibraryUserError(LibraryRegistrationError):
    pass


class InvalidSubscriptionTierError(LibraryRegistrationError):
    pass


class LibraryRegistrationRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @contextmanager
    def _connection(self):
        conn = psycopg.connect(
            host=self._settings.online_library_db_host,
            port=self._settings.online_library_db_port,
            dbname=self._settings.online_library_db_name,
            user=self._settings.online_library_db_user,
            password=self._settings.online_library_db_password,
            connect_timeout=5,
            row_factory=dict_row,
        )
        try:
            yield conn
        finally:
            conn.close()

    def list_subscription_tiers(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select tier_code, tier_name, description
                    from public.subscription_tiers
                    where status = 'ACTIVE'
                    order by display_order, tier_code
                    """
                )
                return list(cur.fetchall())

    def create_approved_user_subscription(
        self,
        *,
        full_name: str,
        email: str,
        keycloak_user_id: str,
        tier_code: str,
    ) -> str:
        with self._connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select 1
                        from public.subscription_tiers
                        where tier_code = %s and status = 'ACTIVE'
                        """,
                        (tier_code,),
                    )
                    if cur.fetchone() is None:
                        raise InvalidSubscriptionTierError(f"Unknown subscription tier: {tier_code}")

                    cur.execute(
                        """
                        select user_id
                        from public.library_users
                        where lower(email) = lower(%s)
                           or keycloak_user_id = %s
                        limit 1
                        """,
                        (email, keycloak_user_id),
                    )
                    if cur.fetchone() is not None:
                        raise DuplicateLibraryUserError("A library user already exists for this email or Keycloak user.")

                    cur.execute(
                        """
                        insert into public.library_users (
                            full_name,
                            email,
                            keycloak_user_id,
                            status,
                            approval_status,
                            approved_at
                        )
                        values (%s, %s, %s, 'ACTIVE', 'APPROVED', current_timestamp)
                        returning user_id
                        """,
                        (full_name, email, keycloak_user_id),
                    )
                    user_id = str(cur.fetchone()["user_id"])

                    cur.execute(
                        """
                        insert into public.user_approval_requests (
                            user_id,
                            request_status,
                            reviewed_at,
                            review_comments
                        )
                        values (%s, 'APPROVED', current_timestamp, 'Auto-approved during self-registration')
                        """,
                        (user_id,),
                    )
                    cur.execute(
                        """
                        insert into public.user_subscriptions (
                            user_id,
                            tier_code,
                            status
                        )
                        values (%s, %s, 'ACTIVE')
                        """,
                        (user_id, tier_code),
                    )
                conn.commit()
                return user_id
            except Exception:
                conn.rollback()
                raise
