from rest_framework.permissions import BasePermission

class IsPostAuthor(BasePermission):
    def has_object_permission(self, request, view, obj):
        # Check if the user is the author of the post
        return obj.author.id == request.user.id