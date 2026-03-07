from rest_framework import serializers
from .models import User, Post, Comment, Like  # Make sure Like is imported!

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'created_at']

class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'text', 'author', 'post', 'created_at']

    def validate_post(self, value):
        if not Post.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Post not found.")
        return value

    def validate_author(self, value):
        if not User.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Author not found.")
        return value

class LikeSerializer(serializers.ModelSerializer):
    user_username = serializers.ReadOnlyField(source='user.username')
    
    class Meta:
        model = Like
        fields = ['id', 'user', 'user_username', 'post', 'created_at']
        read_only_fields = ['created_at']

    def validate(self, data):
        user = data.get('user')
        post = data.get('post')
        
        if Like.objects.filter(user=user, post=post).exists():
            raise serializers.ValidationError("You have already liked this post")
        
        return data

class PostSerializer(serializers.ModelSerializer):
    comments = serializers.StringRelatedField(many=True, read_only=True)
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = ['id', 'content', 'author', 'created_at', 'comments', 'like_count', 'comment_count']
    
    def get_like_count(self, obj):
        return obj.likes.count()
    
    def get_comment_count(self, obj):
        return obj.comments.count()