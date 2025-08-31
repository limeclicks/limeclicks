# R2 CORS Configuration for Performance Tab

The Performance tab needs to fetch PageSpeed Insights data stored in R2. For this to work, you need to configure CORS on your R2 bucket.

## Required CORS Configuration

Add this CORS policy to your R2 bucket:

```json
[
  {
    "AllowedOrigins": [
      "*"
    ],
    "AllowedMethods": [
      "GET",
      "HEAD"
    ],
    "AllowedHeaders": [
      "*"
    ],
    "ExposeHeaders": [
      "ETag"
    ],
    "MaxAgeSeconds": 3600
  }
]
```

## How to Apply CORS Configuration

### Using Cloudflare Dashboard:
1. Go to R2 in your Cloudflare dashboard
2. Select your bucket
3. Go to Settings → CORS
4. Add the above configuration

### Using Wrangler CLI:
```bash
# Create a cors.json file with the above configuration
wrangler r2 bucket cors put <BUCKET_NAME> --file cors.json
```

### Using AWS CLI (with R2 endpoint):
```bash
aws s3api put-bucket-cors \
  --bucket <BUCKET_NAME> \
  --cors-configuration file://cors.json \
  --endpoint-url <R2_ENDPOINT_URL>
```

## Security Note

For production, you should restrict `AllowedOrigins` to your specific domain(s) instead of using `*`:

```json
"AllowedOrigins": [
  "https://yourdomain.com",
  "https://www.yourdomain.com"
]
```

## Troubleshooting

If you're still getting CORS errors after applying the configuration:

1. Check browser console for specific CORS error messages
2. Verify the presigned URLs are being generated correctly
3. Clear browser cache and try again
4. Check if the R2 bucket is public or requires authentication
5. Verify the CORS configuration was applied successfully

## Alternative Solution

If CORS configuration is not possible, you can create a proxy endpoint in your Django application that fetches the data server-side and returns it to the client.