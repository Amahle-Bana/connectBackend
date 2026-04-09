from rest_framework import serializers
from .models import User, Post, Parties, Candidates


# User Serializer
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        # Model to serialize
        model = User
        # Fields to serialize - matching the actual User model fields
        fields = [
            'id', 'username', 'email', 'password', 'full_name', 'candidate', 'structure',
            'created_at', 'updated_at', 'profile_picture', 'bio', 'privacy_settings',
            'user_facebook', 'user_instagram', 'user_x_twitter', 'user_threads',
            'user_youtube', 'user_linkedin', 'user_tiktok',
            # Django's AbstractUser fields that are inherited
            'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined', 'last_login',
            'is_email_verified',
        ]
        # Extra kwargs
        extra_kwargs = {
            # Password field is write only
            'password': {'write_only': True},
            'is_email_verified': {'read_only': True},
        }

    def create(self, validated_data):
        # Get the password from the validated data
        password = validated_data.pop('password', None)
        # Create a new user instance
        instance = self.Meta.model(**validated_data)
        # If the password is not None, set the password
        if password is not None:
            # Set the password (this will hash it)
            instance.set_password(password)
        # Save the user
        instance.save()
        # Return the user
        return instance


# Post Serializer
class PostSerializer(serializers.ModelSerializer):
    # Include user details in the response
    user = UserSerializer(read_only=True)
    # Include the username for easy access
    username = serializers.CharField(source='user.username', read_only=True)
    # Include the profile picture for easy access
    profile_picture = serializers.CharField(source='user.profile_picture', read_only=True)
    # Include parties information
    parties = serializers.SerializerMethodField()
    # Allow parties to be set by ID during creation
    parties_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Post
        fields = [
            'id', 'user', 'username', 'profile_picture', 'content', 'images', 'videos',
            'is_anonymous', 'user_data', 'created_at', 'updated_at', 'upvotes', 'downvotes', 'comments', 'parties', 'parties_ids'
        ]
        read_only_fields = ['id', 'user', 'username', 'profile_picture', 'created_at', 'updated_at', 'upvotes', 'downvotes', 'comments', 'parties']
    
    def create(self, validated_data):
        # Extract parties_ids before creating the post
        parties_ids = validated_data.pop('parties_ids', [])

        # Get the user from the context (set in the view)
        user = self.context['request'].user
        validated_data['user'] = user

        # If user_data is not provided, create it from the authenticated user
        if 'user_data' not in validated_data or not validated_data['user_data']:
            validated_data['user_data'] = {
                'username': user.username,
                'email': user.email,
                'fullName': user.full_name,
                'profilePicture': user.profile_picture
            }

        # Create the post
        post = super().create(validated_data)

        # Set the parties if any were provided
        if parties_ids:
            parties = Parties.objects.filter(id__in=parties_ids)
            post.parties.set(parties)

        return post

    def get_parties(self, obj):
        """Get parties data for the post"""
        parties_data = []
        for party in obj.parties.all():
            parties_data.append({
                'id': party.id,
                'party_name': party.party_name,
                'manifesto': party.manifesto,
                'votes': party.votes,
                'logo': party.logo
            })
        return parties_data


# Parties Serializer
class PartiesSerializer(serializers.ModelSerializer):
    # Calculate supporters count from the supporters JSON field
    supporters_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Parties
        fields = [
            'id', 'party_name', 'manifesto', 'votes', 'supporters', 'supporters_count',
            'party_leader', 'structure', 'logo', 'website', 'facebook', 'twitter', 'instagram',
            'linkedin', 'youtube', 'tiktok', 'x', 'threads'
        ]
        read_only_fields = ['id', 'supporters_count']
    
    def get_supporters_count(self, obj):
        """Calculate the number of supporters from the supporters JSON field"""
        if obj.supporters and isinstance(obj.supporters, list):
            return len(obj.supporters)
        return 0
    
    def validate(self, data):
        """Clean empty URL fields to None to avoid validation errors"""
        url_fields = ['website', 'facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'tiktok', 'x', 'threads']
        for field in url_fields:
            if field in data and (data[field] == '' or data[field] is None):
                data[field] = None
        return data


# Candidates Serializer
class CandidatesSerializer(serializers.ModelSerializer):
    # Calculate supporters count from the supporters JSON field
    supporters_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Candidates
        fields = [
            'id', 'candidate_name', 'manifesto', 'votes', 'supporters', 'supporters_count',
            'department', 'structure', 'profile_picture', 'website', 'facebook', 'twitter', 'instagram',
            'linkedin', 'youtube', 'tiktok', 'x', 'threads'
        ]
        read_only_fields = ['id', 'supporters_count', 'votes']
    
    def get_supporters_count(self, obj):
        """Calculate the number of supporters from the supporters JSON field"""
        if obj.supporters and isinstance(obj.supporters, list):
            return len(obj.supporters)
        return 0
    
    def validate(self, data):
        """Clean empty URL fields to None to avoid validation errors"""
        url_fields = ['website', 'facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'tiktok', 'x', 'threads']
        for field in url_fields:
            if field in data and (data[field] == '' or data[field] is None):
                data[field] = None
        return data
