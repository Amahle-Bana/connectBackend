from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# Create your models here.

# User Model
class User(AbstractUser):
    # User ID
    id = models.AutoField(primary_key=True, unique=True, null=False, blank=False)
    # Username
    username = models.CharField(max_length=30, unique=True, editable=True, null=False, blank=False)
    # Full Name
    full_name = models.CharField(max_length=100, null=True, blank=True)
    # User Email
    email = models.EmailField(max_length=100, unique=True, editable=True, null=False, blank=False)
    # Email verified via OTP
    is_email_verified = models.BooleanField(default=False)
    # User Password (Hashed)
    password = models.CharField(max_length=255, null=False, blank=False, editable=True)
    # Candidate
    candidate = models.BooleanField(default=False)
    # Candidate Votes
    votes = models.PositiveIntegerField(default=0, null=True, blank=True)
    # Campus Structure
    structure = models.CharField(max_length=100, null=True, blank=True)
    # User Details Created At
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False, editable=False)
    # User Details Updated At
    updated_at = models.DateTimeField(auto_now=True, null=False, blank=False, editable=False)
    # Profile Picture
    profile_picture = models.TextField(null=True, blank=True)

    # Bio
    bio = models.TextField(null=True, blank=True)

    # Privacy Settings (Public/Private)
    PRIVACY_CHOICES = [
        ("Public", "Public"),
        ("Private", "Private"),
    ]
    privacy_settings = models.CharField(max_length=7, choices=PRIVACY_CHOICES, default="Public")

    # SOCIAL MEDIA LINKS
    user_facebook = models.URLField(max_length=255, null=True, blank=True)
    user_instagram = models.TextField(max_length=255, null=True, blank=True)
    user_x_twitter = models.TextField(max_length=255, null=True, blank=True)
    user_threads = models.TextField(max_length=255, null=True, blank=True)
    user_youtube = models.URLField(max_length=255, null=True, blank=True)
    user_linkedin = models.URLField(max_length=255, null=True, blank=True)
    user_tiktok = models.TextField(max_length=255, null=True, blank=True)

    # Used for authentication in place of username
    USERNAME_FIELD = 'email'

    # SUPERUSER REQUIRED FIELDS
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.username


# Post Model
class Post(models.Model):
    # Post ID
    id = models.AutoField(primary_key=True, unique=True, null=False, blank=False)
    # User who created the post (foreign key to User model)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    # Post content/text
    content = models.TextField(max_length=500, null=False, blank=False)
    # Images (stored as JSON array of base64 strings or file paths)
    images = models.JSONField(default=list, null=True, blank=True)
    # Videos (stored as JSON array of base64 strings or file paths)
    videos = models.JSONField(default=list, null=True, blank=True)
    # Anonymous post flag
    is_anonymous = models.BooleanField(default=False)
    # User data at time of post creation (for historical record)
    user_data = models.JSONField(default=dict, null=True, blank=True)
    # Post created at
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False, editable=False)
    # Post updated at
    updated_at = models.DateTimeField(auto_now=True, null=False, blank=False, editable=False)
    # Upvotes count
    upvotes = models.PositiveIntegerField(default=0, null=False, blank=False)
    # Downvotes count
    downvotes = models.PositiveIntegerField(default=0, null=False, blank=False)
    # Comments count
    comments = models.JSONField(default=list, null=True, blank=True)
    # Associated parties (many-to-many relationship)
    parties = models.ManyToManyField('Parties', related_name='posts', blank=True)

    class Meta:
        ordering = ['-created_at']  # Order by newest first
    
    def __str__(self):
        return f"Post by {self.user.username if not self.is_anonymous else 'Anonymous'} - {self.content[:50]}..."



