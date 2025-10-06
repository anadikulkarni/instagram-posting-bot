# 📲 Instagram Bulk Poster

A Streamlit-based application for posting content to multiple Instagram Business accounts simultaneously. Built with scheduling capabilities, group management, and automated posting workflows.

## Features

### Core Functionality
- **📤 Bulk Posting**: Post images and videos to multiple Instagram accounts at once
- **⏰ Scheduling**: Schedule posts for future publication (processed every 15-20 minutes)
- **👥 Group Management**: Create account groups for easier bulk operations
- **📊 Post Logs**: Track all posting activity with detailed logs
- **🔐 Secure Authentication**: Session-based auth 

### Technical Highlights
- **AWS S3 Integration**: Reliable media storage and delivery
- **Instagram Graph API**: Direct integration with Instagram Business accounts
- **Smart Scheduling**: GitHub Actions-powered automated posting
- **Database-Backed**: PostgreSQL for data persistence
- **Timezone Support**: IST (Asia/Kolkata) timezone handling

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL database (Supabase recommended)
- AWS S3 bucket
- Facebook Developer Account with Instagram Graph API access
- Streamlit Cloud account (for deployment)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/instagram-bulk-poster.git
cd instagram-bulk-poster
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**

Create a `.streamlit/secrets.toml` file (for local development) or configure Streamlit Cloud secrets:

```toml
[supabase]
db_url = "postgresql://user:password@host:port/database"

[fb_access_token]
ACCESS_TOKEN = "your_facebook_page_access_token"

[aws]
access_key_id = "your_aws_access_key"
secret_access_key = "your_aws_secret_key"
bucket_name = "your-s3-bucket-name"
region = "eu-north-1"  # or your preferred region
```

For production deployment, set these as environment variables:
- `DATABASE_URL`
- `FB_ACCESS_TOKEN`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_BUCKET_NAME`
- `AWS_REGION`

4. **Initialize the database**

The application will automatically create required tables on first run. Ensure your database URL is properly configured.

5. **Run the application**
```bash
streamlit run Post.py
```

## Usage

### First-Time Setup

1. **Login**: Use the default credentials 

2. **Connect Instagram Accounts**: The app automatically fetches all Instagram Business accounts linked to your Facebook Pages

3. **Create Groups** (Optional): Navigate to the Groups page to organize accounts into logical groups

### Posting Content

1. **Select Accounts**: Choose individual accounts or groups
2. **Upload Media**: Support for images (PNG, JPG) and videos (MP4, MOV, AVI)
3. **Write Caption**: Add your Instagram caption with hashtags and mentions
4. **Post or Schedule**:
   - **Post Now**: Immediate posting to all selected accounts
   - **Post Later**: Schedule for future publication

### Viewing Logs

Navigate to the **Logs** page to see:
- Post history
- Success/failure status
- Timestamps (in IST)
- Account details

## Architecture

### Project Structure

```
instagram-bulk-poster/
├── Post.py                          # Main application file
├── pages/
│   ├── Groups.py                    # Group management interface
│   └── Logs.py                      # Post logs viewer
├── services/
│   ├── instagram_api.py             # Instagram Graph API integration
│   ├── aws_utils.py                 # AWS S3 operations
│   ├── cloudinary_utils.py          # Legacy Cloudinary support
│   └── scheduler.py                 # Post scheduling logic
├── db/
│   ├── models.py                    # SQLAlchemy ORM models
│   └── utils.py                     # Database utilities
├── utils/
│   ├── auth.py                      # Authentication system
│   └── cache.py                     # Caching utilities
├── .github/workflows/
│   ├── instagram-checker.yml        # Lightweight scheduler checker
│   └── instagram-poster-heavy.yml   # Heavy posting workflow
├── config.py                        # Configuration management
├── smart_checker.py                 # Smart workflow trigger logic
└── requirements.txt                 # Python dependencies
```

### Database Schema

**Groups**: Account group definitions
- `id`, `name`

**GroupAccount**: Group-to-account mappings
- `id`, `group_id`, `ig_id`

**ScheduledPost**: Pending scheduled posts
- `id`, `ig_ids`, `caption`, `media_url`, `scheduled_time`, etc.

**PostLog**: Historical post records
- `id`, `username`, `ig_ids`, `caption`, `results`, `timestamp`

**Session**: User authentication sessions
- `id`, `username`, `session_token`, `expires_at`

**WorkflowLocks**: Prevents concurrent workflow runs
- `lock_name`, `locked_at`, `locked_by`

## Automated Scheduling

The app uses GitHub Actions for reliable scheduled posting:

### How It Works

1. **Smart Checker** (`instagram-checker.yml`):
   - Runs every 15 minutes between 9 AM - 8 PM IST
   - Lightweight check (~2 seconds)
   - Queries database for due posts
   - Triggers heavy workflow only when needed

2. **Heavy Poster** (`instagram-poster-heavy.yml`):
   - Triggered by smart checker or manually
   - Processes all due posts
   - Uses distributed locking to prevent concurrent runs
   - Handles media upload and Instagram API calls

### Setting Up GitHub Actions

1. **Fork/Clone the repository** to your GitHub account

2. **Add GitHub Secrets**:
   Navigate to Settings → Secrets and variables → Actions, and add:
   - `DATABASE_URL`
   - `FB_ACCESS_TOKEN`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_BUCKET_NAME`
   - `AWS_REGION`
   - `PAT_TOKEN` (Personal Access Token with `repo` and `workflow` scopes)

