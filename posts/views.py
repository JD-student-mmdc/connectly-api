from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsPostAuthor, IsAdminUser, IsOwnerOrAdmin, CanViewPost, IsRegularUser
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from .models import User, Post, Comment, Like  # ✅ Added Like
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer  # ✅ Added LikeSerializer
from .permissions import IsAdminUser, IsOwnerOrAdmin, CanViewPost, IsRegularUser
from factories.post_factory import PostFactory
from singletons.logger_singleton import LoggerSingleton
from singletons.config_manager import ConfigManager
from django.core.cache import cache
import hashlib
import json
from django.db.models import Prefetch
from django.db import models

logger = LoggerSingleton().get_logger()


# ========== EXISTING FUNCTION-BASED VIEWS (Keep these) ==========

def get_users(request):
    try:
        users = list(User.objects.values('id', 'username', 'email', 'created_at'))
        return JsonResponse(users, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def create_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Received data:", data)
            
            from django.contrib.auth.models import User as AuthUser
            from .models import User as ProfileUser
            
            try:
                # Create auth user
                auth_user = AuthUser.objects.create_user(
                    username=data['username'],
                    password=data.get('password', 'temp123'),
                    email=data['email']
                )
                print("Auth user created:", auth_user.username)
            except Exception as auth_error:
                return JsonResponse({'error': f'Auth user error: {str(auth_error)}'}, status=400)
            
            try:
                # Create profile user
                user = ProfileUser.objects.create(
                    username=data['username'],
                    email=data['email']
                )
                print("Profile user created:", user.username)
            except Exception as profile_error:
                return JsonResponse({'error': f'Profile user error: {str(profile_error)}'}, status=400)
            
            return JsonResponse({'id': user.id, 'message': 'User created successfully'}, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'General error: {str(e)}'}, status=400)
            
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_posts(request):
    try:
        posts = list(Post.objects.values('id', 'content', 'author', 'created_at'))
        return JsonResponse(posts, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def create_post(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            author = User.objects.get(id=data['author'])
            post = Post.objects.create(content=data['content'], author=author)
            return JsonResponse({'id': post.id, 'message': 'Post created successfully'}, status=201)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Author not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# ========== NEW DRF CLASS-BASED VIEWS ==========

class UserListCreate(APIView):
    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PostListCreate(APIView):
    def get(self, request):
        posts = Post.objects.all()
        serializer = PostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Make a copy of the data
        data = request.data.copy()
        
        # If privacy is not provided, default to 'public'
        if 'privacy' not in data:
            data['privacy'] = 'public'
        
        serializer = PostSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Post created by user {data.get('author')} with privacy: {data.get('privacy')}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CommentListCreate(APIView):
    def get(self, request):
        comments = Comment.objects.all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProtectedView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "Authenticated!", "user": request.user.username})

