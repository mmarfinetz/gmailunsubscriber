"""
Gmail Unsubscriber - Claude Chat Integration with Prompt Caching

This module provides Claude AI integration with efficient prompt caching
for the Gmail Unsubscriber project. The CLAUDE.md prompt is cached to reduce
costs and improve response times.
"""

import os
import pathlib
import logging
from typing import List, Dict, Any, Optional
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class ClaudeChatManager:
    """Manages Claude AI interactions with efficient prompt caching."""
    
    def __init__(self):
        """Initialize Claude client and load cached prompt."""
        self.client = anthropic.Anthropic(
            api_key=os.environ.get('ANTHROPIC_API_KEY')
        )
        
        # Load the project prompt from CLAUDE.md
        claude_md_path = pathlib.Path(__file__).parent.parent / "CLAUDE.md"
        if not claude_md_path.exists():
            raise FileNotFoundError(f"CLAUDE.md not found at {claude_md_path}")
        
        self.claude_prompt = claude_md_path.read_text(encoding='utf-8')
        logger.info(f"Loaded CLAUDE.md ({len(self.claude_prompt)} characters)")
        
    def ask_claude(
        self, 
        message: str, 
        history: Optional[List[Dict[str, Any]]] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
        cache_type: str = "ephemeral"
    ) -> anthropic.types.Message:
        """
        Send a message to Claude with the cached project prompt.
        
        Args:
            message: User message to send
            history: Optional conversation history (list of message dicts)
            model: Claude model to use (must support caching)
            max_tokens: Maximum tokens in response
            cache_type: Cache type ("ephemeral" for 5min, "persistent" for 60min)
            
        Returns:
            Anthropic message response object
            
        Raises:
            anthropic.APIError: If API call fails
            ValueError: If required environment variables are missing
        """
        if not self.client.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        try:
            # Prepare system prompt with caching
            system_messages = [
                {
                    "type": "text",
                    "text": self.claude_prompt,
                    "cache_control": {"type": cache_type}
                }
            ]
            
            # Prepare conversation messages
            messages = []
            
            # Add conversation history if provided
            if history:
                messages.extend(history)
                
                # Cache the last assistant response if available
                if (history and 
                    history[-1].get("role") == "assistant" and
                    len(history) > 1):
                    
                    # Add cache control to the last assistant message
                    last_msg = messages[-1].copy()
                    last_msg["cache_control"] = {"type": cache_type}
                    messages[-1] = last_msg
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Make API call with caching
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_messages,
                messages=messages
            )
            
            # Log cache usage for monitoring
            usage = response.usage
            logger.info(
                f"Claude API call - Input: {usage.input_tokens}, "
                f"Output: {usage.output_tokens}, "
                f"Cache Read: {getattr(usage, 'cache_read_input_tokens', 0)}, "
                f"Cache Write: {getattr(usage, 'cache_creation_input_tokens', 0)}"
            )
            
            return response
            
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Claude chat: {e}")
            raise
    
    def chat_simple(self, message: str) -> str:
        """
        Simple chat interface that returns just the text response.
        
        Args:
            message: User message
            
        Returns:
            Claude's text response
        """
        try:
            response = self.ask_claude(message)
            return response.content[0].text if response.content else ""
        except Exception as e:
            logger.error(f"Error in simple chat: {e}")
            return f"Error: {str(e)}"
    
    def chat_with_context(
        self, 
        message: str, 
        gmail_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Chat with Gmail Unsubscriber specific context.
        
        Args:
            message: User message
            gmail_context: Context about current Gmail processing
            user_context: Context about the user's session
            
        Returns:
            Claude's response text
        """
        # Build context-aware message
        context_parts = [message]
        
        if gmail_context:
            context_parts.append(f"\nGmail Context: {gmail_context}")
            
        if user_context:
            context_parts.append(f"\nUser Context: {user_context}")
        
        full_message = "\n".join(context_parts)
        
        return self.chat_simple(full_message)

# Global instance for use across the application
chat_manager = ClaudeChatManager()

# Convenience functions for easy import
def ask_claude(message: str, history: Optional[List[Dict[str, Any]]] = None) -> anthropic.types.Message:
    """Convenience function to ask Claude with caching."""
    return chat_manager.ask_claude(message, history)

def chat_simple(message: str) -> str:
    """Convenience function for simple text chat."""
    return chat_manager.chat_simple(message)

def chat_with_gmail_context(
    message: str, 
    gmail_context: Optional[Dict[str, Any]] = None,
    user_context: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function for Gmail-context aware chat."""
    return chat_manager.chat_with_context(message, gmail_context, user_context) 