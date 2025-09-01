# Server-Sent Events (SSE) Configuration Guide

This guide covers the special configuration needed for Server-Sent Events (SSE) to work properly with Nginx and Cloudflare in production.

## Table of Contents
- [Overview](#overview)
- [Nginx Configuration for SSE](#nginx-configuration-for-sse)
- [Cloudflare Configuration](#cloudflare-configuration)
- [Django Implementation](#django-implementation)
- [Testing SSE](#testing-sse)
- [Troubleshooting](#troubleshooting)
- [Alternative Solutions](#alternative-solutions)

## Overview

Server-Sent Events (SSE) require special configuration because:
- SSE uses long-lived HTTP connections
- Nginx buffers responses by default
- Cloudflare has connection timeout limits
- Proxies may interfere with streaming responses

## Nginx Configuration for SSE

### Update Nginx Configuration

Add this SSE-specific location block to your `/etc/nginx/sites-available/limeclicks` configuration:

```nginx
# SSE endpoints - Add this to your server block
location /sse/ {
    # Disable buffering for SSE
    proxy_buffering off;
    proxy_cache off;
    
    # Disable Nginx buffering
    proxy_read_timeout 86400s;  # 24 hours
    proxy_send_timeout 86400s;
    
    # SSE specific headers
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    
    # Important: Tell Nginx this is an event stream
    proxy_set_header X-Accel-Buffering no;
    
    # Standard proxy headers
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Pass to Gunicorn
    proxy_pass http://limeclicks_app;
    
    # SSE keep-alive settings
    keepalive_timeout 0;
    keepalive_requests 0;
    
    # Immediately flush data to client
    gzip off;
    
    # Access log for debugging (optional)
    access_log /var/log/nginx/sse_access.log;
}

# Alternative: For all API streaming endpoints
location ~ ^/api/.*/(stream|sse|events)$ {
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header X-Accel-Buffering no;
    proxy_read_timeout 86400s;
    chunked_transfer_encoding off;
    
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_pass http://limeclicks_app;
    
    gzip off;
}
```

### Complete Nginx SSE Configuration File

Create `/etc/nginx/sites-available/limeclicks-sse.conf`:

```nginx
upstream limeclicks_app {
    server unix:/home/limeclicks/limeclicks/gunicorn.sock fail_timeout=0;
    keepalive 32;  # Keep connections alive for SSE
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    # ... SSL configuration ...
    
    # Special handling for SSE endpoints
    location /sse/ {
        # Critical SSE settings
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
        proxy_send_timeout 24h;
        keepalive_timeout 24h;
        send_timeout 24h;
        
        # Disable compression for SSE
        gzip off;
        
        # SSE headers
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        proxy_set_header X-Accel-Buffering no;
        proxy_set_header Cache-Control no-cache;
        
        # Standard headers
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Pass to app
        proxy_pass http://limeclicks_app;
        
        # Immediately send data
        tcp_nodelay on;
        tcp_nopush off;
    }
    
    # Regular application routes
    location / {
        # ... standard configuration ...
    }
}
```

## Cloudflare Configuration

### Important Cloudflare Limitations

Cloudflare has specific limitations for SSE:
- **Free/Pro/Business plans**: 100 seconds timeout
- **Enterprise plan**: Can be configured up to 600 seconds
- Cloudflare buffers responses until it receives enough data

### Option 1: Bypass Cloudflare for SSE (Recommended)

Create a subdomain that bypasses Cloudflare:

1. **Create subdomain**: `sse.yourdomain.com`
2. **DNS Settings**: Set to "DNS only" (gray cloud) not "Proxied" (orange cloud)
3. **Point directly to your server IP**

Update Nginx to handle SSE subdomain:

```nginx
server {
    listen 443 ssl http2;
    server_name sse.yourdomain.com;
    
    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/sse.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sse.yourdomain.com/privkey.pem;
    
    # Only handle SSE endpoints
    location / {
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        proxy_set_header X-Accel-Buffering no;
        
        # CORS headers if needed
        add_header Access-Control-Allow-Origin "https://yourdomain.com" always;
        add_header Access-Control-Allow-Credentials true always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;
        
        if ($request_method = OPTIONS) {
            return 204;
        }
        
        proxy_pass http://limeclicks_app;
    }
}
```

### Option 2: Configure Cloudflare for SSE

If you must use Cloudflare for SSE:

1. **Page Rules** (Business plan or higher):
   - URL: `*yourdomain.com/sse/*`
   - Settings:
     - Cache Level: Bypass
     - Disable Performance
     - Disable Security

2. **Workers** (Paid plans):
   Create a Cloudflare Worker to handle SSE:

```javascript
// Cloudflare Worker for SSE
addEventListener('fetch', event => {
  event.respondWith(handleSSE(event.request))
})

async function handleSSE(request) {
  // Check if this is an SSE endpoint
  const url = new URL(request.url)
  if (!url.pathname.startsWith('/sse/')) {
    return fetch(request)
  }
  
  // Forward request to origin
  const response = await fetch(request, {
    cf: {
      // Disable caching
      cacheTtl: 0,
      // Disable Cloudflare features
      mirage: false,
      polish: false,
      minify: false,
      apps: false
    }
  })
  
  // Return response with SSE headers
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: {
      ...response.headers,
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no'
    }
  })
}
```

3. **Transform Rules** (if available):
   - Create rule for `/sse/*` paths
   - Disable Auto Minify
   - Disable Rocket Loader
   - Disable Email Obfuscation

## Django Implementation

### Django View for SSE

```python
# views.py
import json
import time
from django.http import StreamingHttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

@never_cache
@csrf_exempt  # Only if necessary
def sse_stream(request):
    """
    SSE endpoint for real-time updates
    """
    def event_stream():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE connection established'})}\n\n"
        
        # Keep connection alive
        while True:
            try:
                # Your logic to get new data
                data = get_latest_updates()  # Your function
                
                if data:
                    # Format as SSE
                    event = f"data: {json.dumps(data)}\n\n"
                    yield event
                else:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                
                # Sleep to prevent overwhelming
                time.sleep(1)
                
            except GeneratorExit:
                # Client disconnected
                break
            except Exception as e:
                # Send error event
                error_event = f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                yield error_event
                break
    
    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    
    # Important headers for SSE
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'  # Configure as needed
    
    return response

# Alternative with async support (Django 4.1+)
import asyncio
from django.http import StreamingHttpResponse

async def async_sse_stream(request):
    async def event_generator():
        while True:
            try:
                # Async data fetching
                data = await get_latest_updates_async()
                
                if data:
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    yield ": heartbeat\n\n"
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
    
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    
    return response
```

### URLs Configuration

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('sse/updates/', views.sse_stream, name='sse_updates'),
    path('sse/notifications/', views.async_sse_stream, name='sse_notifications'),
]
```

### Frontend JavaScript Client

```javascript
// SSE Client Implementation
class SSEClient {
    constructor(url, options = {}) {
        this.url = url;
        this.eventSource = null;
        this.reconnectDelay = options.reconnectDelay || 5000;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectAttempts = 0;
        this.handlers = {};
    }
    
    connect() {
        // Use subdomain if configured
        const sseUrl = this.url.startsWith('http') 
            ? this.url 
            : `${window.location.protocol}//sse.${window.location.host}${this.url}`;
        
        this.eventSource = new EventSource(sseUrl, {
            withCredentials: true  // If using cookies
        });
        
        this.eventSource.onopen = (event) => {
            console.log('SSE Connected');
            this.reconnectAttempts = 0;
            this.onConnect(event);
        };
        
        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('SSE Parse Error:', e);
            }
        };
        
        this.eventSource.onerror = (event) => {
            console.error('SSE Error:', event);
            this.handleError(event);
            
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.reconnect();
            }
        };
    }
    
    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.onMaxReconnectReached();
            return;
        }
        
        this.reconnectAttempts++;
        console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectDelay * this.reconnectAttempts);
    }
    
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
    
    on(event, handler) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(handler);
    }
    
    handleMessage(data) {
        const handlers = this.handlers[data.type] || [];
        handlers.forEach(handler => handler(data));
        
        // Global handler
        if (this.handlers['*']) {
            this.handlers['*'].forEach(handler => handler(data));
        }
    }
    
    handleError(error) {
        if (this.handlers['error']) {
            this.handlers['error'].forEach(handler => handler(error));
        }
    }
    
    onConnect(event) {
        if (this.handlers['connect']) {
            this.handlers['connect'].forEach(handler => handler(event));
        }
    }
    
    onMaxReconnectReached() {
        if (this.handlers['maxReconnect']) {
            this.handlers['maxReconnect'].forEach(handler => handler());
        }
    }
}

