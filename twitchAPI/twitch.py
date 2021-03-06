#  Copyright (c) 2020. Lena "Teekeks" During <info@teawork.de>
"""
The Twitch API client
---------------------

This is the base of this library, it handles authentication renewal, error handling and permission management.

Look at the `Twitch API reference <https://dev.twitch.tv/docs/api/reference>`__ for a more detailed documentation on
what each endpoint does.

**************
Example Usage:
**************

.. code-block:: python

    from twitchAPI.twitch import Twitch
    from pprint import pprint
    twitch = Twitch('my_app_key', 'my_app_secret')
    # lets create a simple app authentication:
    twitch.authenticate_app([])
    pprint(twitch.get_users(logins=['your_twitch_username']))


**************
Authentication
**************

The Twitch API knows 2 different authentications. App and User Authentication.
Which one you need (or if one at all) depends on what calls you want to use.

Its always good to get at least App authentication even for calls where you dont need it since the rate limmits are way better for authenticated calls.


App Authentication
==================

App authentication is super simple, just do the following:

.. code-block:: python

    from twitchAPI.twitch import Twitch
    twitch = Twitch('my_app_id', 'my_app_secret')
    # add App authentication
    twitch.authenticate_app([])


User Authentication
===================

To get a user auth token, the user has to explicitly click "Authorize" on the twitch website. You can use various online
services to generate a token or use my build in authenticator.

See :obj:`twitchAPI.oauth` for more info.

********************
Class Documentation:
********************
"""
import requests
from typing import Union, List, Optional
from .helper import build_url, TWITCH_API_BASE_URL, TWITCH_AUTH_BASE_URL, make_fields_datetime, build_scope, \
    fields_to_enum
from datetime import datetime
from .types import *


