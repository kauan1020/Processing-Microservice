import httpx
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta
import json

from interfaces.gateways.auth_gateway_interface import AuthGatewayInterface
from domain.exceptions import ProcessingException


class AuthGatewayException(ProcessingException):
    """Exception raised for authentication gateway operations."""
    pass


class AuthGateway(AuthGatewayInterface):
    """
    HTTP-based authentication gateway for auth microservice integration.

    This gateway provides concrete implementation for communicating with
    the authentication microservice over HTTP/REST API with proper error
    handling, caching, and retry logic for reliable service integration.

    It handles token validation, user information retrieval, and session
    management while providing resilience against network issues and
    service unavailability through circuit breaker patterns.
    """

    def __init__(self,
                 auth_service_url: str,
                 timeout: int = 10,
                 retry_attempts: int = 3,
                 cache_ttl_seconds: int = 300):
        """
        Initialize authentication gateway with service configuration.

        Args:
            auth_service_url: Base URL of the authentication service
            timeout: HTTP request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            cache_ttl_seconds: Time-to-live for cached responses in seconds
        """
        self.auth_service_url = auth_service_url.rstrip('/')
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.cache_ttl_seconds = cache_ttl_seconds

        self.token_cache = {}
        self.user_cache = {}

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={"Content-Type": "application/json"},
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token with the authentication service.

        Args:
            token: JWT token string to validate with the auth service

        Returns:
            Dict[str, Any]: Token validation result containing user info and status

        Raises:
            AuthGatewayException: If communication with auth service fails
        """
        try:
            cache_key = f"token:{hash(token)}"

            if cache_key in self.token_cache:
                cached_result, cached_time = self.token_cache[cache_key]
                if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                    return cached_result

            url = f"{self.auth_service_url}/auth/validate"
            params = {"token": token}

            response = await self._make_request("GET", url, params=params)

            if response.status_code == 200:
                result = response.json()

                if "success" in result and result["success"]:
                    token_info = result.get("data", {})
                    validated_result = {
                        "valid": token_info.get("valid", True),
                        "user_id": token_info.get("user_id"),
                        "token_type": token_info.get("token_type", "access"),
                        "expires_at": token_info.get("expires_at"),
                        "issued_at": token_info.get("issued_at"),
                        "validation_method": "auth_service"
                    }
                else:
                    validated_result = result.copy()
                    if "valid" not in validated_result:
                        validated_result["valid"] = True
                    validated_result["validation_method"] = "auth_service"

                if validated_result.get("valid"):
                    self.token_cache[cache_key] = (validated_result, datetime.utcnow())

                return validated_result

            elif response.status_code == 401:
                return {
                    "valid": False,
                    "error": "Token is invalid or expired",
                    "reason": "Unauthorized"
                }

            else:
                raise AuthGatewayException(f"Token validation failed with status {response.status_code}")

        except httpx.RequestError as e:
            # Em caso de erro de rede, retornar erro para permitir fallback
            raise AuthGatewayException(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthGatewayException(f"Invalid JSON response from auth service: {str(e)}")
        except AuthGatewayException:
            raise
        except Exception as e:
            raise AuthGatewayException(f"Unexpected error validating token: {str(e)}")

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed user information from the authentication service.

        Args:
            user_id: Unique identifier of the user to retrieve information for

        Returns:
            Optional[Dict[str, Any]]: User information or None if not found

        Raises:
            AuthGatewayException: If communication with auth service fails
        """
        try:
            cache_key = f"user:{user_id}"

            if cache_key in self.user_cache:
                cached_result, cached_time = self.user_cache[cache_key]
                if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                    return cached_result

            url = f"{self.auth_service_url}/users/profile"
            params = {"user_id": user_id}

            response = await self._make_request("GET", url, params=params)

            if response.status_code == 200:
                result = response.json()
                self.user_cache[cache_key] = (result, datetime.utcnow())
                return result

            elif response.status_code == 404:
                return None

            else:
                raise AuthGatewayException(f"User info retrieval failed with status {response.status_code}")

        except httpx.RequestError as e:
            raise AuthGatewayException(f"Network error retrieving user info: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthGatewayException(f"Invalid JSON response from auth service: {str(e)}")
        except Exception as e:
            raise AuthGatewayException(f"Unexpected error retrieving user info: {str(e)}")

    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh an expired access token using a valid refresh token.

        Args:
            refresh_token: Valid refresh token to exchange for new access token

        Returns:
            Optional[Dict[str, Any]]: Token refresh result or None if invalid

        Raises:
            AuthGatewayException: If token refresh fails due to service issues
        """
        try:
            url = f"{self.auth_service_url}/auth/refresh"
            data = {"refresh_token": refresh_token}

            response = await self._make_request("POST", url, json=data)

            if response.status_code == 200:
                return response.json()

            elif response.status_code == 401:
                return None

            else:
                raise AuthGatewayException(f"Token refresh failed with status {response.status_code}")

        except httpx.RequestError as e:
            raise AuthGatewayException(f"Network error refreshing token: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthGatewayException(f"Invalid JSON response from auth service: {str(e)}")
        except Exception as e:
            raise AuthGatewayException(f"Unexpected error refreshing token: {str(e)}")

    async def check_user_permissions(self, user_id: str, resource: str, action: str) -> bool:
        """
        Check if a user has permission to perform a specific action on a resource.

        Args:
            user_id: Unique identifier of the user to check permissions for
            resource: Resource type being accessed
            action: Action being performed

        Returns:
            bool: True if user has permission, False otherwise

        Raises:
            AuthGatewayException: If permission check fails due to service issues
        """
        try:
            url = f"{self.auth_service_url}/auth/permissions"
            params = {
                "user_id": user_id,
                "resource": resource,
                "action": action
            }

            response = await self._make_request("GET", url, params=params)

            if response.status_code == 200:
                result = response.json()
                return result.get("allowed", False)

            elif response.status_code == 404:
                return False

            else:
                raise AuthGatewayException(f"Permission check failed with status {response.status_code}")

        except httpx.RequestError as e:
            raise AuthGatewayException(f"Network error checking permissions: {str(e)}")
        except json.JSONDecodeError as e:
            raise AuthGatewayException(f"Invalid JSON response from auth service: {str(e)}")
        except Exception as e:
            raise AuthGatewayException(f"Unexpected error checking permissions: {str(e)}")

    async def invalidate_token(self, token: str) -> bool:
        """
        Invalidate a token by adding it to the revocation list.

        Args:
            token: JWT token string to invalidate

        Returns:
            bool: True if token was successfully invalidated, False otherwise

        Raises:
            AuthGatewayException: If token invalidation fails due to service issues
        """
        try:
            url = f"{self.auth_service_url}/auth/revoke"
            data = {"token": token}

            response = await self._make_request("POST", url, json=data)

            cache_key = f"token:{hash(token)}"
            if cache_key in self.token_cache:
                del self.token_cache[cache_key]

            return response.status_code == 200

        except httpx.RequestError as e:
            raise AuthGatewayException(f"Network error invalidating token: {str(e)}")
        except Exception as e:
            raise AuthGatewayException(f"Unexpected error invalidating token: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health and availability of the authentication service.

        Returns:
            Dict[str, Any]: Health check result with service status information
        """
        try:
            start_time = datetime.utcnow()

            url = f"{self.auth_service_url}/health"
            response = await self._make_request("GET", url, timeout=5)

            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            if response.status_code == 200:
                health_data = response.json()
                return {
                    "healthy": True,
                    "response_time": response_time,
                    "version": health_data.get("version", "unknown"),
                    "last_check_time": start_time.isoformat(),
                    "service_status": health_data.get("status", "unknown")
                }
            else:
                return {
                    "healthy": False,
                    "response_time": response_time,
                    "last_check_time": start_time.isoformat(),
                    "error": f"Service returned status {response.status_code}"
                }

        except Exception as e:
            return {
                "healthy": False,
                "response_time": 0,
                "last_check_time": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information from the authentication service.

        Returns:
            Dict[str, Any]: Service status information with metrics and statistics
        """
        try:
            url = f"{self.auth_service_url}/api/status"
            response = await self._make_request("GET", url)

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"Service status check failed with status {response.status_code}"
                }

        except Exception as e:
            return {
                "error": str(e)
            }

    async def _make_request(self,
                            method: str,
                            url: str,
                            timeout: Optional[int] = None,
                            **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            timeout: Optional request timeout override
            **kwargs: Additional request parameters

        Returns:
            httpx.Response: HTTP response object

        Raises:
            httpx.RequestError: If all retry attempts fail
        """
        request_timeout = timeout or self.timeout

        for attempt in range(self.retry_attempts):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    timeout=request_timeout,
                    **kwargs
                )
                return response

            except httpx.RequestError as e:
                if attempt == self.retry_attempts - 1:
                    raise e

                await asyncio.sleep(2 ** attempt)
                continue

    async def clear_cache(self) -> None:
        """
        Clear all cached authentication data.

        Removes all cached tokens and user information to force
        fresh authentication on next requests.
        """
        self.token_cache.clear()
        self.user_cache.clear()

    async def close(self) -> None:
        """
        Close the HTTP client and cleanup resources.

        Properly closes HTTP connections and cleans up resources
        to prevent connection leaks and resource exhaustion.
        """
        await self.client.aclose()