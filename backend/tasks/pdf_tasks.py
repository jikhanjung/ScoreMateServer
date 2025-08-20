"""
Celery tasks for PDF processing (info extraction, thumbnail generation)
"""
import os
import tempfile
import logging
from celery import shared_task
from django.conf import settings
import pdfplumber
from PIL import Image
import fitz  # PyMuPDF for thumbnail generation

from scores.models import Score
from files.utils import S3Handler

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pdf_info(self, score_id):
    """
    Extract PDF information (pages, metadata) from uploaded PDF
    """
    try:
        score = Score.objects.get(id=score_id)
        logger.info(f"Starting PDF info extraction for score {score_id}")
        
        if not score.s3_key:
            logger.error(f"Score {score_id} has no S3 key")
            return {'success': False, 'error': 'No S3 key'}
        
        s3_handler = S3Handler()
        
        # Download PDF to temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            try:
                # Generate download URL (use internal endpoint for Celery worker)
                download_data = s3_handler.generate_presigned_download_url(
                    score.s3_key, expiry=600, use_public_endpoint=False
                )
                
                # Download file (in a real implementation, you'd use requests to download)
                # For now, we'll simulate the process
                
                import requests
                response = requests.get(download_data['url'], timeout=30)
                response.raise_for_status()
                
                temp_file.write(response.content)
                temp_file.flush()
                
                # Extract PDF information
                with pdfplumber.open(temp_file.name) as pdf:
                    page_count = len(pdf.pages)
                    
                    # Extract basic metadata
                    metadata = pdf.metadata or {}
                    
                    # Update score with extracted information
                    score.pages = page_count
                    
                    # Update title and composer if not already set and available in metadata
                    if not score.title and metadata.get('Title'):
                        score.title = metadata['Title'][:200]  # Limit length
                    
                    if not score.composer and metadata.get('Author'):
                        score.composer = metadata['Author'][:100]  # Limit length
                    
                    score.save(update_fields=['pages', 'title', 'composer'])
                
                logger.info(f"Successfully extracted PDF info for score {score_id}: {page_count} pages")
                
                return {
                    'success': True,
                    'score_id': score_id,
                    'pages': page_count,
                    'metadata': metadata
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass
    
    except Score.DoesNotExist:
        logger.error(f"Score {score_id} not found")
        return {'success': False, 'error': 'Score not found'}
    
    except Exception as exc:
        logger.error(f"PDF info extraction failed for score {score_id}: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(exc)}


@shared_task(bind=True, max_retries=3)
def generate_thumbnail(self, score_id, page_number=1):
    """
    Generate thumbnail for PDF (cover or specific page)
    """
    try:
        score = Score.objects.get(id=score_id)
        logger.info(f"Starting thumbnail generation for score {score_id}, page {page_number}")
        
        if not score.s3_key:
            logger.error(f"Score {score_id} has no S3 key")
            return {'success': False, 'error': 'No S3 key'}
        
        s3_handler = S3Handler()
        
        # Download PDF to temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            try:
                # Download PDF (use internal endpoint for Celery worker)
                download_data = s3_handler.generate_presigned_download_url(
                    score.s3_key, expiry=600, use_public_endpoint=False
                )
                
                import requests
                response = requests.get(download_data['url'], timeout=30)
                response.raise_for_status()
                
                temp_pdf.write(response.content)
                temp_pdf.flush()
                
                # Generate thumbnail using PyMuPDF
                pdf_doc = fitz.open(temp_pdf.name)
                
                if page_number > len(pdf_doc):
                    logger.error(f"Page {page_number} not found in PDF with {len(pdf_doc)} pages")
                    return {'success': False, 'error': f'Page {page_number} not found'}
                
                # Get page (0-indexed)
                page = pdf_doc[page_number - 1]
                
                # Render page as image
                mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image for resizing
                with tempfile.NamedTemporaryFile(suffix='.png') as temp_img:
                    temp_img.write(img_data)
                    temp_img.flush()
                    
                    with Image.open(temp_img.name) as img:
                        # Resize to thumbnail size (max 300x400, maintain aspect ratio)
                        img.thumbnail((300, 400), Image.Resampling.LANCZOS)
                        
                        # Save as JPEG for smaller file size
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as thumb_file:
                            img.convert('RGB').save(thumb_file.name, 'JPEG', quality=85, optimize=True)
                            
                            # Upload thumbnail to S3
                            if page_number == 1:
                                # Cover thumbnail
                                thumb_s3_key = score.generate_thumbnail_s3_key()
                            else:
                                # Page thumbnail
                                thumb_s3_key = score.generate_page_thumbnail_s3_key(page_number)
                            
                            # Upload to S3
                            with open(thumb_file.name, 'rb') as thumb_data:
                                s3_handler.s3_client.put_object(
                                    Bucket=s3_handler.bucket_name,
                                    Key=thumb_s3_key,
                                    Body=thumb_data,
                                    ContentType='image/jpeg',
                                    CacheControl='max-age=86400'  # 24 hours
                                )
                            
                            # Update score with thumbnail key (for cover only)
                            if page_number == 1:
                                score.thumbnail_key = thumb_s3_key
                                score.save(update_fields=['thumbnail_key'])
                            
                            # Clean up temporary thumbnail file
                            try:
                                os.unlink(thumb_file.name)
                            except OSError:
                                pass
                
                pdf_doc.close()
                
                logger.info(f"Successfully generated thumbnail for score {score_id}, page {page_number}")
                
                return {
                    'success': True,
                    'score_id': score_id,
                    'page_number': page_number,
                    'thumbnail_key': thumb_s3_key
                }
                
            finally:
                # Clean up temporary PDF file
                try:
                    os.unlink(temp_pdf.name)
                except OSError:
                    pass
    
    except Score.DoesNotExist:
        logger.error(f"Score {score_id} not found")
        return {'success': False, 'error': 'Score not found'}
    
    except Exception as exc:
        logger.error(f"Thumbnail generation failed for score {score_id}: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(exc)}


@shared_task(bind=True, max_retries=3)
def generate_all_page_thumbnails(self, score_id):
    """
    Generate thumbnails for all pages of a PDF
    """
    try:
        score = Score.objects.get(id=score_id)
        logger.info(f"Starting all page thumbnails generation for score {score_id}")
        
        if not score.pages:
            # First extract PDF info to get page count
            info_result = process_pdf_info(score_id)
            if not info_result.get('success'):
                return {'success': False, 'error': 'Failed to get page count'}
            
            score.refresh_from_db()
        
        if not score.pages:
            return {'success': False, 'error': 'Page count not available'}
        
        results = []
        failed_pages = []
        
        # Generate thumbnail for each page
        for page_num in range(1, score.pages + 1):
            try:
                result = generate_thumbnail(score_id, page_num)
                results.append(result)
                
                if not result.get('success'):
                    failed_pages.append(page_num)
                    
            except Exception as e:
                logger.error(f"Failed to generate thumbnail for page {page_num}: {e}")
                failed_pages.append(page_num)
        
        success_count = len([r for r in results if r.get('success')])
        
        logger.info(f"Generated {success_count}/{score.pages} thumbnails for score {score_id}")
        
        return {
            'success': len(failed_pages) == 0,
            'score_id': score_id,
            'total_pages': score.pages,
            'successful_pages': success_count,
            'failed_pages': failed_pages,
            'results': results
        }
        
    except Score.DoesNotExist:
        logger.error(f"Score {score_id} not found")
        return {'success': False, 'error': 'Score not found'}
    
    except Exception as exc:
        logger.error(f"All page thumbnails generation failed for score {score_id}: {exc}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(exc)}