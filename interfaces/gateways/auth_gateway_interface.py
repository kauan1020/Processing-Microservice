from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AuthGatewayInterface(ABC):
    """
    Gateway interface for authentication service integration.

    This interface defines the contract for communicating with the
    authentication microservice to validate user tokens, retrieve
    user information, and ensure proper authorization for video
    processing operations across the distributed system.

    The implementation should handle HTTP communication, token validation,
    caching for performance, and error handling for authentication
    service connectivity issues or token validation failures.
    """

    @abstractmethod
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token with the authentication service.

        This method communicates with the authentication microservice
        to verify token validity, extract user information, and ensure
        the token hasn't been revoked or expired for secure access control.

        Args:
            token: JWT token string to validate with the auth service

        Returns:
            Dict[str, Any]: Token validation result containing:
                - valid: Boolean indicating if token is valid
                - user_id: User identifier extracted from valid token
                - user_email: User email address for notifications
                - token_type: Type of token (access or refresh)
                - expires_at: Token expiration timestamp
                - issued_at: Token issuance timestamp
                - error: Error message if validation failed

        Raises:
            AuthGatewayException: If communication with auth service fails
                                 or service returns unexpected response format
        """
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve detailed user information from the authentication service.

        This method fetches comprehensive user profile data including
        email, permissions, and account status for processing authorization
        and user communication with caching for performance optimization.

        Args:
            user_id: Unique identifier of the user to retrieve information for

        Returns:
            Optional[Dict[str, Any]]: User information dictionary containing:
                - user_id: User unique identifier
                - email: User email address for notifications
                - username: User display name
                - first_name: User first name
                - last_name: User last name
                - status: Account status (active, inactive, blocked)
                - created_at: Account creation timestamp
                - last_login: Last login timestamp
                Returns None if user is not found

        Raises:
            AuthGatewayException: If communication with auth service fails
                                 or user lookup encounters system errors
        """
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh an expired access token using a valid refresh token.

        This method exchanges a valid refresh token for a new access token
        to maintain authenticated sessions for long-running processing
        operations without requiring user re-authentication.

        Args:
            refresh_token: Valid refresh token to exchange for new access token

        Returns:
            Optional[Dict[str, Any]]: Token refresh result containing:
                - access_token: New JWT access token for API access
                - token_type: Token type (typically "Bearer")
                - expires_in: Token expiration time in seconds
                - user_id: User identifier associated with the token
                Returns None if refresh token is invalid or expired

        Raises:
            AuthGatewayException: If token refresh fails due to service
                                 communication issues or invalid token format
        """
        pass

    @abstractmethod
    async def check_user_permissions(self, user_id: str, resource: str, action: str) -> bool:
        """
        Check if a user has permission to perform a specific action on a resource.

        This method verifies user permissions for fine-grained access control
        to ensure users can only access their own video processing jobs
        and perform authorized operations within the system.

        Args:
            user_id: Unique identifier of the user to check permissions for
            resource: Resource type being accessed (e.g., "video_job", "download")
            action: Action being performed (e.g., "read", "write", "delete")

        Returns:
            bool: True if user has permission to perform the action,
                 False if permission is denied or user doesn't exist

        Raises:
            AuthGatewayException: If permission check fails due to service
                                 communication errors or malformed requests
        """
        pass

    @abstractmethod
    async def invalidate_token(self, token: str) -> bool:
        """
        Invalidate a token by adding it to the revocation list.

        This method revokes a token to ensure it cannot be used for
        further authentication, useful for logout operations or
        security incidents requiring immediate token invalidation.

        Args:
            token: JWT token string to invalidate and add to revocation list

        Returns:
            bool: True if token was successfully invalidated,
                 False if invalidation failed or token was already invalid

        Raises:
            AuthGatewayException: If token invalidation fails due to
                                 communication issues with the auth service
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health and availability of the authentication service.

        This method performs health checks to ensure the authentication
        service is operational and responsive for circuit breaker patterns
        and system monitoring in the distributed processing environment.

        Returns:
            Dict[str, Any]: Health check result containing:
                - healthy: Boolean indicating service health status
                - response_time: Service response time in milliseconds
                - version: Authentication service version information
                - last_check_time: Timestamp of the health check
                - error: Error message if health check failed
        """
        pass

    @abstractmethod
    async def get_service_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information from the authentication service.

        This method retrieves detailed service metrics and statistics
        for monitoring, alerting, and system health dashboards to
        ensure optimal performance of the authentication integration.

        Returns:
            Dict[str, Any]: Service status information containing:
                - uptime: Service uptime in seconds
                - active_tokens: Number of currently active tokens
                - requests_per_second: Current request rate
                - error_rate: Error rate percentage
                - database_status: Authentication database connectivity status
                - cache_status: Token cache system status
        """
        pass