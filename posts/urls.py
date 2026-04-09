from django.urls import path
from . import views
from . import views_oauth

urlpatterns = [
    # Existing endpoints
    path('users/', views.get_users, name='get_users'),
    path('users/create/', views.create_user, name='create_user'),
    path('posts/', views.get_posts, name='get_posts'),
    path('posts/create/', views.create_post, name='create_post'),
    
    # DRF endpoints
    path('api/users/', views.UserListCreate.as_view(), name='user-list-create'),
    path('api/posts/', views.PostListCreate.as_view(), name='post-list-create'),
    path('api/comments/', views.CommentListCreate.as_view(), name='comment-list-create'),
    
    # Protected endpoints
    path('protected/', views.ProtectedView.as_view(), name='protected'),
    path('post/<int:pk>/', views.PostDetailView.as_view(), name='post-detail'),
    
    # Factory endpoint
    path('factory/posts/create/', views.CreatePostWithFactoryView.as_view(), name='factory-create-post'),
    
    # ========== ADD THESE NEW LIKE ENDPOINTS ==========
    path('<int:pk>/like/', views.LikePostView.as_view(), name='like-post'),
    path('<int:pk>/unlike/', views.UnlikePostView.as_view(), name='unlike-post'),
    path('<int:pk>/likes/', views.PostLikesView.as_view(), name='post-likes'),
    
    # ========== ADD THESE COMMENT ENDPOINTS ==========
    path('<int:pk>/comment/', views.CreateCommentView.as_view(), name='create-comment'),
    path('<int:pk>/comments/', views.PostCommentsView.as_view(), name='post-comments'),
    
    # ========== OPTIONAL: POST WITH COUNTS ==========
    path('<int:pk>/with-counts/', views.PostWithCountsView.as_view(), name='post-with-counts'),

    path('api/auth/google/', views_oauth.GoogleLoginView.as_view(), name='google-login'),

    path('api/google/test/', views.GoogleLoginTest.as_view(), name='google-test'),

    path('test/google-token/', views.test_google_token, name='test-google-token'),

    path('feed/', views.NewsFeedView.as_view(), name='news-feed'),
    
    path('feed/simple/', views.SimpleFeedView.as_view(), name='simple-feed'),

      # ========== NEW RBAC AND PRIVACY ENDPOINTS ==========
    
    # Role management endpoints (admin only)
    path('admin/users/', views.ListUsersView.as_view(), name='list-users'),
    path('admin/users/<int:user_id>/promote/', views.PromoteToAdminView.as_view(), name='promote-user'),
    path('admin/users/<int:user_id>/demote/', views.DemoteFromAdminView.as_view(), name='demote-user'),
    path('admin/users/<int:user_id>/role/', views.UpdateUserRoleView.as_view(), name='update-role'),
    
    # User role info (authenticated users)
    path('user/role/', views.GetUserRoleView.as_view(), name='user-role'),
    
    # Privacy endpoints
    path('posts/<int:pk>/privacy/', views.UpdatePostPrivacyView.as_view(), name='update-privacy'),

    # Cache management
    path('admin/cache/clear/', views.ClearCacheView.as_view(), name='clear-cache'),

    path('profile/<int:user_id>/tasks/', views.UserProfileWithTasks.as_view(), name='user-tasks'),

    path('share-task/', views.ShareTaskAsPost.as_view(), name='share-task'),

    path('assign-task/', views.AssignTaskToFollower.as_view(), name='assign-task'),
]