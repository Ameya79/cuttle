# Extreme Edge-Case Testing Rigor

All engine components, adapters, parsers, and runners in Cuttle must undergo rigorous stress and edge-case testing:

1. **Corrupt & Degraded Inputs**:
   - Zero-byte files (`0` bytes).
   - Truncated files (partial headers, truncated streams at 10%, 30%, 90%).
   - Wrong extensions (e.g., PNG named `.jpg`, MP4 named `.png`).
   - Garbage/random binary payloads.
2. **Filesystem & Path Hostility**:
   - Non-English Unicode names (e.g. `वीडियो नमूना.mp4`, Japanese, emojis).
   - Shell-breaking punctuation and spaces (e.g. `a & b (final) v2.mp4`, quotes, semicolons).
   - Paths exceeding Windows `MAX_PATH` (260+ characters).
3. **Concurrency & Locking**:
   - Files locked exclusively by other processes.
   - Rapid cancellation tokens fired before, during, and after processing.
   - Resource cleanup: No `.cuttle-part` or intermediate files left behind on errors or cancellations.
4. **Source Immutability**:
   - Source file SHA-256 must be verified unchanged before and after every test.