class PostDetailView(APIView):
    """
    Retrieve, update or delete a post with optimized queries
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            # Try to get from cache first
            cache_key = f"post_detail_{pk}_{request.user.id}"
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache HIT for post {pk}")
                return Response(cached_response)
            
            logger.info(f"Cache MISS for post {pk}")
            
            # Optimized query with related data - THIS IS THE KEY OPTIMIZATION!
            post = Post.objects.select_related('author').prefetch_related(
                Prefetch('likes', queryset=Like.objects.select_related('user')),
                Prefetch('comments', queryset=Comment.objects.select_related('author').order_by('-created_at')[:10])
            ).get(pk=pk)
            
            # Check if user can view this post
            if not post.can_view(request.user):
                logger.warning(f"User {request.user.id} attempted to view private post {pk}")
                return Response(
                    {'error': 'You do not have permission to view this post'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Serialize the data
            serializer = PostSerializer(post)
            response_data = serializer.data
            
            # Add cache hit/miss indicator for testing
            response_data['cached'] = False
            
            # Store in cache for 1 minute
            cache.set(cache_key, response_data, timeout=60)
            
            return Response(response_data)
            
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def put(self, request, pk):
        # Update method - no caching needed
        try:
            post = Post.objects.get(pk=pk)
            
            # Check if user can edit this post
            if not post.can_edit(request.user):
                logger.warning(f"User {request.user.id} attempted to edit post {pk} without permission")
                return Response(
                    {'error': 'You do not have permission to edit this post'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = PostSerializer(post, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # Clear cache for this post since it was updated
                cache_key = f"post_detail_{pk}_{request.user.id}"
                cache.delete(cache_key)
                logger.info(f"Cache cleared for post {pk} after update")
                
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def delete(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            
            # Check if user can delete this post
            if not post.can_delete(request.user):
                logger.warning(f"User {request.user.id} attempted to delete post {pk} without permission")
                return Response(
                    {'error': 'You do not have permission to delete this post'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Clear cache before deleting
            cache_key = f"post_detail_{pk}_{request.user.id}"
            cache.delete(cache_key)
            
            post.delete()
            logger.info(f"Post {pk} deleted by user {request.user.id}")
            return Response({"message": "Post deleted successfully"}, status=status.HTTP_200_OK)
            
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        
class UpdatePostPrivacyView(APIView):
    """
    Update privacy setting of a post (owner or admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            
            # Only author or admin can change privacy
            if not post.can_edit(request.user):
                return Response(
                    {'error': 'You do not have permission to change privacy settings'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            privacy = request.data.get('privacy')
            if privacy not in ['public', 'private']:
                return Response(
                    {'error': 'Privacy must be either "public" or "private"'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            old_privacy = post.privacy
            post.privacy = privacy
            post.save()
            
            logger.info(f"Post {pk} privacy changed from {old_privacy} to {privacy} by user {request.user.id}")
            
            return Response({
                'message': f'Post privacy updated to {privacy}',
                'post_id': post.id,
                'privacy': post.privacy,
                'author': post.author.username
            })
            
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
    
class CreatePostWithFactoryView(APIView):
    def post(self, request):
        data = request.data
        try:
            post = PostFactory.create_post(
                post_type=data.get('post_type', 'text'),
                content=data.get('content', ''),
                author_id=data.get('author'),
                metadata=data.get('metadata', {})
            )
            return Response({
                'message': 'Post created successfully!',
                'post_id': post.id,
                'post_type': post.post_type
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)  

class LikePostView(APIView):
    def post(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            user_id = request.data.get('user')
            
            if not user_id:
                return Response({"error": "User ID required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if like already exists
            like, created = Like.objects.get_or_create(user=user, post=post)
            
            if created:
                logger.info(f"Post {pk} liked by user {user_id}")
                serializer = LikeSerializer(like)
                return Response({
                    'message': 'Post liked successfully',
                    'like': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": "You already liked this post"}, status=status.HTTP_400_BAD_REQUEST)
                
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

class UnlikePostView(APIView):
    def delete(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            user_id = request.data.get('user')
            
            if not user_id:
                return Response({"error": "User ID required"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
            like = Like.objects.filter(user=user, post=post)
            
            if like.exists():
                like.delete()
                logger.info(f"Post {pk} unliked by user {user_id}")
                return Response({"message": "Like removed successfully"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "You haven't liked this post"}, status=status.HTTP_400_BAD_REQUEST)
                
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

class PostLikesView(APIView):
    def get(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            likes = Like.objects.filter(post=post)
            serializer = LikeSerializer(likes, many=True)
            return Response({
                'post_id': pk,
                'like_count': likes.count(),
                'likes': serializer.data
            })
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

class PostLikesView(APIView):
    def get(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            likes = Like.objects.filter(post=post)
            serializer = LikeSerializer(likes, many=True)
            return Response({
                'post_id': pk,
                'like_count': likes.count(),
                'likes': serializer.data
            })
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)


class CreateCommentView(APIView):
    def post(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            data = request.data.copy()
            data['post'] = post.id
            
            serializer = CommentSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                logger.info(f"Comment added to post {pk}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

class PostCommentsView(APIView):
    def get(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            comments = Comment.objects.filter(post=post).order_by('-created_at')
            serializer = CommentSerializer(comments, many=True)
            return Response({
                'post_id': pk,
                'comment_count': comments.count(),
                'comments': serializer.data
            })
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)
        
class PostWithCountsView(APIView):
    def get(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            data = {
                'id': post.id,
                'content': post.content,
                'author': post.author.id,
                'author_username': post.author.username,
                'created_at': post.created_at,
                'like_count': post.likes.count(),
                'comment_count': post.comments.count(),
                'recent_comments': CommentSerializer(post.comments.all()[:5], many=True).data
            }
            return Response(data)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=404)

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

class GoogleLoginTest(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://127.0.0.1:8000/accounts/google/login/callback/"
    client_class = OAuth2Client


import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def test_google_token(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        access_token = data.get('access_token')
        
        if not access_token:
            return JsonResponse({'error': 'No token provided'}, status=400)
        
        # Verify token with Google
        url = 'https://www.googleapis.com/oauth2/v1/userinfo'
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                return JsonResponse({
                    'success': True,
                    'email': user_data.get('email'),
                    'name': user_data.get('name'),
                    'data': user_data
                })
            else:
                return JsonResponse({
                    'error': 'Invalid token',
                    'details': response.text
                }, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class NewsFeedView(APIView):
    """
    Optimized news feed with pagination, caching, and query optimization
    """
    def get(self, request):
        try:
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            feed_type = request.GET.get('type', 'all')
            
            # Create a cache key based on request parameters
            cache_key = self._generate_cache_key(request)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache HIT for feed: {cache_key}")
                return Response(cached_response)
            
            logger.info(f"Cache MISS for feed: {cache_key}")
            
            # Start with base queryset
            queryset = Post.objects.all()
            
            # Apply privacy filtering
            if request.user.is_authenticated:
                if hasattr(request.user, 'is_admin') and request.user.is_admin():
                    pass  # Admins see everything
                else:
                    queryset = queryset.filter(
                        models.Q(privacy='public') | 
                        models.Q(author__username=request.user.username)
                    )
            else:
                queryset = queryset.filter(privacy='public')
            
            # Apply feed type
            if feed_type == 'popular':
                queryset = queryset.annotate(
                    like_count=Count('likes')
                ).order_by('-like_count', '-created_at')
            elif feed_type == 'my_posts' and request.user.is_authenticated:
                queryset = queryset.filter(author__username=request.user.username).order_by('-created_at')
            else:
                queryset = queryset.order_by('-created_at')
            
            # Optimize queries
            queryset = queryset.select_related('author').prefetch_related('likes', 'comments')
            
            # Get total count (cached separately)
            count_cache_key = f"feed_count_{feed_type}_{request.user.id if request.user.is_authenticated else 'anon'}"
            total_count = cache.get(count_cache_key)
            if total_count is None:
                total_count = queryset.count()
                cache.set(count_cache_key, total_count, timeout=600)  # 10 minutes
            
            # Pagination
            paginator = Paginator(queryset, page_size)
            
            try:
                posts_page = paginator.page(page)
            except PageNotAnInteger:
                posts_page = paginator.page(1)
            except EmptyPage:
                posts_page = paginator.page(paginator.num_pages)
            
            # Prepare response data
            posts_data = []
            for post in posts_page:
                posts_data.append({
                    'id': post.id,
                    'content': post.content[:200] + '...' if len(post.content) > 200 else post.content,
                    'author': {
                        'id': post.author.id,
                        'username': post.author.username,
                        'role': getattr(post.author, 'role', 'user')
                    },
                    'created_at': post.created_at,
                    'privacy': getattr(post, 'privacy', 'public'),
                    'like_count': post.likes.count(),
                    'comment_count': post.comments.count(),
                    'is_owner': request.user.is_authenticated and post.author.username == request.user.username
                })
            
            # Build response
            response_data = {
                'count': total_count,
                'total_pages': paginator.num_pages,
                'current_page': posts_page.number,
                'page_size': page_size,
                'has_next': posts_page.has_next(),
                'has_previous': posts_page.has_previous(),
                'feed_type': feed_type,
                'results': posts_data,
                'cached': False
            }
            
            if posts_page.has_next():
                response_data['next_page'] = posts_page.next_page_number()
            if posts_page.has_previous():
                response_data['previous_page'] = posts_page.previous_page_number()
            
            # Store in cache for 5 minutes
            cache.set(cache_key, response_data, timeout=300)
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error in feed: {str(e)}")
            return Response({'error': str(e)}, status=500)
    
    def _generate_cache_key(self, request):
        """Generate unique cache key based on request parameters"""
        key_data = f"feed_{request.GET.urlencode()}_{request.user.id if request.user.is_authenticated else 'anon'}"
        return f"feed_{hashlib.md5(key_data.encode()).hexdigest()}"

class SimpleFeedView(APIView):
    """
    Simple news feed with basic pagination and privacy filtering
    """
    def get(self, request):
        try:
            # Get page and page_size from query params
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            
            # Apply privacy filtering
            if request.user.is_authenticated:
                if request.user.is_admin():
                    # Admins see everything
                    posts = Post.objects.all().order_by('-created_at')
                else:
                    # Regular users: public posts + their own private posts
                    posts = Post.objects.filter(
                        models.Q(privacy='public') | 
                        models.Q(author=request.user)
                    ).order_by('-created_at')
            else:
                # Anonymous users: only public posts
                posts = Post.objects.filter(privacy='public').order_by('-created_at')
            
            # Paginate
            paginator = Paginator(posts, page_size)
            
            try:
                posts_page = paginator.page(page)
            except EmptyPage:
                return Response(
                    {'error': 'Page not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serialize
            serializer = PostSerializer(posts_page, many=True)
            
            # Return paginated response
            return Response({
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': page,
                'next': posts_page.has_next(),
                'previous': posts_page.has_previous(),
                'results': serializer.data
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
# ========== ROLE MANAGEMENT VIEWS ==========

class PromoteToAdminView(APIView):
    """
    Promote a user to admin (admin only)
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            
            # Check if already admin
            if user.is_admin():
                return Response(
                    {'error': f'User {user.username} is already an admin'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.role = 'admin'
            user.save()
            logger.info(f"User {user_id} promoted to admin by {request.user.id}")
            
            return Response({
                'message': f'User {user.username} promoted to admin successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DemoteFromAdminView(APIView):
    """
    Demote an admin to regular user (admin only)
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            
            # Check if user is admin
            if not user.is_admin():
                return Response(
                    {'error': f'User {user.username} is not an admin'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Prevent demoting yourself
            if user.id == request.user.id:
                return Response(
                    {'error': 'You cannot demote yourself'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.role = 'user'
            user.save()
            logger.info(f"User {user_id} demoted to user by {request.user.id}")
            
            return Response({
                'message': f'User {user.username} demoted to regular user',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class ListUsersView(APIView):
    """
    List all users with their roles (admin only)
    """
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        # Use the custom User model directly
        from .models import User as CustomUser
        
        users = CustomUser.objects.all().values(
            'id', 'username', 'email', 'role', 'created_at'
        ).order_by('-created_at')
        
        return Response({
            'count': users.count(),
            'users': list(users)
        })


class GetUserRoleView(APIView):
    """
    Get current user's role information
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Get the custom user from posts.models using the username
        from .models import User as CustomUser
        
        try:
            custom_user = CustomUser.objects.get(username=request.user.username)
            return Response({
                'id': custom_user.id,
                'username': custom_user.username,
                'email': custom_user.email,
                'role': custom_user.role,
                'is_admin': custom_user.is_admin(),
                'is_regular_user': custom_user.role == 'user',
                'created_at': custom_user.created_at
            })
        except CustomUser.DoesNotExist:
            return Response({
                'error': 'User profile not found',
                'username': request.user.username
            }, status=404)


class UpdateUserRoleView(APIView):
    """
    Update a user's role directly (admin only)
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            new_role = request.data.get('role')
            
            if new_role not in ['admin', 'user', 'guest']:
                return Response(
                    {'error': 'Role must be one of: admin, user, guest'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Prevent changing your own role (to avoid losing admin access)
            if user.id == request.user.id and new_role != 'admin':
                return Response(
                    {'error': 'You cannot remove your own admin privileges'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            old_role = user.role
            user.role = new_role
            user.save()
            
            logger.info(f"User {user_id} role changed from {old_role} to {new_role} by {request.user.id}")
            
            return Response({
                'message': f'User {user.username} role updated from {old_role} to {new_role}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'role': user.role
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
class ClearCacheView(APIView):
    """
    Clear all cache (admin only)
    """
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        try:
            cache.clear()
            logger.info(f"Cache cleared by user {request.user.username}")
            return Response({
                'message': 'Cache cleared successfully',
                'cleared_by': request.user.username
            })
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return Response({'error': str(e)}, status=500)