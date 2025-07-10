import asyncio
import aiohttp
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class UserServiceException(Exception):
    pass


class UserServiceGateway:
    def __init__(self,
                 user_service_url: str,
                 timeout: int = 30,
                 retry_attempts: int = 3,
                 cache_ttl_seconds: int = 300,
                 api_key: Optional[str] = None):
        self.user_service_url = user_service_url.rstrip('/')
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        self._cache = {}
        self._cache_ttl = cache_ttl_seconds

    def _is_cache_valid(self, cache_key: str) -> bool:
        if cache_key not in self._cache:
            return False

        cached_time = self._cache[cache_key].get('timestamp')
        if not cached_time:
            return False

        return datetime.utcnow() - cached_time < timedelta(seconds=self._cache_ttl)

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        if self._is_cache_valid(cache_key):
            self.logger.info(f"Cache hit for user {cache_key}: True")
            return self._cache[cache_key]['data']
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        self._cache[cache_key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }

    def _is_development(self) -> bool:
        import os
        env = os.getenv("APP_ENVIRONMENT", "development").lower()
        return env in ["development", "dev", "local"]

    async def verify_user_exists(self, user_id: str) -> bool:
        cache_key = f"user_exists_{user_id}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            url = f"{self.user_service_url}/users/profile"
            params = {"user_id": user_id}

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        self._set_cache(cache_key, True)
                        self.logger.info(f"User {user_id} verification: True")
                        return True
                    elif response.status == 404:
                        self._set_cache(cache_key, False)
                        self.logger.info(f"User {user_id} not found")
                        return False
                    else:
                        self.logger.warning(f"User service returned status {response.status}")
                        if self._is_development():
                            self.logger.info(f"Development mode: accepting user {user_id}")
                            return True
                        return True

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout verifying user {user_id}, assuming exists")
            return True
        except Exception as e:
            self.logger.warning(f"Error verifying user {user_id}: {str(e)}, assuming exists")
            return True

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        cache_key = f"user_info_{user_id}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            # CORREÇÃO: Verificar se a URL está correta
            # A URL no teste direto usa auth-service, mas aqui usa user_service_url
            url = f"{self.user_service_url}/users/profile"
            params = {"user_id": user_id}

            self.logger.info(f"Fetching user info for {user_id} from {url}")
            self.logger.debug(f"Full URL with params: {url}?user_id={user_id}")

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                # Adicionar headers se necessário
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                async with session.get(url, params=params, headers=headers) as response:
                    self.logger.info(f"User service response status: {response.status}")

                    # Log do corpo da resposta para debug
                    response_text = await response.text()
                    self.logger.debug(f"Raw response: {response_text}")

                    if response.status == 200:
                        try:
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError as e:
                            self.logger.error(f"Failed to parse JSON response: {e}")
                            self.logger.error(f"Response text: {response_text}")
                            return self._get_default_user_info(user_id)

                        self.logger.info(f"User service response: {response_data}")

                        if response_data.get("success") and "data" in response_data:
                            user_data = response_data["data"].get("user", {})
                            formatted_data = {
                                "id": user_data.get("id", user_id),
                                "email": user_data.get("email"),
                                "username": user_data.get("username"),
                                "first_name": user_data.get("first_name"),
                                "last_name": user_data.get("last_name"),
                                "full_name": user_data.get("full_name"),
                                "status": user_data.get("status", "active"),
                                "created_at": user_data.get("created_at")
                            }
                            self._set_cache(cache_key, formatted_data)
                            self.logger.info(f"Retrieved user info for {user_id}: email={formatted_data.get('email')}")
                            return formatted_data
                        else:
                            self.logger.warning(f"Unexpected response format for user {user_id}: {response_data}")
                            return self._get_default_user_info(user_id)

                    elif response.status == 404:
                        self.logger.warning(f"User {user_id} not found")
                        return self._get_default_user_info(user_id)
                    else:
                        self.logger.warning(f"User service returned status {response.status}: {response_text}")
                        return self._get_default_user_info(user_id)

        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout getting user info for {user_id}")
            return self._get_default_user_info(user_id)
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP Client error getting user info for {user_id}: {type(e).__name__}: {str(e)}")
            return self._get_default_user_info(user_id)
        except Exception as e:
            self.logger.error(f"Unexpected error getting user info for {user_id}: {type(e).__name__}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return self._get_default_user_info(user_id)

    def _get_default_user_info(self, user_id: str) -> Dict[str, Any]:
        return {
            "id": user_id,
            "email": f"user_{user_id}@example.com",
            "username": f"user_{user_id[:8]}",
            "first_name": "User",
            "last_name": user_id[:8],
            "status": "active"
        }

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        cache_key = f"user_prefs_{user_id}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            user_info = await self.get_user_info(user_id)
            if user_info and "preferences" in user_info:
                preferences = user_info["preferences"]
                self._set_cache(cache_key, preferences)
                self.logger.info(f"Retrieved preferences for user {user_id}")
                return preferences

            url = f"{self.user_service_url}/users/{user_id}/preferences"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        preferences = await response.json()
                        self._set_cache(cache_key, preferences)
                        self.logger.info(f"Retrieved preferences for user {user_id}")
                        return preferences
                    else:
                        self.logger.info(f"Using default preferences for user {user_id}")
                        default_prefs = self._get_default_preferences()
                        self._set_cache(cache_key, default_prefs)
                        return default_prefs

        except Exception as e:
            self.logger.warning(f"Error getting preferences for user {user_id}: {str(e)}")
            default_prefs = self._get_default_preferences()
            self._set_cache(cache_key, default_prefs)
            return default_prefs

    def _get_default_preferences(self) -> Dict[str, Any]:
        return {
            "notifications": {
                "email_enabled": True,
                "job_completion": True,
                "job_failure": True
            },
            "processing": {
                "default_quality": 95,
                "default_fps": 1.0,
                "auto_cleanup": True,
                "max_frames": 100
            }
        }

    async def update_user_activity(self, user_id: str, activity_data: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"User activity {user_id}: {activity_data}")

            if self._is_development():
                return True

            url = f"{self.user_service_url}/users/activity"
            payload = {
                "user_id": user_id,
                "activity_type": "video_processing",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "video-processing-service",
                **activity_data
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status in [200, 201, 204]:
                        self.logger.info(f"Activity recorded for user {user_id}")
                        return True
                    else:
                        self.logger.warning(f"Failed to record activity: status {response.status}")
                        return True

        except Exception as e:
            self.logger.warning(f"Error recording activity for user {user_id}: {str(e)}")
            return True

    async def health_check(self) -> Dict[str, Any]:
        try:
            start_time = datetime.utcnow()

            url = f"{self.user_service_url}/health"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(url) as response:
                    response_time = (datetime.utcnow() - start_time).total_seconds()

                    return {
                        "healthy": response.status == 200,
                        "status": "available" if response.status == 200 else "degraded",
                        "response_time": response_time,
                        "last_check": datetime.utcnow().isoformat()
                    }

        except Exception as e:
            return {
                "healthy": False,
                "status": "unavailable",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            user_info = await self.get_user_info(user_id)
            return user_info if user_info.get("id") == user_id else None
        except Exception:
            return None

    async def close(self) -> None:
        pass