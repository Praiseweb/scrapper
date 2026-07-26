"""
Facebook Automation — Main Entry Point
========================================

Orchestrates the complete Facebook automation workflow:
1. Launch stealth browser
2. Login to Facebook
3. Scrape posts from feed
4. Comment on posts
5. Export results

Usage:
    # Using CLI arguments:
    python -m part3_facebook.main --email your@email.com --password yourpass

    # Using .env file (recommended):
    # Set FACEBOOK_EMAIL and FACEBOOK_PASSWORD in .env
    python -m part3_facebook.main

    # With options:
    python -m part3_facebook.main --max-posts 15 --comment-limit 5 --headless

Note:
    This tool is designed for use with your OWN Facebook account only.
    Built as part of a job assessment for Amazing Properties Wisconsin LLC.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    import os

    load_dotenv()
except ImportError:
    import os

from part3_facebook.browser import BrowserManager
from part3_facebook.scraper import FacebookScraper
from part3_facebook.commenter import FacebookCommenter
from part3_facebook.utils import setup_logger

logger = setup_logger("facebook.main")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Facebook Automation — Scrape posts and post comments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --email user@email.com --password mypass
  %(prog)s --max-posts 10 --comment-limit 3
  %(prog)s --scrape-only
  %(prog)s --headless --output-dir results
        """,
    )

    # Credentials (can also come from .env)
    parser.add_argument(
        "--email",
        default=os.environ.get("FACEBOOK_EMAIL", ""),
        help="Facebook email address (or set FACEBOOK_EMAIL in .env)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("FACEBOOK_PASSWORD", ""),
        help="Facebook password (or set FACEBOOK_PASSWORD in .env)",
    )

    # Scraping options
    parser.add_argument(
        "--max-posts",
        type=int,
        default=int(os.environ.get("MAX_POSTS", "20")),
        help="Maximum number of posts to scrape (default: 20)",
    )
    parser.add_argument(
        "--page-url",
        default=None,
        help="Specific Facebook page URL to scrape (default: news feed)",
    )

    # Commenting options
    parser.add_argument(
        "--comment-limit",
        type=int,
        default=int(os.environ.get("COMMENT_LIMIT", "5")),
        help="Maximum comments to post per session (default: 5)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=float(os.environ.get("MIN_COMMENT_DELAY", "30")),
        help="Minimum seconds between comments (default: 30)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=float(os.environ.get("MAX_COMMENT_DELAY", "120")),
        help="Maximum seconds between comments (default: 120)",
    )

    # Workflow options
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape posts — skip commenting",
    )
    parser.add_argument(
        "--comment-only",
        action="store_true",
        help="Only comment — skip scraping (uses existing posts.json)",
    )

    # Browser options
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (not recommended — easier to detect)",
    )
    parser.add_argument(
        "--state-dir",
        default="browser_state",
        help="Directory for persistent browser state (default: browser_state)",
    )

    # Output options
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output files (default: output)",
    )

    return parser.parse_args()


async def main() -> None:
    """
    Main execution function — orchestrates the full workflow.

    Flow:
        1. Validate credentials
        2. Launch browser with stealth patches
        3. Login to Facebook
        4. Scrape posts from feed/page
        5. Export scraped posts to JSON
        6. Comment on posts (unless --scrape-only)
        7. Export action log
        8. Print summary
    """
    args = parse_args()

    # -----------------------------------------------------------------------
    # Validate credentials
    # -----------------------------------------------------------------------
    if not args.email or not args.password:
        logger.error(
            "Facebook credentials not provided!\n"
            "Set FACEBOOK_EMAIL and FACEBOOK_PASSWORD in .env file, "
            "or pass --email and --password arguments."
        )
        print("\n❌ Error: Facebook credentials required.")
        print("   Option 1: Create a .env file with:")
        print("     FACEBOOK_EMAIL=your@email.com")
        print("     FACEBOOK_PASSWORD=yourpassword")
        print("   Option 2: Pass --email and --password flags")
        sys.exit(1)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Facebook Automation — Starting")
    logger.info("=" * 60)
    logger.info("Max posts: %d", args.max_posts)
    logger.info("Comment limit: %d", args.comment_limit)
    logger.info("Delay range: %.0f-%.0f seconds", args.min_delay, args.max_delay)
    logger.info("Headless: %s", args.headless)
    logger.info("Output dir: %s", output_dir.resolve())

    # -----------------------------------------------------------------------
    # Launch browser and login
    # -----------------------------------------------------------------------
    async with BrowserManager(
        headless=args.headless,
        state_dir=args.state_dir,
    ) as browser:
        page = await browser.login(args.email, args.password)

        scraped_posts = []

        # -------------------------------------------------------------------
        # Phase 1: Scrape posts
        # -------------------------------------------------------------------
        if not args.comment_only:
            logger.info("\n📥 Phase 1: Scraping posts...")
            scraper = FacebookScraper(
                page=page,
                max_posts=args.max_posts,
            )

            if args.page_url:
                scraped_posts = await scraper.scrape_page_posts(args.page_url)
            else:
                scraped_posts = await scraper.scrape_feed_posts()

            # Export scraped posts
            posts_file = scraper.export_json(
                str(output_dir / "facebook_posts.json")
            )
            logger.info("📄 Posts exported to: %s", posts_file)

        else:
            # Load existing posts for comment-only mode
            posts_path = output_dir / "facebook_posts.json"
            if posts_path.exists():
                with open(posts_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scraped_posts = data.get("posts", [])
                logger.info(
                    "Loaded %d posts from %s", len(scraped_posts), posts_path
                )
            else:
                logger.error(
                    "No posts file found at %s — run scraping first.", posts_path
                )
                return

        # -------------------------------------------------------------------
        # Phase 2: Comment on posts
        # -------------------------------------------------------------------
        if not args.scrape_only and scraped_posts:
            logger.info("\n💬 Phase 2: Commenting on posts...")
            commenter = FacebookCommenter(
                page=page,
                min_delay=args.min_delay,
                max_delay=args.max_delay,
                daily_limit=args.comment_limit,
            )

            action_log = await commenter.run_commenting_workflow(
                posts=scraped_posts,
                max_comments=args.comment_limit,
            )

            # Export action log
            log_path = output_dir / "comment_log.json"
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "metadata": {
                            "session_start": datetime.now().isoformat(),
                            "total_actions": commenter.action_count,
                            "daily_limit": args.comment_limit,
                        },
                        "actions": action_log,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            logger.info("📄 Comment log exported to: %s", log_path.resolve())

        elif args.scrape_only:
            logger.info("⏭️  Skipping commenting (--scrape-only mode)")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("📊 SESSION SUMMARY")
    print("=" * 60)
    print(f"  Posts scraped:    {len(scraped_posts)}")
    if not args.scrape_only:
        print(f"  Comments posted:  {commenter.action_count if 'commenter' in dir() else 0}")
    print(f"  Output directory: {output_dir.resolve()}")
    print(f"  Files generated:")

    for f in sorted(output_dir.iterdir()):
        print(f"    📄 {f.name} ({f.stat().st_size:,} bytes)")

    print("=" * 60)
    logger.info("Session complete. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
