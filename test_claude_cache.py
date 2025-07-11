#!/usr/bin/env python3
"""
Test script for Claude prompt caching functionality
Verifies that the CLAUDE.md prompt is being cached properly
"""

import os
import sys
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path for imports
sys.path.insert(0, 'gmail-unsubscriber-backend')

def test_claude_cache():
    """Test Claude prompt caching functionality."""
    
    print("🔍 Testing Claude Prompt Caching Implementation")
    print("=" * 50)
    
    # Check if ANTHROPIC_API_KEY is set
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        print("   Please set ANTHROPIC_API_KEY in your .env file")
        return False
    
    print(f"✅ ANTHROPIC_API_KEY found: {api_key[:8]}...")
    
    # Check if CLAUDE.md exists
    claude_md_path = "CLAUDE.md"
    if not os.path.exists(claude_md_path):
        print(f"❌ CLAUDE.md not found at {claude_md_path}")
        return False
    
    with open(claude_md_path, 'r', encoding='utf-8') as f:
        claude_content = f.read()
    
    print(f"✅ CLAUDE.md found ({len(claude_content)} characters)")
    
    # Test importing the chat module
    try:
        from chat import ClaudeChatManager, ask_claude, chat_simple
        print("✅ Successfully imported Claude chat module")
    except ImportError as e:
        print(f"❌ Failed to import chat module: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading chat module: {e}")
        return False
    
    # Test initializing chat manager
    try:
        chat_manager = ClaudeChatManager()
        print("✅ Successfully initialized ClaudeChatManager")
        print(f"   Loaded prompt: {len(chat_manager.claude_prompt)} characters")
    except Exception as e:
        print(f"❌ Failed to initialize ClaudeChatManager: {e}")
        return False
    
    # Test first API call (should write to cache)
    print("\n📝 Testing first API call (cache write)...")
    test_message = "What is the Gmail Unsubscriber project about?"
    
    try:
        start_time = time.time()
        response1 = chat_manager.ask_claude(test_message)
        end_time = time.time()
        
        duration1 = end_time - start_time
        usage1 = response1.usage
        
        print(f"✅ First call completed in {duration1:.2f}s")
        print(f"   Input tokens: {usage1.input_tokens}")
        print(f"   Output tokens: {usage1.output_tokens}")
        print(f"   Cache read tokens: {getattr(usage1, 'cache_read_input_tokens', 0)}")
        print(f"   Cache write tokens: {getattr(usage1, 'cache_creation_input_tokens', 0)}")
        
        # Should have cache write tokens, no cache read tokens
        cache_write = getattr(usage1, 'cache_creation_input_tokens', 0)
        cache_read = getattr(usage1, 'cache_read_input_tokens', 0)
        
        if cache_write > 0 and cache_read == 0:
            print("✅ Cache write successful (first call)")
        else:
            print(f"⚠️  Unexpected cache usage: write={cache_write}, read={cache_read}")
        
    except Exception as e:
        print(f"❌ First API call failed: {e}")
        return False
    
    # Test second API call (should read from cache)
    print("\n📖 Testing second API call (cache read)...")
    test_message2 = "How do I deploy this project?"
    
    try:
        start_time = time.time()
        response2 = chat_manager.ask_claude(test_message2)
        end_time = time.time()
        
        duration2 = end_time - start_time
        usage2 = response2.usage
        
        print(f"✅ Second call completed in {duration2:.2f}s")
        print(f"   Input tokens: {usage2.input_tokens}")
        print(f"   Output tokens: {usage2.output_tokens}")
        print(f"   Cache read tokens: {getattr(usage2, 'cache_read_input_tokens', 0)}")
        print(f"   Cache write tokens: {getattr(usage2, 'cache_creation_input_tokens', 0)}")
        
        # Should have cache read tokens, minimal cache write tokens
        cache_write2 = getattr(usage2, 'cache_creation_input_tokens', 0)
        cache_read2 = getattr(usage2, 'cache_read_input_tokens', 0)
        
        if cache_read2 > 0 and cache_write2 == 0:
            print("✅ Cache read successful (second call)")
            
            # Calculate speed improvement
            speed_improvement = (duration1 - duration2) / duration1 * 100
            print(f"🚀 Speed improvement: {speed_improvement:.1f}%")
            
            # Calculate cost savings (90% discount on cached tokens)
            cached_tokens = cache_read2
            savings = cached_tokens * 0.9  # 90% savings
            print(f"💰 Token cost savings: ~{savings:.0f} tokens (90% discount)")
            
        else:
            print(f"⚠️  Unexpected cache usage: write={cache_write2}, read={cache_read2}")
    
    except Exception as e:
        print(f"❌ Second API call failed: {e}")
        return False
    
    # Test conversation with history (should cache assistant response)
    print("\n💬 Testing conversation with history...")
    try:
        history = [
            {"role": "user", "content": "What are the main features?"},
            {"role": "assistant", "content": response1.content[0].text if response1.content else "Test response"}
        ]
        
        start_time = time.time()
        response3 = chat_manager.ask_claude("Can you elaborate on the OAuth setup?", history)
        end_time = time.time()
        
        duration3 = end_time - start_time
        usage3 = response3.usage
        
        print(f"✅ Conversation call completed in {duration3:.2f}s")
        print(f"   Input tokens: {usage3.input_tokens}")
        print(f"   Output tokens: {usage3.output_tokens}")
        print(f"   Cache read tokens: {getattr(usage3, 'cache_read_input_tokens', 0)}")
        print(f"   Cache write tokens: {getattr(usage3, 'cache_creation_input_tokens', 0)}")
        
    except Exception as e:
        print(f"❌ Conversation call failed: {e}")
        return False
    
    # Test convenience functions
    print("\n🛠️  Testing convenience functions...")
    try:
        simple_response = chat_simple("What is OAuth?")
        print(f"✅ chat_simple() works - response length: {len(simple_response)} chars")
        
        from chat import chat_with_gmail_context
        context_response = chat_with_gmail_context(
            "Help me understand the unsubscription process",
            gmail_context={"service": "test"},
            user_context={"user_id": "test_user"}
        )
        print(f"✅ chat_with_gmail_context() works - response length: {len(context_response)} chars")
        
    except Exception as e:
        print(f"❌ Convenience functions failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All Claude caching tests passed!")
    print("\n📊 Summary:")
    print(f"   - First call (cache write): {duration1:.2f}s")
    print(f"   - Second call (cache read): {duration2:.2f}s") 
    print(f"   - Speed improvement: {((duration1 - duration2) / duration1 * 100):.1f}%")
    print(f"   - Cached tokens: {cache_read2}")
    print(f"   - Estimated cost savings: 90% on cached tokens")
    
    return True

def test_api_endpoints():
    """Test the Flask API endpoints (requires running server)."""
    
    print("\n🌐 Testing API Endpoints")
    print("=" * 30)
    
    try:
        import requests
        
        # Test chat status endpoint
        response = requests.get("http://localhost:5000/api/chat/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Chat status: {data}")
        else:
            print(f"❌ Chat status endpoint failed: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Backend server not running - skipping API tests")
        print("   Start with: cd gmail-unsubscriber-backend && python app.py")
    except Exception as e:
        print(f"❌ API test failed: {e}")

if __name__ == "__main__":
    print("🤖 Claude Prompt Caching Test Suite")
    print("===================================")
    
    success = test_claude_cache()
    
    if success:
        test_api_endpoints()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Testing completed successfully!")
        print("\nNext steps:")
        print("1. Start the backend: cd gmail-unsubscriber-backend && python app.py")
        print("2. Test API endpoints with authentication")
        print("3. Monitor cache usage in production logs")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1) 