3. **Enable GitHub Actions** in your repository settings

4. **Customize Schedule** (Optional): Edit the cron schedule in `.github/workflows/instagram-checker.yml`

## 🔧 Configuration

### Updating User Credentials

Edit `utils/auth.py`:

```python
USER_CREDENTIALS = {
    "your_username": "your_password",
    "another_user": "another_password"
}
```

For production, consider implementing a proper user management system.

### Adjusting Scheduler Timing

Edit the cron schedule in `.github/workflows/instagram-checker.yml`:

```yaml
schedule:
  - cron: "*/15 5-15 * * *"  # Every 15 min, 9AM-8PM IST
```

### Media Processing Wait Times

Video and image processing times can be adjusted in `services/instagram_api.py`:

```python
if media_type == "video":
    initial_wait = 90      # seconds for first account
    subsequent_wait = 90   # seconds for other accounts
else:
    initial_wait = 15
    subsequent_wait = 5
```

## Security Considerations

- **Access Tokens**: Never commit access tokens to version control
- **Database**: Use SSL connections for production databases
- **AWS**: Follow AWS security best practices (IAM roles, bucket policies)
- **Authentication**: Implement strong password policies and consider OAuth
- **HTTPS**: Always deploy with HTTPS enabled (Streamlit Cloud does this by default)

## Troubleshooting

### Common Issues

**"No Instagram accounts found"**
- Ensure your Facebook Pages are connected to Instagram Business accounts
- Verify your Facebook access token has proper permissions
- Check that token hasn't expired

**"AWS upload failed"**
- Verify AWS credentials are correct
- Ensure S3 bucket exists and is in the specified region
- Check bucket permissions allow public-read ACL

**"Container processing failed"**
- Instagram may be rate-limiting your account
- Try reducing video file size/duration
- Ensure media meets Instagram's requirements

**Scheduled posts not running**
- Check GitHub Actions are enabled
- Verify all secrets are properly configured
- Review workflow run logs in GitHub Actions tab

## API Requirements

### Facebook/Instagram Graph API

Required permissions:
- `pages_show_list`
- `pages_read_engagement`
- `instagram_basic`
- `instagram_content_publish`

Generate a long-lived Page Access Token for production use.

### Instagram Content Requirements

- **Images**: JPG, PNG (aspect ratio 4:5 to 1.91:1)
- **Videos**: MP4, MOV (duration 3-60 seconds for Reels)
- **File Size**: Under 8MB for images, under 100MB for videos
- **Caption**: Up to 2,200 characters

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is provided as-is for educational and personal use. Please ensure compliance with Instagram's Terms of Service and API usage policies.

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Powered by [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- Storage via [AWS S3](https://aws.amazon.com/s3/)
- Automated with [GitHub Actions](https://github.com/features/actions)

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review Instagram Graph API documentation

---

**⚠️ Important**: This tool is for managing your own Instagram Business accounts. Always comply with Instagram's Terms of Service and API usage policies. Excessive posting or automation may result in account restrictions.