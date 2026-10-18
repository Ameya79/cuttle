# Plain-Language Architecture & Explanations

When communicating architectural decisions, system workflows, and task progress:

1. **Intuitive Mental Models First**:
   - Begin with a relatable real-world analogy (e.g. car engine vs. dashboard, kitchen chef vs. waitstaff, postal system).
   - Ground the explanation in the end-user's direct experience (what happens when they double-click, right-click, or click cancel).

2. **Jargon-Free Architecture Summaries**:
   - Translate low-level terms into intuitive equivalents before using technical labels:
     - Named Pipe -> "A direct, 5-millisecond phone line between the right-click menu and the background app"
     - Windows Job Object -> "A master safety switch that guarantees no orphan conversion processes freeze the computer"
     - SQLite state DB -> "The logbook that remembers what was converted and cleans up after crashes"
     - PyInstaller onedir -> "Freezing the app and its engine into a single self-contained folder that runs on any PC without installing Python"

3. **User Journey Flow**:
   - When explaining workflows, trace the path from the user's click in Windows Explorer to the final toast notification.
