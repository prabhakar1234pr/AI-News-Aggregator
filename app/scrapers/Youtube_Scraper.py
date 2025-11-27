"""YouTube scraper with RSS feed and transcript support"""

import logging
from datetime import datetime, timedelta ,timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    RequestBlocked,
    IpBlocked
)

logger = logging.getLogger(__name__)

@dataclass
class VideoInfo:
    """Data class for video information"""
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    channel_name: str
    duration: Optional[str] = None

@dataclass
class Transcript:
    """Data class for video transcript"""
    video_id: str
    text: str
    language: str
    segments: List[Dict[str, Any]]


class YouTubeScraper:
    """
    Professional YouTube scraper with RSS feed support and transcript retrieval.
    
    Features:
    - Get latest video from channel
    - Get all videos from last 24 hours
    - Retrieve video transcripts
    - Comprehensive error handling and fallbacks
    """

    def __init__(
        self,
        channel_id: Optional[str] = None,
        channel_username: Optional[str] = None,
        rss_url: Optional[str] = None,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize YouTube scraper.
        
        Args:
            channel_id: YouTube channel ID (e.g., 'UC...')
            channel_username: YouTube channel username (e.g., '@channelname')
            rss_url: Direct RSS feed URL (takes precedence)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            
        Raises:
            ValueError: If no valid channel identifier is provided
        """

        self.channel_id = channel_id
        self.channel_username = channel_username
        self.rss_url = rss_url or self._build_rss_url()
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Initialize YouTube Transcript API instance
        self._transcript_api = YouTubeTranscriptApi()
        
        if not self.rss_url:
            raise ValueError(
                "Must provide either channel_id, channel_username, or rss_url"
            )
        
        logger.info(f"Initialized YouTubeScraper with RSS URL: {self.rss_url}")

    def _build_rss_url(self) -> str:
        """Build RSS URL from channel identifier"""

        if self.channel_id:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"

        if self.channel_username:
            # Remove @ if present
            username = self.channel_username.lstrip('@')
            return f"https://www.youtube.com/feeds/videos.xml?user={username}"

        return

    def _parse_feed(self) -> feedparser.FeedParserDict:
        """
        Parse RSS feed with retry logic.
        
        Returns:
            Parsed feed object
            
        Raises:
            requests.RequestException: If feed cannot be retrieved after retries
            ValueError: If feed is invalid or empty
        """
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Fetching RSS feed (attempt {attempt + 1}/{self.max_retries})")
                feed = feedparser.parse(self.rss_url)
                
                if feed.bozo and feed.bozo_exception:
                    raise ValueError(f"Invalid RSS feed: {feed.bozo_exception}")
                
                if not feed.entries:
                    raise ValueError("RSS feed contains no entries")
                
                logger.info(f"Successfully parsed feed with {len(feed.entries)} entries")
                return feed
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to parse feed after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                continue
        
        raise requests.RequestException("Failed to fetch RSS feed")

    def _parse_video_entry(self, entry: feedparser.FeedParserDict) -> VideoInfo:
        """Parse a single feed entry into VideoInfo"""
        video_id = entry.yt_videoid if hasattr(entry, 'yt_videoid') else self._extract_video_id(entry.link)
        
        # Parse published date
        published_at = datetime.now(timezone.utc)
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_at = datetime(*entry.published_parsed[:6])
        
        return VideoInfo(
            title=entry.title,
            url=entry.link,
            video_id=video_id,
            published_at=published_at,
            description=entry.get('summary', ''),
            channel_name=entry.get('author', 'Unknown Channel')
        )

    @staticmethod
    def _extract_video_id(url: str) -> str:
        """Extract video ID from YouTube URL"""
        import re
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract video ID from URL: {url}")

    def get_latest_video(self) -> Optional[VideoInfo]:
        """
        Get the latest video from the channel.
        
        Returns:
            VideoInfo object for the latest video, or None if no videos found
            
        Example:
            >>> scraper = YouTubeScraper(channel_id="UC...")
            >>> latest = scraper.get_latest_video()
            >>> print(latest.title)
        """
        try:
            feed = self._parse_feed()
            
            if not feed.entries:
                logger.warning("No videos found in feed")
                return None
            
            latest_entry = feed.entries[0]  # Feed is sorted by date, newest first
            video_info = self._parse_video_entry(latest_entry)
            
            logger.info(f"Retrieved latest video: {video_info.title}")
            return video_info
            
        except Exception as e:
            logger.error(f"Error retrieving latest video: {e}", exc_info=True)
            return None
    

    def get_videos_last_24_hours(self) -> List[VideoInfo]:
        """
        Get all videos published in the last 24 hours.

        Returns:
            List of VideoInfo objects for videos from last 24 hours
            
        Example:
            >>> scraper = YouTubeScraper(channel_id="UC...")
            >>> videos = scraper.get_videos_last_24_hours()
            >>> print(f"Found {len(videos)} videos")
        """
        try:
            feed = self._parse_feed()
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
            
            videos = []
            for entry in feed.entries:
                try:
                    video_info = self._parse_video_entry(entry)
                    
                    # Check if video is within last 24 hours
                    if video_info.published_at >= cutoff_time:
                        videos.append(video_info)
                    else:
                        # Feed is sorted, so we can break early
                        break
                        
                except Exception as e:
                    logger.warning(f"Error parsing video entry: {e}")
                    continue
            
            logger.info(f"Found {len(videos)} videos from last 24 hours")
            return videos

        except Exception as e:
            logger.error(f"Error retrieving videos from last 24 hours: {e}", exc_info=True)
            return []

    
    def get_transcript(
        self,
        video_url: str,
        languages: Optional[List[str]] = None,
        fallback_languages: Optional[List[str]] = None
    ) -> Optional[Transcript]:
        """
        Get transcript for a YouTube video.
        
        Args:
            video_url: YouTube video URL or video ID
            languages: Preferred language codes (e.g., ['en', 'es'])
            fallback_languages: Fallback language codes if preferred not available
            
        Returns:
            Transcript object, or None if transcript cannot be retrieved
            
        Example:
            >>> scraper = YouTubeScraper()
            >>> transcript = scraper.get_transcript("https://youtube.com/watch?v=...")
            >>> print(transcript.text[:100])
        """


        try:
            # Extract video ID if URL provided
            if 'youtube.com' in video_url or 'youtu.be' in video_url:
                video_id = self._extract_video_id(video_url)
            else:
                video_id = video_url  # Assume it's already a video ID
            
            # Default language preferences
            if languages is None:
                languages = ['en']
            if fallback_languages is None:
                fallback_languages = ['en', 'en-US', 'en-GB']
            
            logger.debug(f"Fetching transcript for video {video_id}")
            
            # Try preferred languages first
            fetched_transcript = None
            for lang in languages:
                try:
                    fetched_transcript = self._transcript_api.fetch(
                        video_id,
                        languages=[lang]
                    )
                    logger.info(f"Retrieved transcript in {lang}")
                    break
                except (TranscriptsDisabled, NoTranscriptFound):
                    continue
            
            # Try fallback languages
            if fetched_transcript is None:
                for lang in fallback_languages:
                    if lang in languages:
                        continue  # Already tried
                    try:
                        fetched_transcript = self._transcript_api.fetch(
                            video_id,
                            languages=[lang]
                        )
                        logger.info(f"Retrieved transcript in fallback language {lang}")
                        break
                    except (TranscriptsDisabled, NoTranscriptFound):
                        continue
            
            if fetched_transcript is None:
                logger.warning(f"No transcript available for video {video_id}")
                return None
            
            # Extract text from FetchedTranscript snippets
            full_text = ' '.join([snippet.text for snippet in fetched_transcript.snippets])
            
            # Convert snippets to list of dicts for segments
            segments = [
                {
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                }
                for snippet in fetched_transcript.snippets
            ]
            
            return Transcript(
                video_id=video_id,
                text=full_text,
                language=fetched_transcript.language_code,
                segments=segments
            )
            
        except VideoUnavailable:
            logger.error(f"Video {video_url} is unavailable")
            return None
        except (RequestBlocked, IpBlocked):
            logger.error("YouTube API rate limit exceeded or IP blocked")
            return None
        except Exception as e:
            logger.error(f"Error retrieving transcript: {e}", exc_info=True)
            return None


    def get_channel_info(self) -> Optional[Dict[str, Any]]:
        """
        Get basic channel information from RSS feed.
        
        Returns:
            Dictionary with channel information, or None if unavailable
        """
        try:
            feed = self._parse_feed()
            return {
                'title': feed.feed.get('title', 'Unknown'),
                'link': feed.feed.get('link', ''),
                'description': feed.feed.get('description', ''),
                'author': feed.feed.get('author', 'Unknown')
            }
        except Exception as e:
            logger.error(f"Error retrieving channel info: {e}")
            return 

    
        

    

    
