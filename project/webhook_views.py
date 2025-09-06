"""
DataForSEO webhook handler views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .tasks import process_dataforseo_webhook

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def dataforseo_webhook(request):
    """
    Handle webhook callbacks from DataForSEO
    
    DataForSEO sends a POST request with task results when completed.
    This endpoint processes those callbacks and triggers any necessary actions.
    """
    try:
        # Parse the webhook payload
        if request.content_type == 'application/json':
            try:
                webhook_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in webhook: {e}")
                return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        else:
            # Try to parse form data
            webhook_data = dict(request.POST)
        
        # Extract task_id from query params or payload
        task_id = request.GET.get('task_id') or webhook_data.get('task_id')
        
        if not task_id:
            logger.warning("Received webhook without task_id")
            # Still process it but log for debugging
            task_id = "unknown"
        
        logger.info(f"Received DataForSEO webhook for task: {task_id}")
        logger.debug(f"Webhook data: {json.dumps(webhook_data, indent=2)[:1000]}")  # Log first 1000 chars
        
        # Process the webhook asynchronously
        process_dataforseo_webhook.delay(task_id, webhook_data)
        
        # Return success immediately
        return JsonResponse({
            "status": "received",
            "task_id": task_id,
            "message": "Webhook received and queued for processing"
        })
        
    except Exception as e:
        logger.error(f"Error processing DataForSEO webhook: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "Internal server error",
            "message": str(e)
        }, status=500)