// Usage
const sseClient = new SSEClient('/sse/updates/');

sseClient.on('connect', () => {
    console.log('Connected to SSE');
});

sseClient.on('update', (data) => {
    console.log('Received update:', data);
    // Update UI
});

sseClient.on('error', (error) => {
    console.error('SSE Error:', error);
    // Show error to user
});

sseClient.connect();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    sseClient.disconnect();
});
```

## Testing SSE

### 1. Test Without Proxy

```bash
# Direct test to Gunicorn
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse/updates/
```

### 2. Test Through Nginx

```bash
# Test through Nginx
curl -N -H "Accept: text/event-stream" https://yourdomain.com/sse/updates/
```

### 3. Test SSE Response Headers

```bash
# Check headers
curl -I -H "Accept: text/event-stream" https://yourdomain.com/sse/updates/
```

Expected headers:
```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

### 4. Browser DevTools Test

```javascript
// In browser console
const es = new EventSource('/sse/updates/');
es.onmessage = (e) => console.log('Message:', e.data);
es.onerror = (e) => console.error('Error:', e);
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Drops After 100 Seconds
**Issue**: Cloudflare timeout
**Solution**: Use subdomain bypass or implement reconnection logic

#### 2. No Data Received
**Issue**: Nginx buffering
**Solution**: Ensure `proxy_buffering off` and `X-Accel-Buffering no`

#### 3. CORS Errors
**Issue**: Cross-origin requests blocked
**Solution**: Add proper CORS headers in Django and Nginx

#### 4. Memory Leaks
**Issue**: Connections not properly closed
**Solution**: Implement connection cleanup and limits

```python
# Django - Limit concurrent connections
from django.core.cache import cache
from django.http import HttpResponse

