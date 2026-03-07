from posts.models import Post, User
from singletons.config_manager import ConfigManager
from singletons.logger_singleton import LoggerSingleton

config = ConfigManager()
logger = LoggerSingleton().get_logger()

class PostFactory:
    @staticmethod
    def create_post(post_type, content='', author_id=None, metadata=None):
        if metadata is None:
            metadata = {}
        
        valid_types = [pt[0] for pt in Post.POST_TYPES]
        if post_type not in valid_types:
            raise ValueError(f"Invalid post type. Must be one of: {valid_types}")
        
        if not content or content.strip() == '':
            raise ValueError("Post content cannot be empty")
        
        try:
            author = User.objects.get(id=author_id)
        except User.DoesNotExist:
            raise ValueError(f"Author with id {author_id} not found")
        
        if post_type == 'image' and 'file_size' not in metadata:
            raise ValueError("Image posts require 'file_size' in metadata")
        if post_type == 'video' and 'duration' not in metadata:
            raise ValueError("Video posts require 'duration' in metadata")
        
        post = Post.objects.create(
            content=content,
            author=author,
            post_type=post_type,
            metadata=metadata
        )
        
        logger.info(f"Post created via factory: {post.id} (type: {post_type})")
        
        return post