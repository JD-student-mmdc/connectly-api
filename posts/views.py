from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsPostAuthor
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User, Post, Comment, Like  # ✅ Added Like
from .serializers import UserSerializer, PostSerializer, CommentSerializer, LikeSerializer  # ✅ Added LikeSerializer
from factories.post_factory import PostFactory
from singletons.logger_singleton import LoggerSingleton
from singletons.config_manager import ConfigManager

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
        serializer = PostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
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
    permission_classes = [IsAuthenticated, IsPostAuthor]

    def get(self, request, pk):
        try:
            post = Post.objects.get(pk=pk)
            self.check_object_permissions(request, post)
            return Response({"content": post.content, "author": post.author.username})
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=404)
    
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
    Get news feed with pagination and sorting
    """
    def get(self, request):
        try:
            # Get query parameters with defaults
            page = request.GET.get('page', 1)
            page_size = request.GET.get('page_size', 10)
            sort_by = request.GET.get('sort', '-created_at')  # Default: newest first
            feed_type = request.GET.get('type', 'all')  # all, following, popular
            
            # Base queryset
            if feed_type == 'popular':
                # Sort by like count
                queryset = Post.objects.annotate(
                    like_count=Count('likes')
                ).order_by('-like_count', '-created_at')
            elif feed_type == 'following' and request.user.is_authenticated:
                # Posts from users the current user follows
                # You'll need a Follow model for this - optional
                queryset = Post.objects.all().order_by(sort_by)
            else:
                # Default: all posts sorted by date
                queryset = Post.objects.all().order_by(sort_by)
            
            # Optimize with select_related and prefetch_related
            queryset = queryset.select_related('author').prefetch_related('likes', 'comments')
            
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
                    'content': post.content,
                    'author': {
                        'id': post.author.id,
                        'username': post.author.username
                    },
                    'created_at': post.created_at,
                    'like_count': post.likes.count(),
                    'comment_count': post.comments.count(),
                    'post_type': getattr(post, 'post_type', 'text'),
                })
            
            # Build paginated response
            response_data = {
                'count': paginator.count,
                'total_pages': paginator.num_pages,
                'current_page': posts_page.number,
                'page_size': page_size,
                'has_next': posts_page.has_next(),
                'has_previous': posts_page.has_previous(),
                'results': posts_data
            }
            
            if posts_page.has_next():
                response_data['next_page'] = posts_page.next_page_number()
            if posts_page.has_previous():
                response_data['previous_page'] = posts_page.previous_page_number()
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SimpleFeedView(APIView):
    """
    Simple news feed with basic pagination
    """
    def get(self, request):
        # Get page and page_size from query params
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        # Get all posts ordered by date (newest first)
        posts = Post.objects.all().order_by('-created_at')
        
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