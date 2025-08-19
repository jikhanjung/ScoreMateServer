"""
Celery tasks for file operations (deletion, cleanup)
"""
import logging
from celery import shared_task

from files.utils import S3Handler

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def delete_score_files(self, original_s3_key, thumbnail_s3_key=None, score_id=None):
    """
    Delete all files related to a score from S3
    """
    try:
        s3_handler = S3Handler()
        deleted_files = []
        failed_files = []
        
        logger.info(f"Starting file deletion for score {score_id or 'unknown'}")
        
        # Delete original PDF
        if original_s3_key:
            try:
                s3_handler.delete_file(original_s3_key)
                deleted_files.append(original_s3_key)
                logger.info(f"Deleted original file: {original_s3_key}")
            except Exception as e:
                logger.error(f"Failed to delete original file {original_s3_key}: {e}")
                failed_files.append(original_s3_key)
        
        # Delete cover thumbnail
        if thumbnail_s3_key:
            try:
                s3_handler.delete_file(thumbnail_s3_key)
                deleted_files.append(thumbnail_s3_key)
                logger.info(f"Deleted thumbnail file: {thumbnail_s3_key}")
            except Exception as e:
                logger.error(f"Failed to delete thumbnail file {thumbnail_s3_key}: {e}")
                failed_files.append(thumbnail_s3_key)
        
        # Delete page thumbnails if score_id is provided
        if score_id:
            try:
                from scores.models import Score
                score = Score.objects.get(id=score_id)
                
                if score.pages:
                    for page_num in range(1, score.pages + 1):
                        page_thumb_key = score.generate_page_thumbnail_s3_key(page_num)
                        try:
                            # Check if file exists before trying to delete
                            if s3_handler.check_file_exists(page_thumb_key):
                                s3_handler.delete_file(page_thumb_key)
                                deleted_files.append(page_thumb_key)
                                logger.info(f"Deleted page thumbnail: {page_thumb_key}")
                        except Exception as e:
                            logger.error(f"Failed to delete page thumbnail {page_thumb_key}: {e}")
                            failed_files.append(page_thumb_key)
                            
            except Exception as e:
                logger.error(f"Failed to delete page thumbnails for score {score_id}: {e}")
        
        success = len(failed_files) == 0
        
        logger.info(f"File deletion completed. Deleted: {len(deleted_files)}, Failed: {len(failed_files)}")
        
        return {
            'success': success,
            'score_id': score_id,
            'deleted_files': deleted_files,
            'failed_files': failed_files,
            'total_deleted': len(deleted_files),
            'total_failed': len(failed_files)
        }
        
    except Exception as exc:
        logger.error(f"File deletion task failed: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': str(exc),
            'score_id': score_id
        }


@shared_task(bind=True, max_retries=2)
def delete_single_file(self, s3_key):
    """
    Delete a single file from S3
    """
    try:
        s3_handler = S3Handler()
        s3_handler.delete_file(s3_key)
        
        logger.info(f"Successfully deleted file: {s3_key}")
        
        return {
            'success': True,
            's3_key': s3_key,
            'message': 'File deleted successfully'
        }
        
    except Exception as exc:
        logger.error(f"Failed to delete file {s3_key}: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        
        return {
            'success': False,
            's3_key': s3_key,
            'error': str(exc)
        }


@shared_task(bind=True, max_retries=2)
def cleanup_orphaned_files(self):
    """
    Clean up orphaned files in S3 that don't have corresponding database records
    This is a maintenance task that should be run periodically
    """
    try:
        logger.info("Starting orphaned files cleanup")
        
        # This is a complex operation that would:
        # 1. List all files in S3 bucket
        # 2. Check which ones have corresponding database records
        # 3. Delete files without database records (with caution)
        
        # For now, return a placeholder
        logger.info("Orphaned files cleanup completed (placeholder)")
        
        return {
            'success': True,
            'message': 'Cleanup completed',
            'deleted_files': [],
            'errors': []
        }
        
    except Exception as exc:
        logger.error(f"Orphaned files cleanup failed: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=300)  # 5 minute delay
        
        return {
            'success': False,
            'error': str(exc)
        }


@shared_task(bind=True, max_retries=2)
def cleanup_expired_uploads(self):
    """
    Clean up expired upload reservations from Redis
    This should be run periodically to clean up abandoned uploads
    """
    try:
        from django.core.cache import cache
        import fnmatch
        
        logger.info("Starting expired uploads cleanup")
        
        # Get all quota reservation keys
        # Note: This approach depends on the cache backend
        # For Redis, we could use SCAN command
        # For now, return a placeholder
        
        cleaned_count = 0
        
        logger.info(f"Expired uploads cleanup completed. Cleaned: {cleaned_count}")
        
        return {
            'success': True,
            'cleaned_reservations': cleaned_count,
            'message': 'Expired uploads cleanup completed'
        }
        
    except Exception as exc:
        logger.error(f"Expired uploads cleanup failed: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        
        return {
            'success': False,
            'error': str(exc)
        }