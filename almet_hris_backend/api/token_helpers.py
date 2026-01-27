# api/token_helpers.py
"""
Token Helper Functions
Handles both JWT (for API access) and Graph Token (for Outlook/Email)
"""

import logging
from django.contrib.auth.models import User
from .models import UserGraphToken

logger = logging.getLogger(__name__)


def get_user_tokens(user):
    """
    Get both JWT and Graph tokens for a user
    
    Args:
        user: Django User object
    
    Returns:
        dict: {
            'has_jwt': bool,
            'has_graph_token': bool,
            'graph_token': str or None,
            'graph_token_valid': bool
        }
    """
    # Check Graph token
    graph_token = UserGraphToken.get_valid_token(user)
    
    return {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'has_jwt': True,  # If this function is called, JWT is valid
        'has_graph_token': bool(graph_token),
        'graph_token': graph_token,
        'graph_token_valid': bool(graph_token)
    }


def extract_graph_token_from_request(request):
  
    # 1. Check custom header
    graph_token = request.META.get('HTTP_X_GRAPH_TOKEN')
    if graph_token:
        logger.info("Graph token found in X-Graph-Token header")
        return graph_token
    
    # 2. Check request data (for POST/PUT)
    if hasattr(request, 'data'):
        graph_token = request.data.get('graph_token')
        if graph_token:
            logger.info("Graph token found in request data")
            return graph_token
    
    # 3. Check database (stored during login)
    if request.user and request.user.is_authenticated:
        graph_token = UserGraphToken.get_valid_token(request.user)
        if graph_token:
            logger.info(f"Graph token found in database for user {request.user.username}")
            return graph_token
        else:
            logger.warning(f"No valid Graph token in database for user {request.user.username}")
    
    return None


def refresh_graph_token_if_needed(user):
    """
    Check if Graph token needs refresh and notify user
    
    Args:
        user: Django User object
    
    Returns:
        dict: {
            'needs_refresh': bool,
            'token_valid': bool,
            'message': str
        }
    """
    try:
        token_obj = UserGraphToken.objects.get(user=user)
        
        if token_obj.is_valid():
            return {
                'needs_refresh': False,
                'token_valid': True,
                'message': 'Graph token is valid'
            }
        else:
            return {
                'needs_refresh': True,
                'token_valid': False,
                'message': 'Graph token expired. Please login again to refresh.'
            }
    except UserGraphToken.DoesNotExist:
        return {
            'needs_refresh': True,
            'token_valid': False,
            'message': 'No Graph token found. Please login to obtain token.'
        }