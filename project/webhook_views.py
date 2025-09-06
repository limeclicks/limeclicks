"""
DataForSEO webhook handler views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .tasks import process_dataforseo_webhook

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST", "HEAD"])
def dataforseo_webhook(request):
    """
    Handle webhook callbacks from DataForSEO
    
    GET request (pingback): Lightweight notification with task_id in query params
    POST request (postback): Full task results in request body
    HEAD request: Connectivity check from DataForSEO
    """
    try:
        # Handle HEAD request (connectivity check)
        if request.method == 'HEAD':
            return JsonResponse({"status": "ok"})
        
        # Extract task_id from query params (for both GET and POST)
        task_id = request.GET.get('task_id')
        
        # Handle GET request (pingback)
        if request.method == 'GET':
            # If no task_id, this might be a connectivity check
            if not task_id:
                logger.info("Received GET request without task_id - treating as connectivity check")
                return JsonResponse({"status": "ok", "message": "Webhook endpoint is active"})
            
            logger.info(f"Received DataForSEO pingback for task: {task_id}")
            
            # Process the webhook with just the task_id
            process_dataforseo_webhook.delay(task_id, {})
            
            return JsonResponse({
                "status": "received",
                "task_id": task_id,
                "type": "pingback",
                "message": "Pingback received and queued for processing"
            })
        
        # Handle POST request (postback)
        webhook_data = {}
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
        if not task_id:
            task_id = webhook_data.get('task_id')
        
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