class Parties(models.Model):
    # Parties ID
    id = models.AutoField(primary_key=True, unique=True, null=False, blank=False)
    # Parties Name
    party_name = models.CharField(max_length=100, null=False, blank=False)
    # Bio
    manifesto = models.TextField(null=True, blank=True)
    # Votes
    votes = models.PositiveIntegerField(default=0, null=False, blank=False)
    # Supporters
    supporters = models.JSONField(default=list, null=True, blank=True)
    # Party Leader
    party_leader = models.CharField(max_length=100, null=True, blank=True)
    # Department/Structure
    structure = models.CharField(max_length=100, null=True, blank=True)
    # Parties and Candidates Logo
    logo = models.TextField(null=True, blank=True)
    # Parties and Candidates Website
    website = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates Facebook
    facebook = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates Twitter
    twitter = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates Instagram
    instagram = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates LinkedIn
    linkedin = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates YouTube
    youtube = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates TikTok
    tiktok = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates X (Twitter)
    x = models.URLField(max_length=255, null=True, blank=True)
    # Parties and Candidates Threads
    threads = models.URLField(max_length=255, null=True, blank=True)



class Candidates(models.Model):
    # Candidates ID
    id = models.AutoField(primary_key=True, unique=True, null=False, blank=False)
    # Candidates Name
    candidate_name = models.CharField(max_length=100, null=False, blank=False)
    # Bio
    manifesto = models.TextField(null=True, blank=True)
    # Votes
    votes = models.PositiveIntegerField(default=0, null=False, blank=False)
    # Supporters
    supporters = models.JSONField(default=list, null=True, blank=True)
    # Department
    department = models.CharField(max_length=100, null=True, blank=True)
    # Structure
    structure = models.CharField(max_length=100, null=True, blank=True)
    # Candidate Logo
    profile_picture = models.TextField(null=True, blank=True)
    # Candidate Website
    website = models.URLField(max_length=255, null=True, blank=True)
    # Candidate Facebook
    facebook = models.URLField(max_length=255, null=True, blank=True)
    # Candidate Twitter
    twitter = models.URLField(max_length=255, null=True, blank=True)
    # Candidate Instagram
    instagram = models.URLField(max_length=255, null=True, blank=True)
    # Candidate LinkedIn
    linkedin = models.URLField(max_length=255, null=True, blank=True)
    # Candidate YouTube
    youtube = models.URLField(max_length=255, null=True, blank=True)
    # Candidate TikTok
    tiktok = models.URLField(max_length=255, null=True, blank=True)
    # Candidate X (Twitter)
    x = models.URLField(max_length=255, null=True, blank=True)
    # Candidate Threads
    threads = models.URLField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.candidate_name


# Daily Impressions Model
class DailyImpressions(models.Model):
    # Date for the impressions
    date = models.DateField(unique=True, null=False, blank=False, default=timezone.now)
    # Number of impressions for this date
    impressions = models.PositiveIntegerField(default=0, null=False, blank=False)
    # Created at timestamp
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False, editable=False)
    # Updated at timestamp
    updated_at = models.DateTimeField(auto_now=True, null=False, blank=False, editable=False)

    class Meta:
        ordering = ['-date']  # Order by newest date first
        verbose_name = 'Daily Impression'
        verbose_name_plural = 'Daily Impressions'

    def __str__(self):
        return f"Impressions for {self.date}: {self.impressions}"


# OTP Model for email verification
class OTP(models.Model):
    # OTP ID
    id = models.AutoField(primary_key=True, unique=True, null=False, blank=False)
    # Email address associated with the OTP
    email = models.EmailField(max_length=100, null=False, blank=False)
    # OTP code (6 digits)
    otp_code = models.CharField(max_length=6, null=False, blank=False)
    # OTP created at
    created_at = models.DateTimeField(auto_now_add=True, null=False, blank=False, editable=False)
    # OTP expires at (10 minutes from creation)
    expires_at = models.DateTimeField(null=False, blank=False)
    # Whether the OTP has been used
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.email}: {self.otp_code}"

    def is_expired(self):
        """Check if the OTP has expired"""
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        """Override save to set expiration time"""
        if not self.expires_at:
            # Set expiration to 10 minutes from now
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)