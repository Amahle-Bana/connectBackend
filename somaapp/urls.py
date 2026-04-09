from django.urls import path
from somaapp.views import SignUpUser, LoginUser, UserView, LogoutView, CheckUsernameAvailability, ResetPasswordRequest, ResetPasswordConfirm, ImportantDetails, VerifyLogin, VerifySignup, CleanupSignup, VerifyOTP, UpdateProfilePicture, UpdateUserProfile, UpdateNotificationSettings, UpdateContentPreferences, UpdatePrivacySettings, CheckExistingUserData, CreatePost, GetAllUsers, GetAllPosts, GetMyPosts, GetUserProfileById, GetUserPosts, UpvotePost, DownvotePost, DeletePost, CommentPost, GetAllParties, RegisterParty, RegisterCandidate, GetAllCandidates, GetUserStats, GetPartyStats, GetCandidateStats, TrackImpressions, GetImpressionsStats, UpdateParty, UpdateCandidate, SearchPosts


#  Somaapp URL patterns
urlpatterns = [
    # Check Existing User Data URL
    path('check-existing-user/', CheckExistingUserData.as_view(), name='check-existing-user'),
    # Register User URL
    path('signup/', SignUpUser.as_view(), name='signup'),
    # Login User URL
    path('login/', LoginUser.as_view(), name='login'),
    # User URL
    path('user/', UserView.as_view(), name='user'),
    # Logout User URL
    path('logout/', LogoutView.as_view(), name='logout'),
    # Check Username Availability URL
    path('check-username/', CheckUsernameAvailability.as_view(), name='check-username'),
    # Reset Password Request URL
    path('reset-password-request/', ResetPasswordRequest.as_view(), name='reset-password-request'),
    # Reset Password Confirmation URL
    path('reset-password-confirm/', ResetPasswordConfirm.as_view(), name='reset-password-confirm'),
    # Update User Details URL
    path('important-details/', ImportantDetails.as_view(), name='important-details'),
    # Verify Login URL
    path('verify-login/', VerifyLogin.as_view(), name='verify-login'),
    # Verify Signup URL
    path('verify-signup/', VerifySignup.as_view(), name='verify-signup'),
    # Cleanup Signup URL
    path('cleanup-signup/', CleanupSignup.as_view(), name='cleanup-signup'),
    # Verify OTP URL
    path('verify-otp/', VerifyOTP.as_view(), name='verify-otp'),
    # Update Profile Picture URL
    path('update-profile-picture/', UpdateProfilePicture.as_view(), name='update-profile-picture'),
    # Update User Profile URL
    path('update-profile/', UpdateUserProfile.as_view(), name='update-profile'),
    # Update Notification Settings URL
    path('update-notification-settings/', UpdateNotificationSettings.as_view(), name='update-notification-settings'),
    # Update Content Preferences URL
    path('update-content-preferences/', UpdateContentPreferences.as_view(), name='update-content-preferences'),
    # Update Privacy Settings URL
    path('update-privacy-settings/', UpdatePrivacySettings.as_view(), name='update-privacy-settings'),
    # Create Post URL
    path('create-post/', CreatePost.as_view(), name='create-post'),
    # Get All Users URL
    path('get-all-users/', GetAllUsers.as_view(), name='get-all-users'),
    # Get All Posts URL
    path('get-all-posts/', GetAllPosts.as_view(), name='get-all-posts'),
    # Get My Posts URL (authenticated user's non-anonymous posts)
    path('get-my-posts/', GetMyPosts.as_view(), name='get-my-posts'),
    # Get User Profile By ID URL (public profile)
    path('get-user-profile/<int:user_id>/', GetUserProfileById.as_view(), name='get-user-profile'),
    # Get User Posts URL (public posts by user_id)
    path('get-user-posts/<int:user_id>/', GetUserPosts.as_view(), name='get-user-posts'),
    # Upvote Post URL
    path('upvote-post/<int:post_id>/', UpvotePost.as_view(), name='upvote-post'),
    # Downvote Post URL
    path('downvote-post/<int:post_id>/', DownvotePost.as_view(), name='downvote-post'),
    # Delete Post URL
    path('delete-post/<int:post_id>/', DeletePost.as_view(), name='delete-post'),
    # Comment Post URL
    path('comment-post/<int:post_id>/', CommentPost.as_view(), name='comment-post'),
    # Get All Parties URL
    path('get-all-parties/', GetAllParties.as_view(), name='get-all-parties'),
    # Register Party URL
    path('register-party/', RegisterParty.as_view(), name='register-party'),
    # Register Candidate URL
    path('register-candidate/', RegisterCandidate.as_view(), name='register-candidate'),
    # Update Party URL
    path('update-party/<int:party_id>/', UpdateParty.as_view(), name='update-party'),
    # Update Candidate URL
    path('update-candidate/<int:candidate_id>/', UpdateCandidate.as_view(), name='update-candidate'),
    # Get All Candidates URL
    path('get-all-candidates/', GetAllCandidates.as_view(), name='get-all-candidates'),
    # Get User Statistics URL
    path('get-user-stats/', GetUserStats.as_view(), name='get-user-stats'),
    # Get Party Statistics URL
    path('get-party-stats/', GetPartyStats.as_view(), name='get-party-stats'),
    # Get Candidate Statistics URL
    path('get-candidate-stats/', GetCandidateStats.as_view(), name='get-candidate-stats'),
    # Track App Impressions URL
    path('track-impressions/', TrackImpressions.as_view(), name='track-impressions'),
    # Get Impressions Statistics URL
    path('get-impressions-stats/', GetImpressionsStats.as_view(), name='get-impressions-stats'),
    # Search Posts URL
    path('search-posts/', SearchPosts.as_view(), name='search-posts'),
]