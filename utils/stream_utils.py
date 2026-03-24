"""
Streaming utilities with retry logic.

Wraps client.messages.stream() to handle mid-stream connection drops
(httpx.ReadError, APIConnectionError) with exponential backoff.
"""
import time
import httpx
import anthropic


MAX_RETRIES = 3
BASE_DELAY = 5.0   # seconds before first retry


def stream_with_retry(client, show_progress: bool = True, **api_kwargs) -> str:
    """
    Call client.messages.stream(**api_kwargs), stream text to stdout,
    and return the full response text.

    Retries up to MAX_RETRIES times on connection errors (ReadError,
    APIConnectionError). Raises on the final failure or non-retriable errors.

    Args:
        client:        An AnthropicFoundry (or Anthropic) client instance.
        show_progress: If True, print tokens to stdout as they arrive.
        **api_kwargs:  Passed directly to client.messages.stream()
                       (model, max_tokens, system, messages, …).

    Returns:
        The complete response text as a string.
    """
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if show_progress:
                print()

            with client.messages.stream(**api_kwargs) as stream:
                if show_progress:
                    for text in stream.text_stream:
                        print(text, end="", flush=True)
                else:
                    # dot-progress (used by interrogator for JSON output)
                    char_count = 0
                    for text in stream.text_stream:
                        char_count += len(text)
                        if char_count % 200 < len(text):
                            print(".", end="", flush=True)

                response = stream.get_final_message()

            if show_progress:
                print()

            return response.content[0].text

        except (httpx.ReadError, anthropic.APIConnectionError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** (attempt - 1))  # 5s, 10s, 20s
                print(
                    f"\n  [Connection dropped] Attempt {attempt}/{MAX_RETRIES} failed. "
                    f"Retrying in {delay:.0f}s…",
                    flush=True,
                )
                time.sleep(delay)
            else:
                print(
                    f"\n  [Connection dropped] All {MAX_RETRIES} attempts failed.",
                    flush=True,
                )

    raise last_exc
