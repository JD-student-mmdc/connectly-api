from rest_framework.permissions import BasePermission

class IsPostAuthor(BasePermission):
    """Allows access only to the author of a post."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.author.id == request.user.id


class IsAdminUser(BasePermission):
    """Allows access only to admin users."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get the custom user from posts.models
        from .models import User as CustomUser
        try:
            custom_user = CustomUser.objects.get(username=request.user.username)
            return custom_user.is_admin()
        except CustomUser.DoesNotExist:
            return False
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsOwnerOrAdmin(BasePermission):
    """Allows access only to owners of an object or admins."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin can do anything
        if request.user.is_admin():
            return True
        
        # Check if user is the owner (author) of the object
        if hasattr(obj, 'author'):
            return obj.author.id == request.user.id
        elif hasattr(obj, 'user'):
            return obj.user.id == request.user.id
        
        return False


class CanViewPost(BasePermission):
    """Check if user can view a post based on privacy settings."""
    
    def has_object_permission(self, request, view, obj):
        if not hasattr(obj, 'privacy'):
            return True
        
        # Public posts are viewable by everyone
        if obj.is_public():
            return True
        
        # For private posts, check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Owner can view their own private posts
        if obj.author.id == request.user.id:
            return True
        
        # Admins can view all posts
        if request.user.is_admin():
            return True
        
        return False


class IsRegularUser(BasePermission):
    """Allows access only to regular users (not guests)."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'user'
    
    
class IsOwner(BasePermission):
    """Allows access only to owners of an object."""
    
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if hasattr(obj, 'author'):
            return obj.author.id == request.user.id
        elif hasattr(obj, 'user'):
            return obj.user.id == request.user.id
        
        return False