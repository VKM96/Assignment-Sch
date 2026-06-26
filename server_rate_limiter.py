"""
rate_limiter.py - Rate limiting strategies for server

This module implements rate limiting using a strategy pattern, allowing
easy swapping between different algorithms (fixed window, token bucket, sliding window).

Key components:
- RateLimitStrategy: Base class for all rate limiting strategies
- FixedWindowCounter: Fixed window counter implementation (current default)
- RateLimiter: Wrapper class that delegates to a specific strategy

Usage:
- Import and instantiate in server.py:
  from rate_limiter import RateLimiter, FixedWindowCounter
  rate_limiter = RateLimiter(FixedWindowCounter(max_messages=5, window_seconds=10))
  
- Use in data handler:
  if not rate_limiter.is_allowed(client_key):
      # handle rate limit exceeded

Future strategies can be added by creating a new class that inherits from
RateLimitStrategy and implements is_allowed(). Then swap by changing the
strategy passed to RateLimiter.

TODO:
- Implement TokenBucket strategy
- Implement SlidingWindow strategy
- Add optional client cleanup for very long-running servers

"""

import time


class RateLimitStrategy:
    """
    Base class for rate limiting strategies.
    
    All rate limiting implementations should inherit from this class
    and implement the is_allowed() method.
    """
    
    def is_allowed(self, client_key: str) -> bool:
        """
        Check if a client is allowed to send a message.
        
        Args:
            client_key (str): Unique identifier for the client (e.g., "127.0.0.1:65432")
        
        Returns:
            bool: True if message is allowed, False if rate limit exceeded.
        """
        raise NotImplementedError("Subclasses must implement is_allowed()")


class FixedWindowCounter(RateLimitStrategy):
    """
    Fixed window counter rate limiting strategy.
    
    Time is divided into fixed-size windows. Each window tracks message count
    per client. When the window boundary is crossed, the counter resets.
    
    Pros:
    - Simple implementation
    - Low memory overhead (one entry per active client)
    - Fast O(1) per-check performance
    - Minimal CPU cost
    
    Cons:
    - Can allow up to 2x max_messages at window boundaries
      (e.g., 5 msgs at end of window + 5 msgs at start of next window = 10 in 11 seconds)
    - Less precise than sliding window algorithms
    
    Example:
    - max_messages=5, window_seconds=10
    - Client can send at most 5 messages per any fixed 10-second window
    - After 10 seconds, counter resets and allows 5 more messages
    """
    
    def __init__(self, max_messages: int, window_seconds: int):
        """
        Initialize the fixed window counter.
        
        Args:
            max_messages (int): Maximum messages allowed per window (e.g., 5)
            window_seconds (int): Duration of each window in seconds (e.g., 10)
        """
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        # clients: {client_key: (message_count, window_start_time)}
        self.clients = {}
    
    def is_allowed(self, client_key: str) -> bool:
        """
        Check if client is allowed to send a message.
        
        If the client is in a new time window, the counter resets.
        If the client has not exceeded the limit in the current window, increment and allow.
        Otherwise, reject.
        
        Args:
            client_key (str): Unique identifier for the client
        
        Returns:
            bool: True if allowed, False if rate limit exceeded
        """
        current_time = time.time()
        current_window = int(current_time // self.window_seconds)
        
        if client_key not in self.clients:
            # New client, initialize with count=1 (this message is allowed)
            self.clients[client_key] = (1, current_window)
            return True
        
        msg_count, window_start = self.clients[client_key]
        
        if window_start == current_window:
            # Same window: check if we've exceeded the limit
            if msg_count >= self.max_messages:
                # Limit exceeded, reject this message
                return False
            # Increment count and allow
            self.clients[client_key] = (msg_count + 1, window_start)
            return True
        else:
            # New window: reset counter to 1 (this message is allowed)
            self.clients[client_key] = (1, current_window)
            return True


class RateLimiter:
    """
    Wrapper class for rate limiting strategies.
    
    Delegates rate limit checks to a specific strategy implementation.
    Allows easy swapping between different algorithms without changing
    client code.
    
    Example:
        # Use fixed window counter
        limiter = RateLimiter(FixedWindowCounter(max_messages=5, window_seconds=10))
        
        # Later, swap to token bucket (when implemented)
        limiter = RateLimiter(TokenBucket(max_tokens=5, refill_rate=0.5))
        
        # Usage stays the same
        if not limiter.is_allowed("192.168.1.1:12345"):
            # Handle rate limit exceeded
    """
    
    def __init__(self, strategy: RateLimitStrategy):
        """
        Initialize the rate limiter with a specific strategy.
        
        Args:
            strategy (RateLimitStrategy): The rate limiting strategy to use
        """
        self.strategy = strategy
    
    def is_allowed(self, client_key: str) -> bool:
        """
        Check if client is allowed to send a message.
        
        Delegates to the underlying strategy's is_allowed() method.
        
        Args:
            client_key (str): Unique identifier for the client
        
        Returns:
            bool: True if allowed, False if rate limit exceeded
        """
        return self.strategy.is_allowed(client_key)