MAX_SSE_CONNECTIONS = 100

def sse_stream(request):
    user_id = request.user.id
    connection_key = f"sse_connection_{user_id}"
    
    # Check connection limit
    active_connections = cache.get('sse_connections', 0)
    if active_connections >= MAX_SSE_CONNECTIONS:
        return HttpResponse('Too many connections', status=503)
    
    # Increment connection count
    cache.incr('sse_connections')
    
    try:
        # ... SSE logic ...
        pass
    finally:
        # Decrement on disconnect
        cache.decr('sse_connections')
```

#### 5. Testing Tips

```bash
# Monitor active connections
ss -tan | grep :443 | wc -l

# Check Nginx error logs
tail -f /var/log/nginx/error.log

# Monitor memory usage
htop

# Test with curl and verbose output
curl -v -N -H "Accept: text/event-stream" https://yourdomain.com/sse/updates/
```

## Alternative Solutions

### 1. WebSockets (If SSE doesn't meet requirements)

```python
# Using Django Channels for WebSockets
# Install: pip install channels channels-redis

# routing.py
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/updates/', consumers.UpdateConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': URLRouter(websocket_urlpatterns),
})
```

### 2. Long Polling Fallback

```javascript
// Fallback to long polling if SSE fails
class RealtimeClient {
    constructor(url) {
        this.url = url;
        this.useSSE = typeof EventSource !== 'undefined';
        this.polling = false;
    }
    
    connect() {
        if (this.useSSE) {
            try {
                this.connectSSE();
            } catch (e) {
                console.log('SSE failed, falling back to polling');
                this.startPolling();
            }
        } else {
            this.startPolling();
        }
    }
    
    connectSSE() {
        // SSE implementation
    }
    
    startPolling() {
        this.polling = true;
        this.poll();
    }
    
    async poll() {
        while (this.polling) {
            try {
                const response = await fetch(this.url);
                const data = await response.json();
                this.handleData(data);
                
                // Wait before next poll
                await new Promise(resolve => setTimeout(resolve, 5000));
            } catch (e) {
                console.error('Polling error:', e);
                await new Promise(resolve => setTimeout(resolve, 10000));
            }
        }
    }
}
```

### 3. Using Pusher or Similar Services

For production systems with high SSE requirements, consider:
- Pusher
- Ably
- PubNub
- Firebase Realtime Database
- AWS IoT Core

These services handle the infrastructure complexity and work well with Cloudflare.

## Production Checklist

- [ ] Configure Nginx with `proxy_buffering off`
- [ ] Set `X-Accel-Buffering: no` header
- [ ] Implement heartbeat/keepalive
- [ ] Add reconnection logic in frontend
- [ ] Set up monitoring for SSE connections
- [ ] Configure connection limits
- [ ] Implement proper error handling
- [ ] Test with Cloudflare enabled/disabled
- [ ] Document SSE endpoints
- [ ] Set up alerting for connection issues

## Performance Considerations

1. **Connection Limits**: Monitor and limit concurrent SSE connections
2. **Memory Usage**: Each connection uses memory, plan accordingly
3. **CPU Usage**: Implement efficient data polling
4. **Network**: Consider bandwidth usage for many connections
5. **Database**: Avoid querying DB for each connection continuously

## Security Considerations

1. **Authentication**: Implement proper authentication for SSE endpoints
2. **Rate Limiting**: Prevent abuse with rate limits
3. **Input Validation**: Validate any data sent through SSE
4. **CORS**: Configure CORS properly for cross-origin requests
5. **SSL/TLS**: Always use HTTPS for SSE in production