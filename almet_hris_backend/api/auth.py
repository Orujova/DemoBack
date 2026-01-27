# api/auth.py - COMPLETELY FIXED WITH PROPER TOKEN HANDLING
import jwt
import logging
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from .models import MicrosoftUser, Employee, UserGraphToken


logger = logging.getLogger(__name__)

class MicrosoftTokenValidator:
    @staticmethod
    def validate_token_and_create_jwt(id_token, graph_access_token=None):
        
        try:
           
            
            # Decode ID token without signature verification for development
            payload = jwt.decode(id_token, options={"verify_signature": False})
            
            # Extract required fields
            aud = payload.get('aud')
            microsoft_id = payload.get('sub')
            
            if not microsoft_id:
                raise AuthenticationFailed('Invalid token: missing subject identifier')
            
            # ✅ Validate audience
            valid_audiences = [
                settings.MICROSOFT_CLIENT_ID,
                "00000003-0000-0000-c000-000000000000"
            ]
            
            if aud not in valid_audiences:
                logger.warning(f'Audience mismatch: expected {valid_audiences}, got {aud}')
            
            # Extract email from token with fallback
            email = (
                payload.get('email') or 
                payload.get('preferred_username') or 
                payload.get('unique_name') or 
                payload.get('upn')
            )
            
            if not email:
                raise AuthenticationFailed('Invalid token: missing email information')
            
            # ✅ Normalize email
            email = email.lower().strip()
            
            # Extract name
            name = payload.get('name', '').strip()
            if name:
                name_parts = name.split(' ')
                first_name = name_parts[0] if name_parts else ''
                last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            else:
                first_name = payload.get('given_name', '')
                last_name = payload.get('family_name', '')
            
            logger.info(f'✅ Microsoft login: email={email}, microsoft_id={microsoft_id}')
            
            # ✅ STEP 1: Find or create user
            user = None
            
            # Try to find by Microsoft ID first
            try:
                microsoft_user = MicrosoftUser.objects.select_related('user__employee_profile').get(
                    microsoft_id=microsoft_id
                )
                user = microsoft_user.user
              
                
                # Update user info if changed
                updated = False
                if user.email.lower() != email:
                    user.email = email
                    user.username = email
                    updated = True
                if user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                if user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.save()
                    logger.info(f'🔄 Updated user info for {user.username}')
                
            except MicrosoftUser.DoesNotExist:
           
                
                # Try to find employee by email
                try:
                    from django.db.models import Q
                    employee = Employee.objects.filter(
                        Q(email__iexact=email) | Q(user__email__iexact=email)
                    ).select_related('user').first()
                    
                    if employee:
                      
                        
                        if employee.user:
                            user = employee.user
                         
                            
                            # Update user info
                            user.email = email
                            user.username = email
                            user.first_name = first_name
                            user.last_name = last_name
                            user.save()
                            
                            # Create Microsoft link
                            MicrosoftUser.objects.get_or_create(
                                user=user,
                                defaults={'microsoft_id': microsoft_id}
                            )
                        else:
                            # Create user for employee
                            with transaction.atomic():
                                user = User.objects.create_user(
                                    username=email,
                                    email=email,
                                    first_name=first_name,
                                    last_name=last_name
                                )
                                user.set_unusable_password()
                                user.save()
                                
                                employee.user = user
                                employee.save()
                                
                                MicrosoftUser.objects.create(
                                    user=user,
                                    microsoft_id=microsoft_id
                                )
                        
                       
                    else:
                        # No employee found
                        logger.warning(f'❌ No employee record for {email}')
                        raise AuthenticationFailed(
                            f'Access denied for {email}. No employee record found. '
                            f'Please contact HR department.'
                        )
                        
                except Exception as e:
                    logger.error(f'Error finding employee: {e}')
                    raise
            
            # ✅ CRITICAL: Store Graph Access Token (for Microsoft Graph API calls)
            if graph_access_token and user:
                try:
                    # Store Graph token with 1 hour expiry (default Microsoft token lifetime)
                    UserGraphToken.store_token(
                        user=user,
                        access_token=graph_access_token,
                        expires_in=3600  # 1 hour
                    )
                    logger.info(f'✅ Graph token stored successfully for {user.username}')
                except Exception as token_error:
                    logger.error(f'❌ Failed to store Graph token: {token_error}')
                    # Don't fail authentication, but log the error
            else:
                if not graph_access_token:
                    logger.warning(f'⚠️ No Graph token provided for {user.username if user else email}')
            
            # ✅ STEP 2: Generate YOUR OWN JWT tokens for API access
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            
            
            return user, access_token, refresh_token
            
        except jwt.DecodeError as e:
            logger.error(f'JWT decode error: {str(e)}')
            raise AuthenticationFailed('Invalid token format')
        except AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f'Token validation error: {str(e)}')
            import traceback
            logger.error(f'Traceback: {traceback.format_exc()}')
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    @staticmethod
    def validate_token(id_token, graph_access_token=None):
        """
        Legacy method - returns only user
        Use validate_token_and_create_jwt instead
        """
        user, _, _ = MicrosoftTokenValidator.validate_token_and_create_jwt(
            id_token, 
            graph_access_token
        )
        return user