class Twitch:
    """
    Twitch API client

    :param str app_id: Your app id
    :param str app_secret: Your app secret
    :var bool auto_refresh_auth: If set to true, auto refresh the auth token once it expires. |default| :code:`True`
    """
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    __app_auth_token: Optional[str] = None
    __app_auth_scope: List[AuthScope] = []
    __has_app_auth: bool = False

    __user_auth_token: Optional[str] = None
    __user_auth_refresh_token: Optional[str] = None
    __user_auth_scope: List[AuthScope] = []
    __has_user_auth: bool = False

    auto_refresh_auth: bool = True

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret

    def __generate_header(self, auth_type: 'AuthType', required_scope: List[AuthScope]) -> dict:
        header = {"Client-ID": self.app_id}
        if auth_type == AuthType.APP:
            if not self.__has_app_auth:
                raise UnauthorizedException('Require app authentication!')
            for s in required_scope:
                if s not in self.__app_auth_scope:
                    raise MissingScopeException('Require app auth scope ' + s.name)
            header['Authorization'] = f'Bearer {self.__app_auth_token}'
        elif auth_type == AuthType.USER:
            if not self.__has_user_auth:
                raise UnauthorizedException('require user authentication!')
            for s in required_scope:
                if s not in self.__user_auth_scope:
                    raise MissingScopeException('Require user auth scope ' + s.name)
            header['Authorization'] = f'Bearer {self.__user_auth_token}'
        elif self.__has_user_auth or self.__has_app_auth:
            # if no required, set one anyway to get better rate limits if possible
            header['Authorization'] = \
                f'Bearer {self.__user_auth_token if self.__has_user_auth else self.__app_auth_token}'
        return header

    def refresh_used_token(self):
        """Refreshes the currently used token"""
        if self.__has_user_auth:
            from .oauth import refresh_access_token
            self.__user_auth_token,\
                self.__user_auth_refresh_token = refresh_access_token(self.__user_auth_refresh_token,
                                                                      self.app_id,
                                                                      self.app_secret)
        else:
            self.__generate_app_token()

    def __api_post_request(self,
                           url: str,
                           auth_type: 'AuthType',
                           required_scope: List[AuthScope],
                           data: Optional[dict] = None,
                           retries: int = 1) -> requests.Response:
        """Make POST request with authorization"""
        headers = self.__generate_header(auth_type, required_scope)
        req = None
        if data is None:
            req = requests.post(url, headers=headers)
        else:
            req = requests.post(url, headers=headers, json=data)
        if self.auto_refresh_auth and retries > 0:
            if req.status_code == 401:
                # unauthorized, lets try to refresh the token once
                self.refresh_used_token()
                return self.__api_post_request(url, auth_type, required_scope, data=data, retries=retries - 1)
            elif req.status_code == 503:
                # service unavailable, retry exactly once as recommended by twitch documentation
                return self.__api_post_request(url, auth_type, required_scope, data=data, retries=0)
        elif self.auto_refresh_auth and retries <= 0:
            if req.status_code == 503:
                raise TwitchBackendException('The Twitch API returns a server error')
        return req

    def __api_put_request(self,
                          url: str,
                          auth_type: 'AuthType',
                          required_scope: List[AuthScope],
                          data: Optional[dict] = None,
                          retries: int = 1) -> requests.Response:
        """Make PUT request with authorization"""
        headers = self.__generate_header(auth_type, required_scope)
        req = None
        if data is None:
            req = requests.put(url, headers=headers)
        else:
            req = requests.put(url, headers=headers, json=data)
        if self.auto_refresh_auth and retries > 0:
            if req.status_code == 401:
                # unauthorized, lets try to refresh the token once
                self.refresh_used_token()
                return self.__api_put_request(url, auth_type, required_scope, data=data, retries=retries - 1)
            elif req.status_code == 503:
                # service unavailable, retry exactly once as recommended by twitch documentation
                return self.__api_put_request(url, auth_type, required_scope, data=data, retries=0)
        elif self.auto_refresh_auth and retries <= 0:
            if req.status_code == 503:
                raise TwitchBackendException('The Twitch API returns a server error')
        return req

    def __api_patch_request(self,
                            url: str,
                            auth_type: 'AuthType',
                            required_scope: List[AuthScope],
                            data: Optional[dict] = None,
                            retries: int = 1) -> requests.Response:
        """Make PATCH request with authorization"""
        headers = self.__generate_header(auth_type, required_scope)
        req = None
        if data is None:
            req = requests.patch(url, headers=headers)
        else:
            req = requests.patch(url, headers=headers, json=data)
        if self.auto_refresh_auth and retries > 0:
            if req.status_code == 401:
                # unauthorized, lets try to refresh the token once
                self.refresh_used_token()
                return self.__api_patch_request(url, auth_type, required_scope, data=data, retries=retries - 1)
            elif req.status_code == 503:
                # service unavailable, retry exactly once as recommended by twitch documentation
                return self.__api_patch_request(url, auth_type, required_scope, data=data, retries=0)
        elif self.auto_refresh_auth and retries <= 0:
            if req.status_code == 503:
                raise TwitchBackendException('The Twitch API returns a server error')
        return req

    def __api_delete_request(self,
                             url: str,
                             auth_type: 'AuthType',
                             required_scope: List[AuthScope],
                             data: Optional[dict] = None,
                             retries: int = 1) -> requests.Response:
        """Make DELETE request with authorization"""
        headers = self.__generate_header(auth_type, required_scope)
        req = None
        if data is None:
            req = requests.delete(url, headers=headers)
        else:
            req = requests.delete(url, headers=headers, json=data)
        if self.auto_refresh_auth and retries > 0:
            if req.status_code == 401:
                # unauthorized, lets try to refresh the token once
                self.refresh_used_token()
                return self.__api_delete_request(url, auth_type, required_scope, data=data, retries=retries - 1)
            elif req.status_code == 503:
                # service unavailable, retry exactly once as recommended by twitch documentation
                return self.__api_delete_request(url, auth_type, required_scope, data=data, retries=0)
        elif self.auto_refresh_auth and retries <= 0:
            if req.status_code == 503:
                raise TwitchBackendException('The Twitch API returns a server error')
        return req

    def __api_get_request(self, url: str,
                          auth_type: 'AuthType',
                          required_scope: List[AuthScope],
                          retries: int = 1) -> requests.Response:
        """Make GET request with authorization"""
        headers = self.__generate_header(auth_type, required_scope)
        req = requests.get(url, headers=headers)
        if self.auto_refresh_auth and retries > 0:
            if req.status_code == 401:
                # unauthorized, lets try to refresh the token once
                self.refresh_used_token()
                return self.__api_get_request(url,  auth_type, required_scope, retries - 1)
            elif req.status_code == 503:
                # service unavailable, retry exactly once as recommended by twitch documentation
                return self.__api_get_request(url, auth_type, required_scope, 0)
        elif self.auto_refresh_auth and retries <= 0:
            if req.status_code == 503:
                raise TwitchBackendException('The Twitch API returns a server error')
        return req

    def __generate_app_token(self) -> None:
        params = {
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'grant_type': 'client_credentials',
            'scope': build_scope(self.__app_auth_scope)
        }
        url = build_url(TWITCH_AUTH_BASE_URL + 'oauth2/token', params)
        result = requests.post(url)
        if result.status_code != 200:
            raise TwitchAuthorizationException(f'Authentication failed with code {result.status_code} ({result.text})')
        try:
            data = result.json()
            self.__app_auth_token = data['access_token']
        except ValueError:
            raise TwitchAuthorizationException('Authentication response did not have a valid json body')
        except KeyError:
            raise TwitchAuthorizationException('Authentication response did not contain access_token')

    def authenticate_app(self, scope: List[AuthScope]) -> None:
        """Authenticate with a fresh generated app token

        :param list[~twitchAPI.types.AuthScope] scope: List of Authorization scopes to use
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the authentication fails
        :return: None
        """
        self.__app_auth_scope = scope
        self.__generate_app_token()
        self.__has_app_auth = True

    def set_user_authentication(self, token: str, scope: List[AuthScope], refresh_token: Optional[str] = None) -> None:
        """Set a user token to be used.

        :param str token: the generated user token
        :param list[~twitchAPI.types.AuthScope] scope: List of Authorization Scopes that the given user token has
        :param str refresh_token: The generated refresh token, has to be provided if :attr:`auto_refresh_auth` is True
        :return: None
        :raises ValueError: if :attr:`auto_refresh_auth` is True but refresh_token is not set
        """
        if refresh_token is None and self.auto_refresh_auth:
            raise ValueError('refresh_token has to be provided when auto_refresh_user_auth is True')
        self.__user_auth_token = token
        self.__user_auth_refresh_token = refresh_token
        self.__user_auth_scope = scope
        self.__has_user_auth = True

    def get_app_token(self) -> Union[str, None]:
        """Returns the app token that the api uses or None when not authenticated.

        :return: app token
        :rtype: Union[str, None]
        """
        return self.__app_auth_token

    def get_user_auth_token(self) -> Union[str, None]:
        """Returns the current user auth token, None if no user Authentication is set

        :return: current user auth token
        :rtype: str or None
        """
        return self.__user_auth_token

    def get_used_token(self) -> Union[str, None]:
        """Returns the currently used token, can be either the app or user auth Token or None if no auth is set

        :return: the currently used auth token or None if no Authentication is set
        """
        # if no auth is set, self.__app_auth_token will be None
        return self.__user_auth_token if self.__has_user_auth else self.__app_auth_token
    # ======================================================================================================================
    # API calls
    # ======================================================================================================================

    def get_extension_analytics(self,
                                after: Optional[str] = None,
                                extension_id: Optional[str] = None,
                                first: int = 20,
                                ended_at: Optional[datetime] = None,
                                started_at: Optional[datetime] = None,
                                report_type: Optional[AnalyticsReportType] = None) -> dict:
        """Gets a URL that extension developers can use to download analytics reports (CSV files) for their extensions.
        The URL is valid for 5 minutes.\n\n

        Requires User authentication with scope :py:const:`twitchAPI.types.AuthScope.ANALYTICS_READ_EXTENSION`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-extension-analytics

        :param str after: cursor for forward pagination
        :param str extension_id: If this is specified, the returned URL points to an analytics report for just the specified
                            extension.
        :param int first: Maximum number of objects returned, range 1 to 100, |default| :code:`20`
        :param ~datetime.datetime ended_at: Ending date/time for returned reports, if this is provided,
                        `started_at` must also be specified.
        :param ~datetime.datetime started_at: Starting date/time for returned reports, if this is provided,
                        `ended_at` must also be specified.
        :param ~twitchAPI.types.AnalyticsReportType report_type: Type of analytics report that is returned
        :rtype: dict
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: When you only supply `started_at` or `ended_at` without the other or when first is not in
                        range 1 to 100
        """
        if ended_at is not None or started_at is not None:
            # you have to put in both:
            if ended_at is None or started_at is None:
                raise ValueError('you must specify both ended_at and started_at')
            if started_at > ended_at:
                raise ValueError('started_at must be before ended_at')
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        url_params = {
            'after': after,
            'ended_at': ended_at.isoformat() if ended_at is not None else None,
            'extension_id': extension_id,
            'first': first,
            'started_at': started_at.isoformat() if started_at is not None else None,
            'type': report_type.value if report_type is not None else None
        }
        url = build_url(TWITCH_API_BASE_URL + 'analytics/extensions',
                        url_params,
                        remove_none=True)
        response = self.__api_get_request(url, AuthType.USER, required_scope=[AuthScope.ANALYTICS_READ_EXTENSION])
        data = response.json()
        return make_fields_datetime(data, ['started_at', 'ended_at'])

    def get_game_analytics(self,
                           after: Optional[str] = None,
                           first: int = 20,
                           game_id: Optional[str] = None,
                           ended_at: Optional[datetime] = None,
                           started_at: Optional[datetime] = None,
                           report_type: Optional[AnalyticsReportType] = None) -> dict:
        """Gets a URL that game developers can use to download analytics reports (CSV files) for their games.
        The URL is valid for 5 minutes.\n\n

        Requires User authentication with scope :py:const:`twitchAPI.types.AuthScope.ANALYTICS_READ_GAMES`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-game-analytics

        :param str after: cursor for forward pagination
        :param int first: Maximum number of objects returned, range 1 to 100, |default| :code:`20`
        :param str game_id: Game ID
        :param ~datetime.datetime ended_at: Ending date/time for returned reports, if this is provided,
                        `started_at` must also be specified.
        :param ~datetime.datetime started_at: Starting date/time for returned reports, if this is provided,
                        `ended_at` must also be specified.
        :param ~twitchAPI.types.AnalyticsReportType report_type: Type of analytics report that is returned.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: When you only supply `started_at` or `ended_at` without the other or when first is not in
                        range 1 to 100
        :rtype: dict
        """
        if ended_at is not None or started_at is not None:
            if ended_at is None or started_at is None:
                raise ValueError('you must specify both ended_at and started_at')
            if ended_at < started_at:
                raise ValueError('ended_at must be after started_at')
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        url_params = {
            'after': after,
            'ended_at': ended_at.isoformat() if ended_at is not None else None,
            'first': first,
            'game_id': game_id,
            'started_at': started_at.isoformat() if started_at is not None else None,
            'type': report_type.value if report_type is not None else None
        }
        url = build_url(TWITCH_API_BASE_URL + 'analytics/games',
                        url_params,
                        remove_none=True)
        response = self.__api_get_request(url, AuthType.USER, [AuthScope.ANALYTICS_READ_GAMES])
        data = response.json()
        return make_fields_datetime(data, ['ended_at', 'started_at'])

    def get_bits_leaderboard(self,
                             count: int = 10,
                             period: TimePeriod = TimePeriod.ALL,
                             started_at: Optional[datetime] = None,
                             user_id: Optional[str] = None) -> dict:
        """Gets a ranked list of Bits leaderboard information for an authorized broadcaster.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.BITS_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-bits-leaderboard

        :param int count: Number of results to be returned. In range 1 to 100, |default| :code:`10`
        :param ~twitchAPI.types.TimePeriod period: Time period over which data is aggregated, default
                :const:`twitchAPI.types.TimePeriod.ALL`
        :param ~datetime.datetime started_at: Timestamp for the period over which the returned data is aggregated.
        :param str user_id: ID of the user whose results are returned; i.e., the person who paid for the Bits.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if count > 100 or count < 1:
            raise ValueError('count must be between 1 and 100')
        url_params = {
            'count': count,
            'period': period.value,
            'started_at': started_at.isoformat() if started_at is not None else None,
            'user_id': user_id
        }
        url = build_url(TWITCH_API_BASE_URL + 'bits/leaderboard', url_params, remove_none=True)
        response = self.__api_get_request(url, AuthType.USER, [AuthScope.BITS_READ])
        data = response.json()
        return make_fields_datetime(data, ['ended_at', 'started_at'])

    def get_extension_transactions(self,
                                   extension_id: str,
                                   transaction_id: Optional[str] = None,
                                   after: Optional[str] = None,
                                   first: int = 20) -> dict:
        """Get Extension Transactions allows extension back end servers to fetch a list of transactions that have
        occurred for their extension across all of Twitch.
        A transaction is a record of a user exchanging Bits for an in-Extension digital good.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-extension-transactions

        :param str extension_id: ID of the extension to list transactions for.
        :param str transaction_id: Transaction IDs to look up.
        :param str after: cursor for forward pagination
        :param int first: Maximum number of objects returned, range 1 to 100, |default| :code:`20`
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first > 100 or first < 1:
            raise ValueError("first must be between 1 and 100")
        url_param = {
            'extension_id': extension_id,
            'id': transaction_id,
            'after': after,
            first: first
        }
        url = build_url(TWITCH_API_BASE_URL + 'extensions/transactions', url_param, remove_none=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        data = result.json()
        return make_fields_datetime(data, ['timestamp'])

    def create_clip(self,
                    broadcaster_id: str,
                    has_delay: bool = False) -> dict:
        """Creates a clip programmatically. This returns both an ID and an edit URL for the new clip.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.CLIPS_EDIT`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#create-clip

        :param str broadcaster_id: Broadcaster ID of the stream from which the clip will be made.
        :param bool has_delay: If False, the clip is captured from the live stream when the API is called; otherwise,
                a delay is added before the clip is captured (to account for the brief delay between the broadcaster’s
                stream and the viewer’s experience of that stream). |default| :code:`False`
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        param = {
            'broadcaster_id': broadcaster_id,
            'has_delay': str(has_delay).lower()
        }
        url = build_url(TWITCH_API_BASE_URL + 'clips', param)
        result = self.__api_post_request(url, AuthType.USER, [AuthScope.CLIPS_EDIT])
        return result.json()

    def get_clips(self,
                  broadcaster_id: Optional[str] = None,
                  game_id: Optional[str] = None,
                  clip_id: Optional[List[str]] = None,
                  after: Optional[str] = None,
                  before: Optional[str] = None,
                  ended_at: Optional[datetime] = None,
                  started_at: Optional[datetime] = None,
                  first: int = 20) -> dict:
        """Gets clip information by clip ID (one or more), broadcaster ID (one only), or game ID (one only).
        Clips are returned sorted by view count, in descending order.\n\n

        Requires App or User authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-clips

        :param str broadcaster_id: ID of the broadcaster for whom clips are returned.
        :param str game_id: ID of the game for which clips are returned.
        :param list[str] clip_id: ID of the clip being queried. Limit: 100.
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :param ~datetime.datetime ended_at: Ending date/time for returned clips
        :param ~datetime.datetime started_at: Starting date/time for returned clips
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if you try to query more than 100 clips in one call
        :raises ValueError: if not exactly one of clip_id, broadcaster_id or game_id is given
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if clip_id is not None and len(clip_id) > 100:
            raise ValueError('A maximum of 100 clips can be queried in one call')
        if not (sum([clip_id is not None, broadcaster_id is not None, game_id is not None]) == 1):
            raise ValueError('You need to specify exactly one of clip_id, broadcaster_id or game_id')
        if first < 1 or first > 100:
            raise ValueError('first must be in range 1 to 100')
        param = {
            'broadcaster_id': broadcaster_id,
            'game_id': game_id,
            'clip_id': clip_id,
            'after': after,
            'before': before,
            'first': first,
            'ended_at': ended_at.astimezone().isoformat() if ended_at is not None else None,
            'started_at': started_at.astimezone().isoformat() if started_at is not None else None
        }
        url = build_url(TWITCH_API_BASE_URL + 'clips', param, split_lists=True, remove_none=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        data = result.json()
        return make_fields_datetime(data, ['created_at'])

    def create_entitlement_grants_upload_url(self,
                                             manifest_id: str) -> dict:
        """Creates a URL where you can upload a manifest file and notify users that they have an entitlement.
        Entitlements are digital items that users are entitled to use.
        Twitch entitlements are granted to users gratis or as part of a purchase on Twitch.\n\n

        Requires App authentication\n
        For detailed documentation, see here:
        https://dev.twitch.tv/docs/api/reference#create-entitlement-grants-upload-url

        :param str manifest_id: Unique identifier of the manifest file to be uploaded. Must be 1-64 characters.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the the authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if length of manifest_id is not in range 1 to 64
        :rtype: dict
        """
        if len(manifest_id) < 1 or len(manifest_id) > 64:
            raise ValueError('manifest_id must be between 1 and 64 characters long!')
        param = {
            'manifest_id': manifest_id,
            'type': 'bulk_drops_grant'
        }
        url = build_url(TWITCH_API_BASE_URL + 'entitlements/upload', param)
        result = self.__api_post_request(url, AuthType.APP, [])
        return result.json()

    def get_code_status(self,
                        code: List[str],
                        user_id: int) -> dict:
        """Gets the status of one or more provided Bits codes.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-code-status

        :param list[str] code: The code to get the status of. Maximum of 20 entries
        :param int user_id: Represents the numeric Twitch user ID of the account which is going to receive the
                        entitlement associated with the code.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if length of code is not in range 1 to 20
        :rtype: dict
        """
        if len(code) > 20 or len(code) < 1:
            raise ValueError('only between 1 and 20 codes are allowed')
        param = {
            'code': code,
            'user_id': user_id
        }
        url = build_url(TWITCH_API_BASE_URL + 'entitlements/codes', param, split_lists=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        data = result.json()
        return fields_to_enum(data, ['status'], CodeStatus, CodeStatus.UNKNOWN_VALUE)

    def redeem_code(self,
                    code: List[str],
                    user_id: int) -> dict:
        """Redeems one or more provided Bits codes to the authenticated Twitch user.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#redeem-code

        :param list[str] code: The code to redeem to the authenticated user’s account. Maximum of 20 entries
        :param int user_id: Represents the numeric Twitch user ID of the account which  is going to receive the
                        entitlement associated with the code.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if length of code is not in range 1 to 20
        :rtype: dict
        """
        if len(code) > 20 or len(code) < 1:
            raise ValueError('only between 1 and 20 codes are allowed')
        param = {
            'code': code,
            'user_id': user_id
        }
        url = build_url(TWITCH_API_BASE_URL + 'entitlements/code', param, split_lists=True)
        result = self.__api_post_request(url, AuthType.APP, [])
        data = result.json()
        return fields_to_enum(data, ['status'], CodeStatus, CodeStatus.UNKNOWN_VALUE)

    def get_top_games(self,
                      after: Optional[str] = None,
                      before: Optional[str] = None,
                      first: int = 20) -> dict:
        """Gets games sorted by number of current viewers on Twitch, most popular first.\n\n

        Requires App or User authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-top-games

        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        param = {
            'after': after,
            'before': before,
            'first': first
        }
        url = build_url(TWITCH_API_BASE_URL + 'games/top', param, remove_none=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        return result.json()

    def get_games(self,
                  game_ids: Optional[List[str]] = None,
                  names: Optional[List[str]] = None) -> dict:
        """Gets game information by game ID or name.\n\n

        Requires User or App authentication.
        In total, only 100 game ids and names can be fetched at once.

        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-games

        :param list[str] game_ids: Game ID
        :param list[str] names: Game Name
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if neither game_ids nor names are given or if game_ids and names are more than 100 entries
                        combined.
        :rtype: dict
        """
        if game_ids is None and names is None:
            raise ValueError('at least one of either game_ids and names has to be set')
        if (len(game_ids) if game_ids is not None else 0) + (len(names) if names is not None else 0) > 100:
            raise ValueError('in total, only 100 game_ids and names can be passed')
        param = {
            'id': game_ids,
            'name': names
        }
        url = build_url(TWITCH_API_BASE_URL + 'games', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        return result.json()

    def check_automod_status(self,
                             broadcaster_id: str,
                             msg_id: str,
                             msg_text: str,
                             user_id: str) -> dict:
        """Determines whether a string message meets the channel’s AutoMod requirements.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.MODERATION_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#check-automod-status

        :param str broadcaster_id: Provided broadcaster ID must match the user ID in the user auth token.
        :param str msg_id: Developer-generated identifier for mapping messages to results.
        :param str msg_text: Message text.
        :param str user_id: User ID of the sender.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        # TODO you can pass multiple sets in the body, account for that
        url_param = {
            'broadcaster_id': broadcaster_id
        }
        url = build_url(TWITCH_API_BASE_URL + 'moderation/enforcements/status', url_param)
        body = {
            'data': [{
                'msg_id': msg_id,
                'msg_text': msg_text,
                'user_id': user_id}
            ]
        }
        result = self.__api_post_request(url, AuthType.USER, [AuthScope.MODERATION_READ], data=body)
        return result.json()

    def get_banned_events(self,
                          broadcaster_id: str,
                          user_id: Optional[str] = None,
                          after: Optional[str] = None,
                          first: int = 20) -> dict:
        """Returns all user bans and un-bans in a channel.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.MODERATION_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-banned-events

        :param str broadcaster_id: Provided broadcaster ID must match the user ID in the user auth token.
        :param str user_id: Filters the results and only returns a status object for users who are banned in
                        this channel and have a matching user_id
        :param str after: Cursor for forward pagination
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 ot 100
        :rtype: dict
        """
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        param = {
            'broadcaster_id': broadcaster_id,
            'user_id': user_id,
            'after': after,
            'first': first
        }
        url = build_url(TWITCH_API_BASE_URL + 'moderation/banned/events', param, remove_none=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.MODERATION_READ])
        data = result.json()
        data = fields_to_enum(data, ['event_type'], ModerationEventType, ModerationEventType.UNKNOWN)
        data = make_fields_datetime(data, ['event_timestamp', 'expires_at'])
        return data

    def get_banned_users(self,
                         broadcaster_id: str,
                         user_id: Optional[str] = None,
                         after: Optional[str] = None,
                         before: Optional[str] = None) -> dict:
        """Returns all banned and timed-out users in a channel.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.MODERATION_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-banned-users

        :param str broadcaster_id: Provided broadcaster ID must match the user ID in the user auth token.
        :param str user_id: Filters the results and only returns a status object for users who are banned in this
                        channel and have a matching user_id.
        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        param = {
            'broadcaster_id': broadcaster_id,
            'user_id': user_id,
            'after': after,
            'before': before
        }
        url = build_url(TWITCH_API_BASE_URL + 'moderation/banned', param, remove_none=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.MODERATION_READ])
        return make_fields_datetime(result.json(), ['expires_at'])

    def get_moderators(self,
                       broadcaster_id: str,
                       user_ids: Optional[List[str]] = None,
                       after: Optional[str] = None) -> dict:
        """Returns all moderators in a channel.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.MODERATION_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-moderators

        :param str broadcaster_id: Provided broadcaster ID must match the user ID in the user auth token.
        :param list[str] user_ids: Filters the results and only returns a status object for users who are moderator in
                        this channel and have a matching user_id. Maximum 100
        :param str after: Cursor for forward pagination
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if user_ids has more than 100 entries
        :rtype: dict
        """
        if user_ids is not None and len(user_ids) > 100:
            raise ValueError('user_ids can only be 100 entries long')
        param = {
            'broadcaster_id': broadcaster_id,
            'user_id': user_ids,
            'after': after
        }
        url = build_url(TWITCH_API_BASE_URL + 'moderation/moderators', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.MODERATION_READ])
        return result.json()

    def get_moderator_events(self,
                             broadcaster_id: str,
                             user_ids: Optional[List[str]] = None) -> dict:
        """Returns a list of moderators or users added and removed as moderators from a channel.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.MODERATION_READ`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-moderator-events

        :param str broadcaster_id: Provided broadcaster ID must match the user ID in the user auth token.
        :param list[str] user_ids: Filters the results and only returns a status object for users who are moderator in
                        this channel and have a matching user_id. Maximum 100
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if user_ids has more than 100 entries
        :rtype: dict
        """
        if user_ids is not None and len(user_ids) > 100:
            raise ValueError('user_ids can only be 100 entries long')
        param = {
            'broadcaster_id': broadcaster_id,
            'user_id': user_ids
        }
        url = build_url(TWITCH_API_BASE_URL + 'moderation/moderators/events', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.MODERATION_READ])
        data = result.json()
        data = fields_to_enum(data, ['event_type'], ModerationEventType, ModerationEventType.UNKNOWN)
        data = make_fields_datetime(data, ['event_timestamp'])
        return data

    def create_stream_marker(self,
                             user_id: str,
                             description: Optional[str] = None) -> dict:
        """Creates a marker in the stream of a user specified by user ID.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_EDIT_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#create-stream-marker

        :param str user_id: ID of the broadcaster in whose live stream the marker is created.
        :param str description: Description of or comments on the marker. Max length is 140 characters.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if description has more than 140 characters
        :rtype: dict
        """
        if description is not None and len(description) > 140:
            raise ValueError('max length for description is 140')
        url = build_url(TWITCH_API_BASE_URL + 'streams/markers', {})
        body = {'user_id': user_id}
        if description is not None:
            body['description'] = description
        result = self.__api_post_request(url, AuthType.USER, [AuthScope.USER_EDIT_BROADCAST], data=body)
        data = result.json()
        return make_fields_datetime(data, ['created_at'])

    def get_streams(self,
                    after: Optional[str] = None,
                    before: Optional[str] = None,
                    first: int = 20,
                    game_id: Optional[List[str]] = None,
                    language: Optional[List[str]] = None,
                    user_id: Optional[List[str]] = None,
                    user_login: Optional[List[str]] = None) -> dict:
        """Gets information about active streams. Streams are returned sorted by number of current viewers, in
        descending order. Across multiple pages of results, there may be duplicate or missing streams, as viewers join
        and leave streams.\n\n

        Requires App or User authentication.\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-streams

        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :param list[str] game_id: Returns streams broadcasting a specified game ID. You can specify up to 100 IDs.
        :param list[str] language: Stream language. You can specify up to 100 languages.
        :param list[str] user_id: Returns streams broadcast by one or more specified user IDs. You can specify up
                        to 100 IDs.
        :param list[str] user_login: Returns streams broadcast by one or more specified user login names.
                        You can specify up to 100 names.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100 or one of the following fields have more than 100 entries:
                        `user_id, game_id, language, user_login`
        :rtype: dict
        """
        if user_id is not None and len(user_id) > 100:
            raise ValueError('a maximum of 100 user_id entries are allowed')
        if user_login is not None and len(user_login) > 100:
            raise ValueError('a maximum of 100 user_login entries are allowed')
        if language is not None and len(language) > 100:
            raise ValueError('a maximum of 100 languages are allowed')
        if game_id is not None and len(game_id) > 100:
            raise ValueError('a maximum of 100 game_id entries are allowed')
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        param = {
            'after': after,
            'before': before,
            'first': first,
            'game_id': game_id,
            'language': language,
            'user_id': user_id,
            'user_login': user_login
        }
        url = build_url(TWITCH_API_BASE_URL + 'streams', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        data = result.json()
        return make_fields_datetime(data, ['started_at'])

    def get_stream_markers(self,
                           user_id: str,
                           video_id: str,
                           after: Optional[str] = None,
                           before: Optional[str] = None,
                           first: int = 20) -> dict:
        """Gets a list of markers for either a specified user’s most recent stream or a specified VOD/video (stream),
        ordered by recency.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_READ_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-stream-markers

        Only one of user_id and video_id must be specified.

        :param str user_id: ID of the broadcaster from whose stream markers are returned.
        :param str video_id: ID of the VOD/video whose stream markers are returned.
        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :param int first: Number of values to be returned when getting videos by user or game ID. Limit: 100.
                        |default| :code:`20`
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100 or neither user_id nor video_id is provided
        :rtype: dict
        """
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        if user_id is None and video_id is None:
            raise ValueError('you must specify either user_id and/or video_id')
        param = {
            'user_id': user_id,
            'video_id': video_id,
            'after': after,
            'before': before,
            'first': first
        }
        url = build_url(TWITCH_API_BASE_URL + 'streams/markers', param, remove_none=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.USER_READ_BROADCAST])
        return make_fields_datetime(result.json(), ['created_at'])

    def get_broadcaster_subscriptions(self,
                                      broadcaster_id: str,
                                      user_ids: Optional[List[str]] = None) -> dict:
        """Get all of a broadcaster’s subscriptions.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.CHANNEL_READ_SUBSCRIPTIONS`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-broadcaster-subscriptions

        :param str broadcaster_id: User ID of the broadcaster. Must match the User ID in the Bearer token.
        :param list[str] user_ids: Unique identifier of account to get subscription status of. Maximum 100 entries
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if user_ids has more than 100 entries
        :rtype: dict
        """
        if user_ids is not None and len(user_ids) > 100:
            raise ValueError('user_ids can have a maximum of 100 entries')
        param = {
            'broadcaster_id': broadcaster_id,
            'user_id': user_ids
        }
        url = build_url(TWITCH_API_BASE_URL + 'subscriptions', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.CHANNEL_READ_SUBSCRIPTIONS])
        return result.json()

    def get_all_stream_tags(self,
                            after: Optional[str] = None,
                            first: int = 20,
                            tag_ids: Optional[List[str]] = None) -> dict:
        """Gets the list of all stream tags defined by Twitch, optionally filtered by tag ID(s).\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-all-stream-tags

        :param str after: Cursor for forward pagination
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :param list[str] tag_ids: IDs of tags. Maximum 100 entries
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100 or tag_ids has more than 100 entries
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        if tag_ids is not None and len(tag_ids) > 100:
            raise ValueError('tag_ids can not have more than 100 entries')
        param = {
            'after': after,
            'first': first,
            'tag_id': tag_ids
        }
        url = build_url(TWITCH_API_BASE_URL + 'tags/streams', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        return result.json()

    def get_stream_tags(self,
                        broadcaster_id: str) -> dict:
        """Gets the list of tags for a specified stream (channel).\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-stream-tags

        :param str broadcaster_id: ID of the stream thats tags are going to be fetched
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'streams/tags', {'broadcaster_id': broadcaster_id})
        result = self.__api_get_request(url, AuthType.APP, [])
        return result.json()

    def replace_stream_tags(self,
                            broadcaster_id: str,
                            tag_ids: List[str]) -> dict:
        """Applies specified tags to a specified stream, overwriting any existing tags applied to that stream.
        If no tags are specified, all tags previously applied to the stream are removed.
        Automated tags are not affected by this operation.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_EDIT_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#replace-stream-tags

        :param str broadcaster_id: ID of the stream for which tags are to be replaced.
        :param list[str] tag_ids: IDs of tags to be applied to the stream. Maximum of 100 supported.
        :return: {}
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if more than 100 tag_ids where provided
        :rtype: dict
        """
        if len(tag_ids) > 100:
            raise ValueError('tag_ids can not have more than 100 entries')
        url = build_url(TWITCH_API_BASE_URL + 'streams/tags', {'broadcaster_id': broadcaster_id})
        self.__api_put_request(url, AuthType.USER, [AuthScope.USER_EDIT_BROADCAST], data={'tag_ids': tag_ids})
        # this returns nothing
        return {}

    def get_users(self,
                  user_ids: Optional[List[str]] = None,
                  logins: Optional[List[str]] = None) -> dict:
        """Gets information about one or more specified Twitch users.
        Users are identified by optional user IDs and/or login name.
        If neither a user ID nor a login name is specified, the user is the one authenticated.\n\n

        Requires App authentication if either user_ids or logins is provided, otherwise requires a User authentication.
        If you have user Authentication and want to get your email info, you also need the authentication scope
        :const:`twitchAPI.types.AuthScope.USER_READ_EMAIL`\n
        If you provide user_ids and/or logins, the maximum combined entries should not exceed 100.

        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-users

        :param list[str] user_ids: User ID. Multiple user IDs can be specified. Limit: 100.
        :param list[str] logins: User login name. Multiple login names can be specified. Limit: 100.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if more than 100 combined user_ids and logins where provided
        :rtype: dict
        """
        if (len(user_ids) if user_ids is not None else 0) + (len(logins) if logins is not None else 0) > 100:
            raise ValueError('the total number of entries in user_ids and logins can not be more than 100')
        url_params = {
            'id': user_ids,
            'login': logins
        }
        url = build_url(TWITCH_API_BASE_URL + 'users', url_params, remove_none=True, split_lists=True)
        response = self.__api_get_request(url,
                                          AuthType.USER if user_ids is None and logins is None else AuthType.APP,
                                          [])
        return response.json()

    def get_users_follows(self,
                          after: Optional[str] = None,
                          first: int = 20,
                          from_id: Optional[str] = None,
                          to_id: Optional[str] = None) -> dict:
        """Gets information on follow relationships between two Twitch users.
        Information returned is sorted in order, most recent follow first.\n\n

        Requires App authentication.\n
        You have to use at least one of the following fields: from_id, to_id
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-users-follows

        :param str after: Cursor for forward pagination
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`20`
        :param str from_id: User ID. The request returns information about users who are being followed by
                        the from_id user.
        :param str to_id: User ID. The request returns information about users who are following the to_id user.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100 or neither from_id nor to_id is provided
        :rtype: dict
        """
        if first > 100 or first < 1:
            raise ValueError('first must be between 1 and 100')
        if from_id is None and to_id is None:
            raise ValueError('at least one of from_id and to_id needs to be set')
        param = {
            'after': after,
            'first': first,
            'from_id': from_id,
            'to_id': to_id
        }
        url = build_url(TWITCH_API_BASE_URL + 'users/follows', param, remove_none=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        return make_fields_datetime(result.json(), ['followed_at'])

    def update_user(self,
                    description: str) -> dict:
        """Updates the description of the Authenticated user.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_EDIT`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#update-user

        :param str description: User’s account description
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'users', {'description': description})
        result = self.__api_put_request(url, AuthType.USER, [AuthScope.USER_EDIT])
        return result.json()

    def get_user_extensions(self) -> dict:
        """Gets a list of all extensions (both active and inactive) for the authenticated user\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_READ_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-user-extensions

        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'users/extensions/list', {})
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.USER_READ_BROADCAST])
        return result.json()

    def get_user_active_extensions(self,
                                   user_id: Optional[str] = None) -> dict:
        """Gets information about active extensions installed by a specified user, identified by a user ID or the
        authenticated user.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_READ_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-user-active-extensions

        :param str user_id: ID of the user whose installed extensions will be returned.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'users/extensions', {'user_id': user_id}, remove_none=True)
        result = self.__api_get_request(url, AuthType.USER, [AuthScope.USER_READ_BROADCAST])
        return result.json()

    def update_user_extensions(self,
                               data: dict) -> dict:
        """"Updates the activation state, extension ID, and/or version number of installed extensions
        for the authenticated user.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_EDIT_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#update-user-extensions

        :param dict data: The user extension data to be written
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'users/extensions', {})
        result = self.__api_put_request(url,
                                        AuthType.USER,
                                        [AuthScope.USER_EDIT_BROADCAST],
                                        data=data)
        return result.json()

    def get_videos(self,
                   ids: Optional[List[str]] = None,
                   user_id: Optional[str] = None,
                   game_id: Optional[str] = None,
                   after: Optional[str] = None,
                   before: Optional[str] = None,
                   first: int = 20,
                   language: Optional[str] = None,
                   period: TimePeriod = TimePeriod.ALL,
                   sort: SortMethod = SortMethod.TIME,
                   video_type: VideoType = VideoType.ALL) -> dict:
        """Gets video information by video ID (one or more), user ID (one only), or game ID (one only).\n\n

        Requires App authentication.\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-videos

        :param list[str] ids: ID of the video being queried. Limit: 100.
        :param str user_id: ID of the user who owns the video.
        :param str game_id: ID of the game the video is of.
        :param str after: Cursor for forward pagination
        :param str before: Cursor for backward pagination
        :param int first: Number of values to be returned when getting videos by user or game ID.
                        Limit: 100. Default: 20.
        :param str language: Language of the video being queried.
        :param ~twitchAPI.types.TimePeriod period: Period during which the video was created.
        :param ~twitchAPI.types.SortMethod sort: Sort order of the videos.
        :param ~twitchAPI.types.VideoType video_type: Type of video.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100, ids has more than 100 entries or none of ids, user_id
                        nor game_id is provided.
        :rtype: dict
        """
        if ids is None and user_id is None and game_id is None:
            raise ValueError('you must use either ids, user_id or game_id')
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        if ids is not None and len(ids) > 100:
            raise ValueError('ids can only have a maximum of 100 entries')
        param = {
            'id': ids,
            'user_id': user_id,
            'game_id': game_id,
            'after': after,
            'before': before,
            'first': first,
            'language': language,
            'period': period.value,
            'sort': sort.value,
            'type': video_type.value
        }
        url = build_url(TWITCH_API_BASE_URL + 'videos', param, remove_none=True, split_lists=True)
        result = self.__api_get_request(url, AuthType.APP, [])
        data = result.json()
        data = make_fields_datetime(data, ['created_at', 'published_at'])
        data = fields_to_enum(data, ['type'], VideoType, VideoType.UNKNOWN)
        return data

    def get_webhook_subscriptions(self,
                                  first: Optional[int] = 20,
                                  after: Optional[str] = None) -> dict:
        """Gets the Webhook subscriptions of the authenticated user, in order of expiration.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-webhook-subscriptions

        :param int first: Number of values to be returned per page. Limit: 100. |default| :code:`20`
        :param str after: Cursor for forward pagination
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be in range 1 to 100')
        url = build_url(TWITCH_API_BASE_URL + 'webhooks/subscriptions',
                        {'first': first, 'after': after},
                        remove_none=True)
        response = self.__api_get_request(url, AuthType.APP, [])
        return response.json()

    def get_channel_information(self,
                                broadcaster_id: str) -> dict:
        """Gets channel information for users.\n\n

        Requires App or user authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-channel-information

        :param str broadcaster_id: ID of the channel to be updated
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'channels', {'broadcaster_id': broadcaster_id})
        response = self.__api_get_request(url, AuthType.APP, [])
        return response.json()

    def modify_channel_information(self,
                                   broadcaster_id: str,
                                   game_id: Optional[str] = None,
                                   broadcaster_language: Optional[str] = None,
                                   title: Optional[str] = None) -> bool:
        """Modifies channel information for users.\n\n

        Requires User authentication with scope :const:`twitchAPI.types.AuthScope.USER_EDIT_BROADCAST`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#modify-channel-information

        :param str broadcaster_id: ID of the channel to be updated
        :param str game_id: The current game ID being played on the channel
        :param str broadcaster_language: The language of the channel
        :param str title: The title of the stream
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if none of the following fiends are specified: `game_id, broadcaster_language, title`
        :rtype: bool
        """
        if game_id is None and broadcaster_language is None and title is None:
            raise ValueError('You need to specify at least one of the optional parameter')
        url = build_url(TWITCH_API_BASE_URL + 'channels',
                        {'broadcaster_id': broadcaster_id}, remove_none=True)
        body = {k: v for k, v in {'game_id': game_id,
                                  'broadcaster_language': broadcaster_language,
                                  'title': title} if v is not None}
        response = self.__api_patch_request(url, AuthType.USER, [AuthScope.USER_EDIT_BROADCAST], data=body)
        return response.status_code == 204

    def search_channels(self,
                        query: str,
                        first: Optional[int] = 20,
                        after: Optional[str] = None,
                        live_only: Optional[bool] = False) -> dict:
        """Returns a list of channels (users who have streamed within the past 6 months) that match the query via
        channel name or description either entirely or partially.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#search-channels

        :param str query: search query
        :param int first: Maximum number of objects to return. Maximum: 100 |default| :code:`20`
        :param str after: Cursor for forward pagination
        :param bool live_only: Filter results for live streams only. Default: False
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        url = build_url(TWITCH_API_BASE_URL + 'search/channels',
                        {'query': query,
                         'first': first,
                         'after': after,
                         'live_only': live_only}, remove_none=True)
        response = self.__api_get_request(url, AuthType.APP, [])
        return make_fields_datetime(response.json(), ['started_at'])

    def search_categories(self,
                          query: str,
                          first: Optional[int] = 20,
                          after: Optional[str] = None) -> dict:
        """Returns a list of games or categories that match the query via name either entirely or partially.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#search-categories

        :param str query: search query
        :param int first: Maximum number of objects to return. Maximum: 100 |default| :code:`20`
        :param str after: Cursor for forward pagination
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        url = build_url(TWITCH_API_BASE_URL + 'search/categories',
                        {'query': query,
                         'first': first,
                         'after': after}, remove_none=True)
        response = self.__api_get_request(url, AuthType.APP, [])
        return response.json()

    def get_stream_key(self,
                       broadcaster_id: str) -> dict:
        """Gets the channel stream key for a user.\n\n

        Requires User authentication with :const:`twitchAPI.types.AuthScope.CHANNEL_READ_STREAM_KEY`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-stream-key

        :param str broadcaster_id: User ID of the broadcaster
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'streams/key', {'broadcaster_id': broadcaster_id})
        response = self.__api_get_request(url, AuthType.USER, [AuthScope.CHANNEL_READ_STREAM_KEY])
        return response.json()

    def start_commercial(self,
                         broadcaster_id: str,
                         length: int) -> dict:
        """Starts a commercial on a specified channel.\n\n

        Requires User authentication with :const:`twitchAPI.types.AuthScope.CHANNEL_EDIT_COMMERCIAL`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#start-commercial

        :param str broadcaster_id: ID of the channel requesting a commercial
        :param int length: Desired length of the commercial in seconds. , one of these: [30, 60, 90, 120, 150, 180]
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if length is not one of these: `30, 60, 90, 120, 150, 180`
        :rtype: dict
        """
        if length not in [30, 60, 90, 120, 150, 180]:
            raise ValueError('length needs to be one of these: [30, 60, 90, 120, 150, 180]')
        url = build_url(TWITCH_API_BASE_URL + 'channels/commercial',
                        {'broadcaster_id': broadcaster_id,
                         'length': length})
        response = self.__api_post_request(url, AuthType.USER, [AuthScope.CHANNEL_EDIT_COMMERCIAL])
        return response.json()

    def create_user_follows(self,
                            from_id: str,
                            to_id: str,
                            allow_notifications: Optional[bool] = False) -> bool:
        """Adds a specified user to the followers of a specified channel.\n\n

        Requires User authentication with :const:`twitchAPI.types.AuthScope.USER_EDIT_FOLLOWS`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#create-user-follows

        :param str from_id: User ID of the follower
        :param str to_id: ID of the channel to be followed by the user
        :param bool allow_notifications: If true, the user gets email or push notifications (depending on the user’s
                        notification settings) when the channel goes live. Default value is false.
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: bool
        """
        url = build_url(TWITCH_API_BASE_URL + 'users/follows',
                        {'from_id': from_id,
                         'to_id': to_id,
                         'allow_notifications': allow_notifications}, remove_none=True)
        response = self.__api_post_request(url, AuthType.USER, [AuthScope.USER_EDIT_FOLLOWS])
        return response.status_code == 204

    def delete_user_follows(self,
                            from_id: str,
                            to_id: str) -> bool:
        """Deletes a specified user from the followers of a specified channel.\n\n

        Requires User authentication with :const:`twitchAPI.types.AuthScope.USER_EDIT_FOLLOWS`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#delete-user-follows

        :param str from_id: User ID of the follower
        :param str to_id: Channel to be unfollowed by the user
        :raises ~twitchAPI.types.UnauthorizedException: if user authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: bool
        """
        url = build_url(TWITCH_API_BASE_URL + 'users/follows',
                        {'from_id': from_id,
                         'to_id': to_id})
        response = self.__api_delete_request(url, AuthType.USER, [AuthScope.USER_EDIT_FOLLOWS])
        return response.status_code == 204

    def get_cheermotes(self,
                       broadcaster_id: str) -> dict:
        """Retrieves the list of available Cheermotes, animated emotes to which viewers can assign Bits,
        to cheer in chat.\n\n

        Requires App authentication\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-cheermotes

        :param str broadcaster_id: ID for the broadcaster who might own specialized Cheermotes.
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :rtype: dict
        """
        url = build_url(TWITCH_API_BASE_URL + 'bits/cheermotes',
                        {'broadcaster_id': broadcaster_id})
        response = self.__api_get_request(url, AuthType.APP, [])
        return make_fields_datetime(response.json(), ['last_updated'])

    def get_hype_train_events(self,
                              broadcaster_id: str,
                              first: Optional[int] = 1,
                              id: Optional[str] = None,
                              cursor: Optional[str] = None) -> dict:
        """Gets the information of the most recent Hype Train of the given channel ID.
        When there is currently an active Hype Train, it returns information about that Hype Train.
        When there is currently no active Hype Train, it returns information about the most recent Hype Train.
        After 5 days, if no Hype Train has been active, the endpoint will return an empty response.\n\n

        Requires App or User authentication with :const:`twitchAPI.types.AuthScope.CHANNEL_READ_HYPE_TRAIN`\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-hype-train-events

        :param str broadcaster_id: User ID of the broadcaster.
        :param int first: Maximum number of objects to return. Maximum: 100. |default| :code:`1`
        :param str id: The id of the wanted event, if known
        :param str cursor: Cursor for forward pagination
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.MissingScopeException: if the user or app authentication is missing the required scope
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        url = build_url(TWITCH_API_BASE_URL + 'hypetrain/events',
                        {'broadcaster_id': broadcaster_id,
                         'first': first,
                         'id': id,
                         'cursor': cursor}, remove_none=True)
        response = self.__api_get_request(url, AuthType.APP, [AuthScope.CHANNEL_READ_HYPE_TRAIN])
        data = make_fields_datetime(response.json(), ['event_timestamp',
                                                      'started_at',
                                                      'expires_at',
                                                      'cooldown_end_time'])
        data = fields_to_enum(data, ['type'], HypeTrainContributionMethod, HypeTrainContributionMethod.UNKNOWN)
        return data

    def get_drops_entitlements(self,
                               id: Optional[str] = None,
                               user_id: Optional[str] = None,
                               game_id: Optional[str] = None,
                               after: Optional[str] = None,
                               first: Optional[int] = 20) -> dict:
        """Gets a list of entitlements for a given organization that have been granted to a game, user, or both.

        OAuth Token Client ID must have ownership of Game\n\n

        Requires App authentication\n
        See Twitch documentation for valid parameter combinations!\n
        For detailed documentation, see here: https://dev.twitch.tv/docs/api/reference#get-drops-entitlements

        :param str id: Unique Identifier of the entitlement
        :param str user_id: A Twitch User ID
        :param str game_id: A Twitch Game ID
        :param str after: The cursor used to fetch the next page of data.
        :param int first: Maximum number of entitlements to return. Maximum: 100 |default| :code:`20`
        :raises ~twitchAPI.types.UnauthorizedException: if app authentication is not set
        :raises ~twitchAPI.types.TwitchAuthorizationException: if the used authentication token became invalid
                        and a re authentication failed
        :raises ~twitchAPI.types.TwitchBackendException: if the Twitch API itself runs into problems
        :raises ValueError: if first is not in range 1 to 100
        :rtype: dict
        """
        if first < 1 or first > 100:
            raise ValueError('first must be between 1 and 100')
        url = build_url(TWITCH_API_BASE_URL + 'entitlements/drops',
                        {
                            'id': id,
                            'user_id': user_id,
                            'game_id': game_id,
                            'after': after,
                            'first': first
                        }, remove_none=True)
        response = self.__api_get_request(url, AuthType.APP, [])
        data = make_fields_datetime(response.json(), ['timestamp'])
        return data

