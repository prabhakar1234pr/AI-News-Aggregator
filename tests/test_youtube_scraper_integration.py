"""
Integration tests for YouTube Scraper using real YouTube links.

These tests require internet connection and may fail if:
- YouTube is unavailable
- Network issues occur
- Rate limiting is triggered
- Videos/channels are removed or made private

Run with: pytest tests/test_youtube_scraper_integration.py -v
Skip with: pytest tests/test_youtube_scraper_integration.py -m "not integration"
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from datetime import datetime, timedelta
from app.scrapers.Youtube_Scraper import YouTubeScraper, VideoInfo, Transcript


# Real YouTube channel IDs for testing
# Google Developers channel - active channel with regular uploads
GOOGLE_DEVELOPERS_CHANNEL_ID = "UC_x5XG1OV2P6uZZ5FSM9Ttw"

# Real YouTube video URLs with transcripts available
# Using popular videos that are likely to have transcripts
TEST_VIDEO_WITH_TRANSCRIPT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video
TEST_VIDEO_WITH_TRANSCRIPT_2 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Popular video with transcript


@pytest.fixture
def youtube_scraper():
    """Create a YouTube scraper instance for testing"""
    return YouTubeScraper(channel_id=GOOGLE_DEVELOPERS_CHANNEL_ID)


@pytest.fixture
def youtube_scraper_no_channel():
    """Create a YouTube scraper without channel (for transcript-only tests)"""
    return YouTubeScraper(rss_url="https://www.youtube.com/feeds/videos.xml?channel_id=dummy")


@pytest.mark.integration
class TestYouTubeScraperIntegration:
    """Integration tests using real YouTube data"""

    def test_build_rss_url_with_real_channel_id(self, youtube_scraper):
        """Test RSS URL building with real channel ID"""
        url = youtube_scraper._build_rss_url()
        assert "channel_id=" in url
        assert GOOGLE_DEVELOPERS_CHANNEL_ID in url
        assert url.startswith("https://www.youtube.com/feeds/videos.xml")

    def test_extract_video_id_from_real_url(self):
        """Test video ID extraction from real YouTube URLs"""
        test_cases = [
            ("https://www.youtube.com/watch?v=jNQXAC9IVRw", "jNQXAC9IVRw"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=jNQXAC9IVRw&feature=share", "jNQXAC9IVRw"),
        ]
        
        for url, expected_id in test_cases:
            video_id = YouTubeScraper._extract_video_id(url)
            assert video_id == expected_id, f"Failed for URL: {url}"

    @pytest.mark.slow
    def test_parse_feed_with_real_channel(self, youtube_scraper):
        """Test parsing RSS feed from real YouTube channel"""
        feed = youtube_scraper._parse_feed()
        
        assert feed is not None
        assert hasattr(feed, 'entries')
        assert len(feed.entries) > 0, "Feed should contain at least one entry"
        
        # Check first entry structure
        first_entry = feed.entries[0]
        assert hasattr(first_entry, 'title')
        assert hasattr(first_entry, 'link')
        assert 'youtube.com' in first_entry.link

    @pytest.mark.slow
    def test_get_latest_video_from_real_channel(self, youtube_scraper):
        """Test getting latest video from real YouTube channel"""
        latest_video = youtube_scraper.get_latest_video()
        
        assert latest_video is not None, "Should return a video"
        assert isinstance(latest_video, VideoInfo)
        assert latest_video.title is not None and len(latest_video.title) > 0
        assert latest_video.url is not None
        assert latest_video.video_id is not None
        assert latest_video.published_at is not None
        assert isinstance(latest_video.published_at, datetime)
        
        # Verify video URL is valid
        assert 'youtube.com' in latest_video.url or 'youtu.be' in latest_video.url

    @pytest.mark.slow
    def test_get_videos_last_24_hours_from_real_channel(self, youtube_scraper):
        """Test getting videos from last 24 hours from real channel"""
        videos = youtube_scraper.get_videos_last_24_hours()
        
        assert isinstance(videos, list)
        # Note: May be empty if channel hasn't uploaded in last 24 hours
        
        # If videos exist, verify their structure
        for video in videos:
            assert isinstance(video, VideoInfo)
            assert video.title is not None
            assert video.url is not None
            assert video.published_at is not None
            
            # Verify published date is within last 24 hours
            time_diff = datetime.now(video.published_at.tzinfo if hasattr(video.published_at, 'tzinfo') else None) - video.published_at
            assert time_diff <= timedelta(hours=24), "Video should be from last 24 hours"

    @pytest.mark.slow
    def test_get_transcript_from_real_video(self, youtube_scraper_no_channel):
        """Test getting transcript from real YouTube video with transcript"""
        # Using a well-known video that should have transcripts
        transcript = youtube_scraper_no_channel.get_transcript(TEST_VIDEO_WITH_TRANSCRIPT)
        
        # Note: Transcript may be None if video doesn't have one
        # This is acceptable behavior
        if transcript is not None:
            assert isinstance(transcript, Transcript)
            assert transcript.video_id is not None
            assert transcript.text is not None
            assert len(transcript.text) > 0, "Transcript text should not be empty"
            assert transcript.language is not None
            assert isinstance(transcript.segments, list)
            assert len(transcript.segments) > 0, "Should have at least one segment"
            
            # Verify segment structure
            for segment in transcript.segments:
                assert 'text' in segment
                assert 'start' in segment
                assert 'duration' in segment

    @pytest.mark.slow
    def test_get_transcript_with_language_preference(self, youtube_scraper_no_channel):
        """Test getting transcript with specific language preference"""
        transcript = youtube_scraper_no_channel.get_transcript(
            TEST_VIDEO_WITH_TRANSCRIPT,
            languages=['en']
        )
        
        # May be None if transcript not available
        if transcript is not None:
            assert transcript.language in ['en', 'en-US', 'en-GB'], \
                f"Expected English transcript, got {transcript.language}"

    @pytest.mark.slow
    def test_get_channel_info_from_real_channel(self, youtube_scraper):
        """Test getting channel information from real YouTube channel"""
        channel_info = youtube_scraper.get_channel_info()
        
        assert channel_info is not None
        assert isinstance(channel_info, dict)
        assert 'title' in channel_info
        assert 'link' in channel_info
        assert len(channel_info['title']) > 0, "Channel title should not be empty"
        assert 'youtube.com' in channel_info['link'] or channel_info['link'] == ''

    @pytest.mark.slow
    def test_parse_video_entry_from_real_feed(self, youtube_scraper):
        """Test parsing video entry from real RSS feed"""
        feed = youtube_scraper._parse_feed()
        
        if len(feed.entries) > 0:
            entry = feed.entries[0]
            video_info = youtube_scraper._parse_video_entry(entry)
            
            assert isinstance(video_info, VideoInfo)
            assert video_info.title is not None
            assert video_info.url is not None
            assert video_info.video_id is not None
            assert video_info.published_at is not None

    @pytest.mark.slow
    def test_get_transcript_handles_missing_transcript_gracefully(self, youtube_scraper_no_channel):
        """Test that missing transcripts are handled gracefully"""
        # Using a video ID that likely doesn't exist or has no transcript
        # This should return None without raising an exception
        transcript = youtube_scraper_no_channel.get_transcript(
            "https://www.youtube.com/watch?v=invalid_video_id_12345"
        )
        
        # Should return None for invalid/missing transcripts
        assert transcript is None or isinstance(transcript, Transcript)

    @pytest.mark.slow
    def test_scraper_with_different_channel_formats(self):
        """Test scraper initialization with different channel identifier formats"""
        # Test with channel ID
        scraper1 = YouTubeScraper(channel_id=GOOGLE_DEVELOPERS_CHANNEL_ID)
        assert scraper1.rss_url is not None
        
        # Test with RSS URL directly
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={GOOGLE_DEVELOPERS_CHANNEL_ID}"
        scraper2 = YouTubeScraper(rss_url=rss_url)
        assert scraper2.rss_url == rss_url

    @pytest.mark.slow
    def test_multiple_videos_from_channel(self, youtube_scraper):
        """Test retrieving multiple videos from a real channel"""
        videos = youtube_scraper.get_videos_last_24_hours()
        
        # May be empty, but if videos exist, verify we can get details
        if len(videos) > 0:
            for video in videos[:3]:  # Test first 3 videos
                assert video.title is not None
                assert video.url is not None
                assert video.video_id is not None
                
                # Verify video ID extraction works
                extracted_id = YouTubeScraper._extract_video_id(video.url)
                assert extracted_id == video.video_id


@pytest.mark.integration
class TestYouTubeScraperEdgeCases:
    """Test edge cases with real YouTube data"""

    @pytest.mark.slow
    def test_get_transcript_with_fallback_languages(self, youtube_scraper_no_channel):
        """Test transcript retrieval with fallback languages"""
        transcript = youtube_scraper_no_channel.get_transcript(
            TEST_VIDEO_WITH_TRANSCRIPT,
            languages=['es', 'fr'],  # Try non-English first
            fallback_languages=['en']  # Fallback to English
        )
        
        # Should work with fallback
        if transcript is not None:
            assert transcript.text is not None
            assert len(transcript.text) > 0

    @pytest.mark.slow
    def test_video_id_extraction_edge_cases(self):
        """Test video ID extraction with various URL formats"""
        test_cases = [
            ("https://www.youtube.com/watch?v=jNQXAC9IVRw&t=10s", "jNQXAC9IVRw"),        
            ("https://youtu.be/dQw4w9WgXcQ?t=30", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/jNQXAC9IVRw", "jNQXAC9IVRw"),
        ]
        
        for input_value, expected_id in test_cases:
            video_id = YouTubeScraper._extract_video_id(input_value)
            assert video_id == expected_id, f"Failed for input: {input_value}"



