from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, PostSerializer, PartiesSerializer, CandidatesSerializer
from rest_framework import status
from .models import User, Post, Parties, Candidates, DailyImpressions
from django.db import models
import jwt, datetime
from rest_framework.exceptions import AuthenticationFailed
from .utilities.auth_utils.reset_password import send_password_reset_email
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from base64 import b64encode
import csv
import io
import os
import requests
from django.http import HttpResponse



# Check Existing User Data View
class CheckExistingUserData(APIView):
    def post(self, request):
        try:
            username = request.data.get('username', '').strip()
            email = request.data.get('email', '').strip()
            
            errors = []
            
            # Check if username already exists
            if username and User.objects.filter(username=username).exists():
                errors.append('Username already exists')
            
            # Check if email already exists
            if email and User.objects.filter(email=email).exists():
                errors.append('E-mail already exists')
            
            if errors:
                return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({'message': 'Username and email are available'}, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': 'An error occurred while checking user data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Sign Up User View
class SignUpUser(APIView):
    def post(self, request):
        try:
            # Get username and email from request
            username = request.data.get('username', '').strip()
            email = request.data.get('email', '').strip()
            is_resend = request.data.get('resend', False)

            # Validate required fields for new signup
            if not is_resend:
                if not username:
                    return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)

                if not email:
                    return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)

                # Check if email already exists
                if User.objects.filter(email=email).exists():
                    return Response({'error': 'E-mail already exists'}, status=status.HTTP_400_BAD_REQUEST)

            # For resend, only email is required
            if is_resend and not email:
                return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

            # Handle resend OTP case
            if is_resend:
                # Check if user exists
                user = User.objects.filter(email=email).first()
                if not user:
                    return Response({'error': 'User not found. Please sign up first.'}, status=status.HTTP_404_NOT_FOUND)

                # Import OTP utilities
                from .utilities.otp_utils import create_and_send_otp

                # Create and send OTP
                success, otp_obj, message = create_and_send_otp(email)

                if success:
                    return Response({
                        'message': 'OTP sent successfully.',
                        'email': email
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({'error': f'Failed to send OTP: {message}'},
                                  status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Handle new signup case
            # Serialize the data
            serializer = UserSerializer(data=request.data)
            # Check if the data is valid
            if serializer.is_valid():
                # Save the data
                user = serializer.save()

                # Import OTP utilities
                from .utilities.otp_utils import create_and_send_otp

                # Create and send OTP
                success, otp_obj, message = create_and_send_otp(email)

                if success:
                    return Response({
                        'message': 'User created successfully. OTP sent to email.',
                        'user_id': user.id,
                        'email': email
                    }, status=status.HTTP_201_CREATED)
                else:
                    # If OTP sending fails, delete the user and return error
                    user.delete()
                    return Response({'error': f'User created but failed to send OTP: {message}'},
                                  status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Return the errors
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': 'An error occurred during signup'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Verify Signup View
class VerifySignup(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check if user exists in database
            user = User.objects.filter(email=email).first()
            
            if not user:
                return Response({'error': 'User registration not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Verify that the user was created recently (within last 5 minutes)
            if user.date_joined and (timezone.now() - user.date_joined).total_seconds() > 300:
                return Response({'error': 'Signup verification expired'}, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                'message': 'Signup verified successfully',
                'username': user.username
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Cleanup Signup View
class CleanupSignup(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find the user by email
            user = User.objects.filter(email=email).first()
            
            if not user:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if the user was created recently (within last 5 minutes)
            if user.date_joined and (timezone.now() - user.date_joined).total_seconds() > 300:
                return Response({'error': 'Cleanup not allowed for users created more than 5 minutes ago'}, 
                              status=status.HTTP_401_UNAUTHORIZED)
            
            # Delete the user
            user.delete()
            
            return Response({
                'message': 'User registration cleaned up successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# OTP Verification View
class VerifyOTP(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp_code')

        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp_code:
            return Response({'error': 'OTP code is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Import OTP utilities
            from .utilities.otp_utils import verify_otp

            # Verify the OTP
            success, message = verify_otp(email, otp_code)

            if success:
                # Find the user by email
                user = User.objects.filter(email=email).first()

                if not user:
                    return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

                # Mark user as verified and active
                user.is_email_verified = True
                user.is_active = True
                user.last_login = timezone.now()
                user.save(update_fields=['is_email_verified', 'is_active', 'last_login'])

                # Create JWT token now that OTP is verified
                payload = {
                    'id': user.id,
                    'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
                    'iat': datetime.datetime.utcnow(),
                }

                token = jwt.encode(payload, 'secret', algorithm='HS256')

                response = Response()
                response.set_cookie(
                    key='jwt',
                    value=token,
                    httponly=True,
                    max_age=60 * 60 * 24 * 365,  # 365 days in seconds
                    samesite='None',
                    secure=False,  # Keep False for local development without HTTPS
                    domain=None,
                    path='/',
                )

                response.data = {
                    'jwt': token,
                    'username': user.username,
                    'user_id': user.id,
                    'message': 'OTP verified successfully. Account activated.',
                }

                return response
            else:
                return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {'error': f'An error occurred during OTP verification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Check Username Availability View
class CheckUsernameAvailability(APIView):
    def post(self, request):
        # Getting the username from the request
        username = request.data.get('username', '')

        # Checking if the username exists
        exists = User.objects.filter(username=username).exists()

        # Returning the response
        return Response({'available': not exists}, status=status.HTTP_200_OK)



# Login User View
@method_decorator(csrf_exempt, name='dispatch')
class LoginUser(APIView):
    def post(self, request):
        print("Request data:", request.data)
        # Getting email and password Data from the user interface
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Getting User from the database
        user = User.objects.filter(email=email).first()

        # Checking if the user exists
        if user is None:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Checking if the password is correct
        if not user.check_password(password):
            return Response({'error': 'Invalid password'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # At this point credentials are valid. Do NOT issue JWT yet.
        # Instead, send an OTP that must be verified before authentication is completed.
        try:
            from .utilities.otp_utils import create_and_send_otp

            success, otp_obj, message = create_and_send_otp(email)
            if not success:
                return Response(
                    {'error': f'Failed to send OTP: {message}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    'otp_required': True,
                    'email': email,
                    'message': 'OTP sent to your email. Please verify to complete login.',
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred while sending OTP: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

# Verify Login View
class VerifyLogin(APIView):
    def post(self, request):
        # Getting the JWT token from the cookies
        token = request.COOKIES.get('jwt')

        if not token:
            return Response({'error': 'No authentication token found'}, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            
            # Getting the user from the database
            user = User.objects.filter(id=payload['id']).first()
            
            if not user:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Verify that the user's last login is recent (within last 5 minutes)
            if user.last_login and (timezone.now() - user.last_login).total_seconds() > 300:
                return Response({'error': 'Login session expired'}, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                'message': 'Login verified successfully',
                'username': user.username
            }, status=status.HTTP_200_OK)
            
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({'error': 'Invalid token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# User View
@method_decorator(csrf_exempt, name='dispatch')
class UserView(APIView):
    
    # Getting the user from the database
    def get(self, request):
        print("=== UserView GET request ===")
        print("Request cookies:", request.COOKIES)
        print("Request headers:", request.headers)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token: 
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try: 
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        # Enforce email verification via OTP before exposing user data
        if not getattr(user, 'is_email_verified', False):
            print("User email not verified via OTP")
            raise AuthenticationFailed('Email not verified via OTP')

        # Serializing the user
        serializer = UserSerializer(user)
        print("User serialized successfully")

        # Returning the response
        return Response(serializer.data)
    

# Logout User View
@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    def post(self, request):

        # Creating a response
        response = Response()

        # Deleting the cookie
        response.delete_cookie('jwt')

        # Setting the data
        response.data = {
            'message': 'Success'
        }
        
        # Returning The Response
        return response


# Reset Password Request View
class ResetPasswordRequest(APIView):
    def post(self, request):
        # Getting The Email From The Request
        email = request.data.get('email')
        
        # Checking If The Email Is Valid
        if not email:
            return Response({'error': 'Email Is Required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Getting The User From The Database
        user = User.objects.filter(email=email).first()
        
        # Checking If The User Exists
        if not user:
            return Response({'error': 'E-mail Does Not Exist'}, status=status.HTTP_404_NOT_FOUND)
            
        # Generating A Reset Token
        payload = {
            'id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            'iat': datetime.datetime.utcnow()
        }
        
        # Encoding The Payload
        reset_token = jwt.encode(payload, 'secret', algorithm='HS256')
        
        # Sending The Reset Password Email
        email_sent = send_password_reset_email(email, reset_token)
        
        # Checking If The Email Was Sent Successfully
        if email_sent:
            return Response({
                'message': 'Password Reset Email Sent',
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed To Send Reset Email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Reset Password Confirm View
class ResetPasswordConfirm(APIView):
    def post(self, request):

        # Getting The Token And New Password From The Request
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        # Checking If The Token And New Password Are Valid
        if not token or not new_password:
            return Response({'error': 'Token And New Password Are Required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Decoding The Token
        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            user = User.objects.filter(id=payload['id']).first()
            
            # Checking If The User Exists
            if not user:
                return Response({'error': 'User Not Found'}, status=status.HTTP_404_NOT_FOUND)
                
            # Setting The New Password
            user.set_password(new_password)
            user.save()
            
            # Returning The Response
            return Response({'message': 'Password Reset Successful'}, status=status.HTTP_200_OK)
            
        # Handling The Expired Token
        except jwt.ExpiredSignatureError:
            return Response({'error': 'Reset Token Has Expired'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handling The Invalid Token
        except jwt.InvalidTokenError:
            return Response({'error': 'Invalid Reset Token'}, status=status.HTTP_400_BAD_REQUEST)



# Update User Details View
@method_decorator(csrf_exempt, name='dispatch')
class ImportantDetails(APIView):
    def post(self, request):
        print("=== ImportantDetails POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        # Update user details
        update_fields = []
        
        if 'fullName' in request.data:
            user.full_name = request.data['fullName']
            update_fields.append('full_name')
            print("Updated full_name:", request.data['fullName'])
        
        if 'firstName' in request.data:
            user.first_name = request.data['firstName']
            update_fields.append('first_name')
            print("Updated first_name:", request.data['firstName'])
            
        if 'lastName' in request.data:
            user.last_name = request.data['lastName']
            update_fields.append('last_name')
            print("Updated last_name:", request.data['lastName'])

        # Save the changes
        if update_fields:
            user.save(update_fields=update_fields)
            print("User saved successfully with fields:", update_fields)

        # Return success response
        return Response({
            'message': 'User details updated successfully',
            'full_name': user.full_name,
            'first_name': user.first_name,
            'last_name': user.last_name
        }, status=status.HTTP_200_OK)




# Cleanup Signup View
class CleanupSignup(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Find the user by email
            user = User.objects.filter(email=email).first()
            
            if not user:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if the user was created recently (within last 5 minutes)
            if user.date_joined and (timezone.now() - user.date_joined).total_seconds() > 300:
                return Response({'error': 'Cleanup not allowed for users created more than 5 minutes ago'}, 
                              status=status.HTTP_401_UNAUTHORIZED)
            
            # Delete the user
            user.delete()
            
            return Response({
                'message': 'User registration cleaned up successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Update Profile Picture View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateProfilePicture(APIView):
    def post(self, request):
        print("=== UpdateProfilePicture POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data keys:", list(request.data.keys()) if request.data else "No data")
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        # Get the profile picture data from request
        profile_picture_data = request.data.get('profile_picture')
        
        if not profile_picture_data:
            print("No profile picture data provided")
            return Response({
                'error': 'Profile picture data is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Update the profile picture field with base64 data
            user.profile_picture = profile_picture_data
            user.save()
            print("Profile picture updated successfully")

            # Return success response
            return Response({
                'message': 'Profile picture updated successfully',
                'profile_picture': user.profile_picture
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error updating profile picture:", str(e))
            return Response({
                'error': f'Failed to update profile picture: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Update User Profile View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateUserProfile(APIView):
    def post(self, request):
        print("=== UpdateUserProfile POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        try:
            # Update user fields based on request data
            update_fields = []
            
            # Basic profile fields
            if 'username' in request.data:
                # Check if username is already taken by another user
                existing_user = User.objects.filter(username=request.data['username']).exclude(id=user.id).first()
                if existing_user:
                    return Response({
                        'error': 'Username already exists'
                    }, status=status.HTTP_400_BAD_REQUEST)
                user.username = request.data['username']
                update_fields.append('username')
            
            if 'full_name' in request.data:
                user.full_name = request.data['full_name']
                update_fields.append('full_name')
            
            if 'first_name' in request.data:
                user.first_name = request.data['first_name']
                update_fields.append('first_name')
            
            if 'last_name' in request.data:
                user.last_name = request.data['last_name']
                update_fields.append('last_name')
            
            # Personal details
            if 'bio' in request.data:
                user.bio = request.data['bio']
                update_fields.append('bio')
            

            
            if 'privacy_settings' in request.data:
                user.privacy_settings = request.data['privacy_settings']
                update_fields.append('privacy_settings')
            

            
            # Social media links
            if 'user_facebook' in request.data:
                user.user_facebook = request.data['user_facebook']
                update_fields.append('user_facebook')
            
            if 'user_instagram' in request.data:
                user.user_instagram = request.data['user_instagram']
                update_fields.append('user_instagram')
            
            if 'user_x_twitter' in request.data:
                user.user_x_twitter = request.data['user_x_twitter']
                update_fields.append('user_x_twitter')
            
            if 'user_threads' in request.data:
                user.user_threads = request.data['user_threads']
                update_fields.append('user_threads')
            
            if 'user_youtube' in request.data:
                user.user_youtube = request.data['user_youtube']
                update_fields.append('user_youtube')
            
            if 'user_linkedin' in request.data:
                user.user_linkedin = request.data['user_linkedin']
                update_fields.append('user_linkedin')
            
            if 'user_tiktok' in request.data:
                user.user_tiktok = request.data['user_tiktok']
                update_fields.append('user_tiktok')
            

            
            # Save the user with updated fields
            if update_fields:
                user.save(update_fields=update_fields)
                print("User profile updated successfully. Updated fields:", update_fields)
            else:
                print("No fields to update")
            
            # Return success response with updated user data
            serializer = UserSerializer(user)
            return Response({
                'message': 'Profile updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error updating user profile:", str(e))
            return Response({
                'error': f'Failed to update profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Update Notification Settings View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateNotificationSettings(APIView):
    def post(self, request):
        print("=== UpdateNotificationSettings POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        try:
            # Since notification-related fields were removed from the model,
            # we'll store these preferences in bio field or return a message
            print("Notification settings update requested, but fields removed from model")
            
            # Return success response
            serializer = UserSerializer(user)
            return Response({
                'message': 'Notification settings feature is currently disabled',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error updating notification settings:", str(e))
            return Response({
                'error': f'Failed to update notification settings: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Update Content Preferences View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateContentPreferences(APIView):
    def post(self, request):
        print("=== UpdateContentPreferences POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        try:
            # Since content preference fields were removed from the model,
            # we'll return a message indicating the feature is disabled
            print("Content preferences update requested, but fields removed from model")
            
            # Return success response
            serializer = UserSerializer(user)
            return Response({
                'message': 'Content preferences feature is currently disabled',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error updating content preferences:", str(e))
            return Response({
                'error': f'Failed to update content preferences: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Update Privacy Settings View
@method_decorator(csrf_exempt, name='dispatch')
class UpdatePrivacySettings(APIView):
    def post(self, request):
        print("=== UpdatePrivacySettings POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - raising AuthenticationFailed")
            raise AuthenticationFailed('Unauthenticated')
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            raise AuthenticationFailed('Token has expired')
        except Exception as e:
            print("JWT decode error:", str(e))
            raise AuthenticationFailed('Invalid token')
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            raise AuthenticationFailed('User not found')

        try:
            # Update privacy settings based on request data
            update_fields = []
            
            # Only privacy_settings field exists in the current model
            if 'privacy_settings' in request.data:
                user.privacy_settings = request.data['privacy_settings']
                update_fields.append('privacy_settings')
            
            # Save the user with updated fields
            if update_fields:
                user.save(update_fields=update_fields)
                print("Privacy settings updated successfully. Updated fields:", update_fields)
            else:
                print("No privacy settings to update")
            
            # Return success response with updated user data
            serializer = UserSerializer(user)
            return Response({
                'message': 'Privacy settings updated successfully',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error updating privacy settings:", str(e))
            return Response({
                'error': f'Failed to update privacy settings: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Create Post View
@method_decorator(csrf_exempt, name='dispatch')
class CreatePost(APIView):
    def post(self, request):
        print("=== CreatePost POST request ===")
        print("Request cookies:", request.COOKIES)
        print("Request data:", request.data)
        
        # Getting the JWT token from the cookies or Authorization header
        token = request.COOKIES.get('jwt')
        if not token:
            # Try to get token from Authorization header
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                print("JWT token found in Authorization header")
            else:
                print("No JWT token found in cookies or Authorization header")
        
        print("JWT token found:", bool(token))

        if not token:
            print("No JWT token found - returning 401")
            return Response({
                'error': 'Authentication required. Please log in.',
                'detail': 'No JWT token found in cookies or Authorization header'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Decoding the JWT token
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            print("JWT payload:", payload)
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
            return Response({
                'error': 'Token has expired. Please log in again.',
                'detail': 'JWT token has expired'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print("JWT decode error:", str(e))
            return Response({
                'error': 'Invalid authentication token. Please log in again.',
                'detail': f'JWT decode error: {str(e)}'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Getting the user from the database
        user = User.objects.filter(id=payload['id']).first()
        print("User found:", bool(user))
        
        if not user:
            print("User not found in database")
            return Response({
                'error': 'User not found. Please log in again.',
                'detail': 'User ID from token not found in database'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Set the user in the request so the serializer can access it
        request.user = user

        try:
            # Validate required fields
            content = request.data.get('content', '').strip()
            if not content:
                return Response({
                    'error': 'Post content is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user data from request for validation/logging
            user_data = request.data.get('user_data', {})
            print("Frontend user data:", user_data)
            
            # Validate that frontend user matches authenticated user
            if user_data:
                frontend_username = user_data.get('username')
                frontend_email = user_data.get('email')
                
                if frontend_username and frontend_username != user.username:
                    print(f"Warning: Frontend username ({frontend_username}) doesn't match authenticated user ({user.username})")
                
                if frontend_email and frontend_email != user.email:
                    print(f"Warning: Frontend email ({frontend_email}) doesn't match authenticated user ({user.email})")
            
            # Prepare data for serializer
            post_data = {
                'content': content,
                'images': request.data.get('images', []),
                'videos': request.data.get('videos', []),
                'is_anonymous': request.data.get('is_anonymous', False),
                'user_data': user_data,  # Pass the user_data to the serializer
                'parties_ids': request.data.get('parties_ids', [])  # Pass the parties IDs
            }
            
            print("Post data to be saved:", post_data)
            print("Authenticated user:", user.username, user.email)
            
            # Create the post using the serializer
            serializer = PostSerializer(data=post_data, context={'request': request})
            
            if serializer.is_valid():
                # Save the post
                post = serializer.save()
                print("Post created successfully with ID:", post.id)
                
                # Return success response with post data
                return Response({
                    'message': 'Post created successfully',
                    'post': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)
                return Response({
                    'error': 'Invalid post data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("Error creating post:", str(e))
            return Response({
                'error': f'Failed to create post: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Upvote Post View
@method_decorator(csrf_exempt, name='dispatch')
class UpvotePost(APIView):
    def post(self, request, post_id):
        try:
            print("=== UpvotePost POST request ===")
            print("Post ID:", post_id)
            
            # Get the post from the database
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'error': 'Post not found',
                    'detail': f'Post with ID {post_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Toggle upvote (if already upvoted, remove it; if not, add it)
            # For now, we'll just increment/decrement the count
            # In a real app, you'd track individual user votes
            current_upvotes = post.upvotes or 0
            
            # Check if this is a toggle (user clicking again)
            # For now, we'll implement a simple toggle logic
            # You might want to track user-specific voting state in the future
            if current_upvotes > 0:
                post.upvotes = current_upvotes - 1
                action = "removed"
            else:
                post.upvotes = current_upvotes + 1
                action = "added"
            
            post.save()
            
            print(f"Upvote {action}. New count: {post.upvotes}")
            
            return Response({
                'message': f'Upvote {action} successfully',
                'post_id': post_id,
                'new_upvotes': post.upvotes,
                'action': action
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error upvoting post:", str(e))
            return Response({
                'error': f'Failed to upvote post: {str(e)}',
                'detail': 'An error occurred while processing the upvote'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Downvote Post View
@method_decorator(csrf_exempt, name='dispatch')
class DownvotePost(APIView):
    def post(self, request, post_id):
        try:
            print("=== DownvotePost POST request ===")
            print("Post ID:", post_id)
            
            # Get the post from the database
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'error': 'Post not found',
                    'detail': f'Post with ID {post_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Toggle downvote (if already downvoted, remove it; if not, add it)
            current_downvotes = post.downvotes or 0
            
            # Check if this is a toggle (user clicking again)
            if current_downvotes > 0:
                post.downvotes = current_downvotes - 1
                action = "removed"
            else:
                post.downvotes = current_downvotes + 1
                action = "added"
            
            post.save()
            
            print(f"Downvote {action}. New count: {post.downvotes}")
            
            return Response({
                'message': f'Downvote {action} successfully',
                'post_id': post_id,
                'new_downvotes': post.downvotes,
                'action': action
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error downvoting post:", str(e))
            return Response({
                'error': f'Failed to downvote post: {str(e)}',
                'detail': 'An error occurred while processing the downvote'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Delete Post View
@method_decorator(csrf_exempt, name='dispatch')
class DeletePost(APIView):
    def delete(self, request, post_id):
        try:
            print("=== DeletePost DELETE request ===")
            print("Post ID:", post_id)

            # Get the JWT token from the cookies or Authorization header
            token = request.COOKIES.get('jwt')
            if not token:
                # Try to get token from Authorization header
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    print("JWT token found in Authorization header")
                else:
                    print("No JWT token found in cookies or Authorization header")

            if not token:
                return Response({
                    'error': 'Authentication required. Please log in.',
                    'detail': 'No JWT token found in cookies or Authorization header'
                }, status=status.HTTP_401_UNAUTHORIZED)

            try:
                # Decoding the JWT token
                payload = jwt.decode(token, 'secret', algorithms=['HS256'])
                print("JWT payload:", payload)
            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Token has expired. Please log in again.',
                    'detail': 'JWT token has expired'
                }, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                return Response({
                    'error': 'Invalid authentication token. Please log in again.',
                    'detail': f'JWT decode error: {str(e)}'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Get the authenticated user
            user = User.objects.filter(id=payload['id']).first()
            if not user:
                return Response({
                    'error': 'User not found. Please log in again.',
                    'detail': 'User ID from token not found in database'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Get the post from the database
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'error': 'Post not found',
                    'detail': f'Post with ID {post_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if the user is the owner of the post
            if post.user.id != user.id:
                return Response({
                    'error': 'Permission denied',
                    'detail': 'You can only delete your own posts'
                }, status=status.HTTP_403_FORBIDDEN)

            # Store post info for response
            post_info = {
                'id': post.id,
                'content': post.content[:100] + "..." if len(post.content) > 100 else post.content,
                'username': post.user.username,
                'created_at': post.created_at.isoformat(),
                'deleted_at': timezone.now().isoformat()
            }

            # Get associated data before deletion for cleanup logging
            associated_parties = list(post.parties.all())
            comment_count = len(post.comments) if post.comments else 0

            print(f"Deleting post {post_id} with {comment_count} comments and {len(associated_parties)} associated parties")

            # Delete the post (Django will handle cascade deletes automatically due to CASCADE on_delete)
            post.delete()

            print(f"Post {post_id} deleted successfully by user {user.username}")

            return Response({
                'message': 'Post deleted successfully',
                'post': post_info,
                'cleanup_info': {
                    'comments_removed': comment_count,
                    'parties_disassociated': len(associated_parties)
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error deleting post:", str(e))
            return Response({
                'error': f'Failed to delete post: {str(e)}',
                'detail': 'An error occurred while deleting the post'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Comment Post View
@method_decorator(csrf_exempt, name='dispatch')
class CommentPost(APIView):
    def post(self, request, post_id):
        try:
            print("=== CommentPost POST request ===")
            print("Post ID:", post_id)
            print("Request data:", request.data)
            
            # Get the JWT token from the cookies or Authorization header
            token = request.COOKIES.get('jwt')
            if not token:
                # Try to get token from Authorization header
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    print("JWT token found in Authorization header")
                else:
                    print("No JWT token found in cookies or Authorization header")
            
            if not token:
                return Response({
                    'error': 'Authentication required. Please log in.',
                    'detail': 'No JWT token found in cookies or Authorization header'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                # Decoding the JWT token
                payload = jwt.decode(token, 'secret', algorithms=['HS256'])
                print("JWT payload:", payload)
            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Token has expired. Please log in again.',
                    'detail': 'JWT token has expired'
                }, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                return Response({
                    'error': 'Invalid authentication token. Please log in again.',
                    'detail': f'JWT decode error: {str(e)}'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get the authenticated user
            user = User.objects.filter(id=payload['id']).first()
            if not user:
                return Response({
                    'error': 'User not found. Please log in again.',
                    'detail': 'User ID from token not found in database'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Get the post from the database
            try:
                post = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({
                    'error': 'Post not found',
                    'detail': f'Post with ID {post_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get comment data from request
            comment_text = request.data.get('comment', '').strip()
            if not comment_text:
                return Response({
                    'error': 'Comment text is required',
                    'detail': 'Comment cannot be empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create comment object
            comment = {
                'id': f"comment_{post_id}_{int(datetime.datetime.now().timestamp())}",  # Generate unique comment ID
                'user_id': user.id,
                'username': user.username,
                'user_email': user.email,
                'profile_picture': user.profile_picture,
                'full_name': user.full_name or user.username,
                'text': comment_text,
                'post_id': post_id,
                'timestamp': datetime.datetime.now().isoformat(),
                'created_at': datetime.datetime.now().isoformat()
            }
            
            # Get existing comments or initialize empty list
            existing_comments = post.comments or []
            
            # Add new comment to the list
            existing_comments.append(comment)
            
            # Update the post with new comments
            post.comments = existing_comments
            
            # Update comment count (this is the length of comments array)
            # Note: We're using the comments array length as the count
            # You might want to add a separate comment_count field in the future
            
            # Save the post
            post.save()
            
            print(f"Comment added successfully. Total comments: {len(existing_comments)}")
            
            return Response({
                'message': 'Comment added successfully',
                'comment': comment,
                'post_id': post_id,
                'total_comments': len(existing_comments)
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print("Error adding comment:", str(e))
            return Response({
                'error': f'Failed to add comment: {str(e)}',
                'detail': 'An error occurred while processing the comment'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get All Users View
@method_decorator(csrf_exempt, name='dispatch')
class GetAllUsers(APIView):
    def get(self, request):
        try:
            # print("=== GetAllUsers GET request ===")
            # print("Request method:", request.method)
            # print("Request path:", request.path)
            
            # Get only users where candidate=True from the database, ordered by newest first
            users = User.objects.filter(candidate=True).order_by('-date_joined')
            print(f"Found {users.count()} candidates in database")
            
            # Serialize the users
            serializer = UserSerializer(users, many=True)
            # print("Users serialized successfully")
            
            # Return the users data
            return Response({
                'message': 'Users fetched successfully',
                'users': serializer.data,
                'count': users.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching users:", str(e))
            return Response({
                'error': f'Failed to fetch users: {str(e)}',
                'detail': 'An error occurred while retrieving users from the database'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get All Posts View
@method_decorator(csrf_exempt, name='dispatch')
class GetAllPosts(APIView):
    def get(self, request):
        try:
            print("=== GetAllPosts GET request ===")
            print("Request method:", request.method)
            print("Request path:", request.path)

            # Get pagination parameters
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 5))  # Changed to 5 to match frontend
            print(f"Pagination: page={page}, limit={limit}")

            # Calculate offset
            offset = (page - 1) * limit

            # Get total count
            total_posts = Post.objects.count()
            print(f"Total posts in database: {total_posts}")

            # Get paginated posts from the database, ordered by newest first
            posts = Post.objects.all().order_by('-created_at')[offset:offset + limit]
            posts_count = posts.count()
            print(f"Retrieved {posts_count} posts for page {page}")

            # Check if there are more pages
            has_next = (offset + limit) < total_posts
            has_previous = page > 1

            print(f"Pagination info: has_next={has_next}, has_previous={has_previous}")

            # Serialize the posts
            serializer = PostSerializer(posts, many=True)
            print("Posts serialized successfully")

            # Return the posts data with pagination info
            return Response({
                'message': 'Posts fetched successfully',
                'posts': serializer.data,
                'count': posts_count,
                'total': total_posts,
                'page': page,
                'limit': limit,
                'has_next': has_next,
                'has_previous': has_previous,
                'next': f"?page={page + 1}&limit={limit}" if has_next else None,
                'previous': f"?page={page - 1}&limit={limit}" if has_previous else None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error fetching posts:", str(e))
            return Response({
                'error': f'Failed to fetch posts: {str(e)}',
                'detail': 'An error occurred while retrieving posts from the database'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get My Posts View (authenticated user's non-anonymous posts only)
@method_decorator(csrf_exempt, name='dispatch')
class GetMyPosts(APIView):
    def get(self, request):
        try:
            token = request.COOKIES.get('jwt')
            if not token:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                else:
                    return Response({
                        'error': 'Authentication required',
                        'detail': 'No JWT token found in cookies or Authorization header'
                    }, status=status.HTTP_401_UNAUTHORIZED)

            try:
                payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                return Response({
                    'error': 'Token has expired. Please log in again.',
                    'detail': 'JWT token has expired'
                }, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                return Response({
                    'error': 'Invalid authentication token.',
                    'detail': f'JWT decode error: {str(e)}'
                }, status=status.HTTP_401_UNAUTHORIZED)

            user = User.objects.filter(id=payload['id']).first()
            if not user:
                return Response({
                    'error': 'User not found. Please log in again.',
                    'detail': 'User ID from token not found in database'
                }, status=status.HTTP_401_UNAUTHORIZED)

            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 5))
            offset = (page - 1) * limit

            queryset = Post.objects.filter(user=user, is_anonymous=False).order_by('-created_at')
            total_posts = queryset.count()
            posts = queryset[offset:offset + limit]
            posts_count = posts.count()

            has_next = (offset + limit) < total_posts
            has_previous = page > 1

            serializer = PostSerializer(posts, many=True)

            return Response({
                'message': 'Posts fetched successfully',
                'posts': serializer.data,
                'count': posts_count,
                'total': total_posts,
                'page': page,
                'limit': limit,
                'has_next': has_next,
                'has_previous': has_previous,
                'next': f"?page={page + 1}&limit={limit}" if has_next else None,
                'previous': f"?page={page - 1}&limit={limit}" if has_previous else None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error fetching my posts:", str(e))
            return Response({
                'error': f'Failed to fetch posts: {str(e)}',
                'detail': 'An error occurred while retrieving posts from the database'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get User Profile By ID View (public profile for any user)
@method_decorator(csrf_exempt, name='dispatch')
class GetUserProfileById(APIView):
    def get(self, request, user_id):
        try:
            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({
                    'error': 'User not found',
                    'detail': f'No user with id {user_id}'
                }, status=status.HTTP_404_NOT_FOUND)
            serializer = UserSerializer(user)
            data = dict(serializer.data)
            data.pop('password', None)
            data.pop('email', None)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print("Error fetching user profile:", str(e))
            return Response({
                'error': f'Failed to fetch user profile: {str(e)}',
                'detail': 'An error occurred while retrieving the user profile'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get User Posts View (public non-anonymous posts by user_id)
@method_decorator(csrf_exempt, name='dispatch')
class GetUserPosts(APIView):
    def get(self, request, user_id):
        try:
            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({
                    'error': 'User not found',
                    'detail': f'No user with id {user_id}'
                }, status=status.HTTP_404_NOT_FOUND)
            page = int(request.GET.get('page', 1))
            limit = int(request.GET.get('limit', 5))
            offset = (page - 1) * limit
            queryset = Post.objects.filter(user=user, is_anonymous=False).order_by('-created_at')
            total_posts = queryset.count()
            posts = queryset[offset:offset + limit]
            posts_count = posts.count()
            has_next = (offset + limit) < total_posts
            has_previous = page > 1
            serializer = PostSerializer(posts, many=True)
            return Response({
                'message': 'Posts fetched successfully',
                'posts': serializer.data,
                'count': posts_count,
                'total': total_posts,
                'page': page,
                'limit': limit,
                'has_next': has_next,
                'has_previous': has_previous,
                'next': f"?page={page + 1}&limit={limit}" if has_next else None,
                'previous': f"?page={page - 1}&limit={limit}" if has_previous else None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print("Error fetching user posts:", str(e))
            return Response({
                'error': f'Failed to fetch user posts: {str(e)}',
                'detail': 'An error occurred while retrieving posts'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get All Parties View
@method_decorator(csrf_exempt, name='dispatch')
class GetAllParties(APIView):
    def get(self, request):
        try:
            # print("=== GetAllParties GET request ===")
            # print("Request method:", request.method)
            # print("Request path:", request.path)
            
            # Get all parties from the database, ordered by votes (highest first) then by party name
            parties = Parties.objects.all().order_by('-votes', 'party_name')
            # print(f"Found {parties.count()} parties in database")
            
            # Serialize the parties
            serializer = PartiesSerializer(parties, many=True)
            # print("Parties serialized successfully")
            
            # Return the parties data
            return Response({
                'message': 'Parties fetched successfully',
                'parties': serializer.data,
                'count': parties.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching parties:", str(e))
            return Response({
                'error': f'Failed to fetch parties: {str(e)}',
                'detail': 'An error occurred while retrieving parties from the database'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Register Party View
@method_decorator(csrf_exempt, name='dispatch')
class RegisterParty(APIView):
    def post(self, request):
        try:
            print("=== RegisterParty POST request ===")
            print("Request data:", request.data)
            
            # Validate required fields
            party_name = request.data.get('party_name', '').strip()
            if not party_name:
                return Response({
                    'error': 'Party name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if party name already exists
            if Parties.objects.filter(party_name__iexact=party_name).exists():
                return Response({
                    'error': 'A party with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Serialize and validate the data
            serializer = PartiesSerializer(data=request.data)
            
            if serializer.is_valid():
                # Save the party
                party = serializer.save()
                print(f"Party '{party.party_name}' registered successfully with ID: {party.id}")
                
                # Return success response with party data
                return Response({
                    'message': 'Party registered successfully',
                    'party': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)
                return Response({
                    'error': 'Invalid party data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("Error registering party:", str(e))
            return Response({
                'error': f'Failed to register party: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Register Candidate View
@method_decorator(csrf_exempt, name='dispatch')
class RegisterCandidate(APIView):
    def post(self, request):
        try:
            print("=== RegisterCandidate POST request ===")
            print("Request data:", request.data)
            
            # Validate required fields
            candidate_name = request.data.get('candidate_name', '').strip()
            if not candidate_name:
                return Response({
                    'error': 'Candidate name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if candidate name already exists in the same department
            department = request.data.get('department', '').strip()
            if department and Candidates.objects.filter(
                candidate_name__iexact=candidate_name, 
                department__iexact=department
            ).exists():
                return Response({
                    'error': f'A candidate with this name already exists for the {department} position'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif not department and Candidates.objects.filter(candidate_name__iexact=candidate_name).exists():
                return Response({
                    'error': 'A candidate with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Serialize and validate the data
            serializer = CandidatesSerializer(data=request.data)
            
            if serializer.is_valid():
                # Save the candidate
                candidate = serializer.save()
                print(f"Candidate '{candidate.candidate_name}' registered successfully with ID: {candidate.id}")
                
                # Return success response with candidate data
                return Response({
                    'message': 'Candidate registered successfully',
                    'candidate': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                print("Serializer errors:", serializer.errors)
                return Response({
                    'error': 'Invalid candidate data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print("Error registering candidate:", str(e))
            return Response({
                'error': f'Failed to register candidate: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get All Candidates View
@method_decorator(csrf_exempt, name='dispatch')
class GetAllCandidates(APIView):
    def get(self, request):
        try:
            # print("=== GetAllCandidates GET request ===")
            # print("Request method:", request.method)
            # print("Request path:", request.path)
            
            # Get all candidates from the database, ordered by votes (highest first) then by name
            candidates = Candidates.objects.all().order_by('-votes', 'candidate_name')
            # print(f"Found {candidates.count()} candidates in database")
            
            # Serialize the candidates
            serializer = CandidatesSerializer(candidates, many=True)
            print("Candidates serialized successfully")
            
            # Return the candidates data
            return Response({
                'message': 'Candidates fetched successfully',
                'candidates': serializer.data,
                'count': candidates.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching candidates:", str(e))
            return Response({
                'error': f'Failed to fetch candidates: {str(e)}',
                'detail': 'An error occurred while retrieving candidates from the database'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get User Statistics View
@method_decorator(csrf_exempt, name='dispatch')
class GetUserStats(APIView):
    def get(self, request):
        try:
            print("=== GetUserStats GET request ===")
            print("Request method:", request.method)
            print("Request path:", request.path)
            
            # Get total users count
            total_users = User.objects.count()
            print(f"Total users: {total_users}")
            
            # Calculate growth percentage (comparing current month vs previous month)
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            # Start of current month
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Start of previous month
            if current_month_start.month == 1:
                previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
            else:
                previous_month_start = current_month_start.replace(month=current_month_start.month - 1)
            
            # Count users joined in current month
            current_month_users = User.objects.filter(
                date_joined__gte=current_month_start,
                date_joined__lte=now
            ).count()
            
            # Count users joined in previous month
            previous_month_users = User.objects.filter(
                date_joined__gte=previous_month_start,
                date_joined__lt=current_month_start
            ).count()
            
            # Calculate growth percentage
            if previous_month_users > 0:
                growth_percentage = ((current_month_users - previous_month_users) / previous_month_users) * 100
            else:
                # If no users in previous month, consider current month users as 100% growth
                growth_percentage = 100.0 if current_month_users > 0 else 0.0
            
            # Round to 1 decimal place
            growth_percentage = round(growth_percentage, 1)
            
            print(f"Current month users: {current_month_users}")
            print(f"Previous month users: {previous_month_users}")
            print(f"Growth percentage: {growth_percentage}%")
            
            # Return the user statistics
            return Response({
                'message': 'User statistics fetched successfully',
                'total_users': total_users,
                'current_month_users': current_month_users,
                'previous_month_users': previous_month_users,
                'growth_percentage': growth_percentage,
                'growth_direction': 'up' if growth_percentage >= 0 else 'down'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching user statistics:", str(e))
            return Response({
                'error': f'Failed to fetch user statistics: {str(e)}',
                'detail': 'An error occurred while calculating user statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get Party Statistics View
@method_decorator(csrf_exempt, name='dispatch')
class GetPartyStats(APIView):
    def get(self, request):
        try:
            print("=== GetPartyStats GET request ===")
            print("Request method:", request.method)
            print("Request path:", request.path)
            
            # Get total parties count
            total_parties = Parties.objects.count()
            print(f"Total parties: {total_parties}")
            
            # Calculate growth percentage (comparing current month vs previous month)
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            # Start of current month
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Start of previous month
            if current_month_start.month == 1:
                previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
            else:
                previous_month_start = current_month_start.replace(month=current_month_start.month - 1)
            
            # Count parties registered in current month
            current_month_parties = Parties.objects.filter(
                id__gte=1  # Since Parties model doesn't have date_joined, we'll use a simple approach
            ).count()
            
            # For now, we'll set a default growth percentage
            # In a real app, you'd track when parties were created
            growth_percentage = 12.5  # Default value
            
            print(f"Current month parties: {current_month_parties}")
            print(f"Growth percentage: {growth_percentage}%")
            
            # Return the party statistics
            return Response({
                'message': 'Party statistics fetched successfully',
                'total_parties': total_parties,
                'growth_percentage': growth_percentage,
                'growth_direction': 'up'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching party statistics:", str(e))
            return Response({
                'error': f'Failed to fetch party statistics: {str(e)}',
                'detail': 'An error occurred while calculating party statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get Candidate Statistics View
@method_decorator(csrf_exempt, name='dispatch')
class GetCandidateStats(APIView):
    def get(self, request):
        try:
            print("=== GetCandidateStats GET request ===")
            print("Request method:", request.method)
            print("Request path:", request.path)
            
            # Get total candidates count
            total_candidates = Candidates.objects.count()
            print(f"Total candidates: {total_candidates}")
            
            # Calculate growth percentage (comparing current month vs previous month)
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            # Start of current month
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Start of previous month
            if current_month_start.month == 1:
                previous_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
            else:
                previous_month_start = current_month_start.replace(month=current_month_start.month - 1)
            
            # Count candidates registered in current month
            current_month_candidates = Candidates.objects.filter(
                id__gte=1  # Since Candidates model doesn't have date_joined, we'll use a simple approach
            ).count()
            
            # For now, we'll set a default growth percentage
            # In a real app, you'd track when candidates were created
            growth_percentage = 4.5  # Default value
            
            print(f"Current month candidates: {current_month_candidates}")
            print(f"Growth percentage: {growth_percentage}%")
            
            # Return the candidate statistics
            return Response({
                'message': 'Candidate statistics fetched successfully',
                'total_candidates': total_candidates,
                'growth_percentage': growth_percentage,
                'growth_direction': 'up'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Error fetching candidate statistics:", str(e))
            return Response({
                'error': f'Failed to fetch candidate statistics: {str(e)}',
                'detail': 'An error occurred while calculating candidate statistics'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Track App Impressions View
@method_decorator(csrf_exempt, name='dispatch')
class TrackImpressions(APIView):
    """
    View to track app impressions. This endpoint should be called every time
    a user accesses the app (both logged in and not logged in users).
    It increments the impression count for the current date.
    """
    def post(self, request):
        try:
            print("=== TrackImpressions POST request ===")

            # Get today's date
            today = timezone.now().date()
            print(f"Tracking impressions for date: {today}")

            # Try to get the existing record for today, or create a new one
            impression_record, created = DailyImpressions.objects.get_or_create(
                date=today,
                defaults={'impressions': 0}
            )

            # Increment the impressions count
            impression_record.impressions += 1
            impression_record.save()

            print(f"Impressions for {today}: {impression_record.impressions} (created: {created})")

            # Return success response
            return Response({
                'message': 'Impression tracked successfully',
                'date': today.isoformat(),
                'impressions_today': impression_record.impressions,
                'is_new_day': created
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error tracking impression:", str(e))
            return Response({
                'error': f'Failed to track impression: {str(e)}',
                'detail': 'An error occurred while tracking the app impression'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Search Posts View
@method_decorator(csrf_exempt, name='dispatch')
class SearchPosts(APIView):
    """
    View to search posts by content, username, or other criteria.
    Supports partial matching and case-insensitive search.
    """
    def get(self, request):
        try:
            print("=== SearchPosts GET request ===")

            # Get search query parameter
            query = request.GET.get('q', '').strip()
            if not query:
                return Response({
                    'error': 'Search query is required',
                    'detail': 'Please provide a search term using the "q" parameter'
                }, status=status.HTTP_400_BAD_REQUEST)

            print(f"Searching for: '{query}'")

            # Search posts by content (case-insensitive partial match)
            posts_content = Post.objects.filter(content__icontains=query)

            # Search posts by username in user_data JSON field
            posts_username = Post.objects.filter(user_data__username__icontains=query)

            # Search posts by user's actual username (for non-anonymous posts)
            posts_user = Post.objects.filter(
                user__username__icontains=query,
                is_anonymous=False
            )

            # Combine all search results using Q objects to avoid union issues
            from django.db.models import Q
            combined_query = Q(content__icontains=query) | \
                           Q(user_data__username__icontains=query) | \
                           Q(user__username__icontains=query, is_anonymous=False)

            all_posts = Post.objects.filter(combined_query)

            # Order by newest first
            posts = all_posts.order_by('-created_at')

            print(f"Found {posts.count()} posts matching search query")

            # Serialize the posts
            serializer = PostSerializer(posts, many=True)
            print("Posts serialized successfully")

            # Return the search results
            return Response({
                'message': f'Found {posts.count()} posts matching "{query}"',
                'posts': serializer.data,
                'count': posts.count(),
                'query': query
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error searching posts:", str(e))
            return Response({
                'error': f'Failed to search posts: {str(e)}',
                'detail': 'An error occurred while searching posts'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Get Impressions Statistics View
@method_decorator(csrf_exempt, name='dispatch')
class GetImpressionsStats(APIView):
    """
    View to get impressions statistics. Returns total impressions and daily breakdown.
    """
    def get(self, request):
        try:
            print("=== GetImpressionsStats GET request ===")

            # Get all impression records ordered by date (newest first)
            impressions = DailyImpressions.objects.all().order_by('date')

            # Calculate total impressions
            total_impressions = DailyImpressions.objects.aggregate(
                total=models.Sum('impressions')
            )['total'] or 0

            # Get today's impressions
            today = timezone.now().date()
            today_impressions = 0
            try:
                today_record = DailyImpressions.objects.get(date=today)
                today_impressions = today_record.impressions
            except DailyImpressions.DoesNotExist:
                pass

            # Serialize the impressions data
            impressions_data = []
            for impression in impressions:
                impressions_data.append({
                    'date': impression.date.isoformat(),
                    'impressions': impression.impressions,
                    'created_at': impression.created_at.isoformat(),
                    'updated_at': impression.updated_at.isoformat()
                })

            print(f"Total impressions: {total_impressions}, Today's impressions: {today_impressions}")

            # Return success response
            return Response({
                'message': 'Impressions statistics fetched successfully',
                'total_impressions': total_impressions,
                'today_impressions': today_impressions,
                'daily_impressions': impressions_data,
                'count': impressions.count()
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print("Error fetching impressions statistics:", str(e))
            return Response({
                'error': f'Failed to fetch impressions statistics: {str(e)}',
                'detail': 'An error occurred while retrieving impressions data'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Update Party View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateParty(APIView):
    def post(self, request, party_id):
        try:
            print("=== UpdateParty POST request ===")
            print("Party ID:", party_id)
            print("Request data:", request.data)

            # Get the party from the database
            try:
                party = Parties.objects.get(id=party_id)
            except Parties.DoesNotExist:
                return Response({
                    'error': 'Party not found',
                    'detail': f'Party with ID {party_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)

            # Validate required fields
            party_name = request.data.get('party_name', '').strip()
            if not party_name:
                return Response({
                    'error': 'Party name is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if party name already exists (excluding current party)
            if Parties.objects.filter(party_name__iexact=party_name).exclude(id=party_id).exists():
                return Response({
                    'error': 'A party with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Update party fields
            serializer = PartiesSerializer(party, data=request.data, partial=True)

            if serializer.is_valid():
                # Save the updated party
                updated_party = serializer.save()
                print(f"Party '{updated_party.party_name}' updated successfully with ID: {updated_party.id}")

                # Return success response with updated party data
                return Response({
                    'message': 'Party updated successfully',
                    'party': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                print("Serializer errors:", serializer.errors)
                return Response({
                    'error': 'Invalid party data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print("Error updating party:", str(e))
            return Response({
                'error': f'Failed to update party: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Update Candidate View
@method_decorator(csrf_exempt, name='dispatch')
class UpdateCandidate(APIView):
    def post(self, request, candidate_id):
        try:
            print("=== UpdateCandidate POST request ===")
            print("Candidate ID:", candidate_id)
            print("Request data:", request.data)

            # Get the candidate from the database
            try:
                candidate = Candidates.objects.get(id=candidate_id)
            except Candidates.DoesNotExist:
                return Response({
                    'error': 'Candidate not found',
                    'detail': f'Candidate with ID {candidate_id} does not exist'
                }, status=status.HTTP_404_NOT_FOUND)

            # Validate required fields
            candidate_name = request.data.get('candidate_name', '').strip()
            if not candidate_name:
                return Response({
                    'error': 'Candidate name is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if candidate name already exists in the same department (excluding current candidate)
            department = request.data.get('department', '').strip()
            if department and Candidates.objects.filter(
                candidate_name__iexact=candidate_name,
                department__iexact=department
            ).exclude(id=candidate_id).exists():
                return Response({
                    'error': f'A candidate with this name already exists for the {department} position'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif not department and Candidates.objects.filter(candidate_name__iexact=candidate_name).exclude(id=candidate_id).exists():
                return Response({
                    'error': 'A candidate with this name already exists'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Update candidate fields
            serializer = CandidatesSerializer(candidate, data=request.data, partial=True)

            if serializer.is_valid():
                # Save the updated candidate
                updated_candidate = serializer.save()
                print(f"Candidate '{updated_candidate.candidate_name}' updated successfully with ID: {updated_candidate.id}")

                # Return success response with updated candidate data
                return Response({
                    'message': 'Candidate updated successfully',
                    'candidate': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                print("Serializer errors:", serializer.errors)
                return Response({
                    'error': 'Invalid candidate data',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print("Error updating candidate:", str(e))
            return Response({
                'error': f'Failed to update candidate: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

