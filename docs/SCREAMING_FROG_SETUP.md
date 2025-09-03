# Screaming Frog SEO Spider Integration

## Overview
This document describes the Screaming Frog SEO Spider CLI integration for the LimeClicks site audit system.

## License Configuration

### Environment Variable Setup
The system uses the `SCREAMING_FROG_LICENSE` environment variable to manage the license:

```bash
export SCREAMING_FROG_LICENSE="Your Name-XXXX-XXXX-XXXX"
```

### URL Limits
- **Free Version**: Hard limit of 500 URLs
- **Licensed Version**: No URL limit (or as per license terms)
- **Important**: Command-line parameters like `--max-urls` do NOT work
- **Important**: Config files (XML or text) are NOT accepted in headless mode

## How It Works

1. **License Detection**: The system automatically detects the license from the environment variable
2. **Automatic Limit Management**: The license itself manages URL limits without any explicit configuration
3. **No Config Files**: The headless mode doesn't accept config files - everything runs via command-line
4. **Simplified Command**: Uses minimal command structure for reliability

## Production Configuration

### Required Setup
1. Install Screaming Frog SEO Spider (usually at `/usr/bin/screamingfrogseospider`)
2. Set the `SCREAMING_FROG_LICENSE` environment variable
3. Ensure the user running the application has execute permissions

### Verification
Run the production verification test:
```bash
python test_production_crawl.py
```

This will verify:
- License is properly configured
- Screaming Frog executable is found
- Crawl completes successfully
- Results are parsed correctly

## Key Files

- `site_audit/screaming_frog.py` - Main integration class
- `test_production_crawl.py` - Production verification test
- `test_url_limit.py` - URL limit testing
- `test_simple_limit.py` - Simple crawl test

## Important Notes

1. **Do NOT use config files** - They don't work in headless mode
2. **Do NOT use --max-urls parameter** - It's not functional
3. **The license is the only way to control URL limits**
4. **The max_pages parameter in code is for tracking only** - actual limit is determined by license

## Troubleshooting

### Common Issues

1. **"Unrecognized option: --max-urls"**
   - Solution: Remove the parameter, it doesn't work

2. **"Config file isn't a crawl config file"**
   - Solution: Remove config file usage entirely

3. **"Failed to load config: invalid stream header"**
   - Solution: Don't use XML config files in headless mode

4. **Crawl stops at 500 URLs**
   - Solution: Ensure SCREAMING_FROG_LICENSE environment variable is set

## Migration from Database License Storage

Previously, the system stored licenses in the database using the `ScreamingFrogLicense` model. This has been removed in favor of environment variables for better security and deployment flexibility.

### Migration Steps:
1. Remove the `ScreamingFrogLicense` model and migrations
2. Set the `SCREAMING_FROG_LICENSE` environment variable
3. Update deployment configurations to include the environment variable

## Testing

### Quick Test
```bash
python test_simple_limit.py
```

### Full Test
```bash
python test_url_limit.py
```

### Production Verification
```bash
python test_production_crawl.py
```

## Security Notes

- Never commit the license key to version control
- Use environment variables or secret management systems
- The license key format includes the licensee name and key segments

## Support

For issues with the Screaming Frog integration, check:
1. License is valid and properly set
2. Executable has correct permissions
3. Temporary directories are writable
4. Review the logs in the Django application