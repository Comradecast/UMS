"""
BracketRenderService - Renders tournament brackets as images.

Uses Pillow to generate PNG images of bracket visualizations.
Designed for mobile-friendly display with high contrast on dark backgrounds.
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.bracket_snapshot import BracketSnapshot

log = logging.getLogger(__name__)

# Try to import Pillow, handle gracefully if not available
try:
    from PIL import Image, ImageDraw, ImageFont

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    log.warning(
        "Pillow not installed - bracket image rendering will be disabled. "
        "Install with: pip install Pillow>=10.0.0"
    )


# Color scheme (dark theme, mobile-friendly)
COLORS = {
    "background": (26, 26, 46),  # #1a1a2e - dark blue-gray
    "text": (238, 238, 238),  # #eeeeee - light gray
    "text_dim": (150, 150, 150),  # dimmed text for TBD/BYE
    "match_bg": (30, 30, 60),  # match box background
    "match_border_pending": (255, 193, 7),  # yellow - pending
    "match_border_completed": (40, 167, 69),  # green - completed
    "match_border_bye": (100, 100, 100),  # gray - bye
    "winner_highlight": (76, 175, 80),  # green highlight for winner
    "connector": (80, 80, 120),  # bracket connector lines
    "header_bg": (45, 45, 80),  # header background
}

# Layout constants
MATCH_WIDTH = 200
MATCH_HEIGHT = 60
MATCH_PADDING = 15
ROUND_GAP = 40
VERTICAL_GAP = 20
HEADER_HEIGHT = 60  # taller header so title + winner text aren't crammed
MARGIN = 24  # slightly more edge padding
TOP_PADDING = 16
BOTTOM_PADDING = 32
FONT_SIZE_LARGE = 18
FONT_SIZE_MEDIUM = 14
FONT_SIZE_SMALL = 12


class BracketRenderService:
    """Renders tournament brackets as images using Pillow."""

    def __init__(self):
        self._font_large = None
        self._font_medium = None
        self._font_small = None
        self._fonts_loaded = False

    def _load_fonts(self):
        if self._fonts_loaded or not PILLOW_AVAILABLE:
            return

        try:
            # Use a real Windows font with full Unicode support
            font_path = "C:/Windows/Fonts/segoeui.ttf"

            self._font_large = ImageFont.truetype(font_path, FONT_SIZE_LARGE)
            self._font_medium = ImageFont.truetype(font_path, FONT_SIZE_MEDIUM)
            self._font_small = ImageFont.truetype(font_path, FONT_SIZE_SMALL)

        except Exception as e:
            log.warning(f"Could not load segoeui.ttf fallback: {e}")

            # LAST RESORT fallback (bitmap font)
            self._font_large = ImageFont.load_default()
            self._font_medium = ImageFont.load_default()
            self._font_small = ImageFont.load_default()

        self._fonts_loaded = True

    def render_bracket(self, snapshot: "BracketSnapshot") -> bytes | None:
        """
        Generate PNG image of the bracket.

        Args:
            snapshot: BracketSnapshot containing all match data

        Returns:
            PNG image bytes, or None if rendering failed
        """
        if not PILLOW_AVAILABLE:
            log.warning("Cannot render bracket: Pillow not available")
            return None

        try:
            self._load_fonts()
            return self._render_single_elimination(snapshot)
        except Exception as e:
            log.error(f"Failed to render bracket: {e}", exc_info=True)
            return None

    def _render_single_elimination(self, snapshot: "BracketSnapshot") -> bytes:
        """Render a single elimination bracket."""
        # Calculate image dimensions
        num_rounds = snapshot.total_rounds
        if num_rounds == 0:
            num_rounds = 1

        # Width: rounds * (match_width + gap) + margins
        img_width = MARGIN * 2 + num_rounds * MATCH_WIDTH + (num_rounds - 1) * ROUND_GAP

        # Height: header + spacing + match layout + bottom padding
        first_round = snapshot.matches_by_round.get(1, [])
        num_matches_r1 = max(len(first_round), 1)

        img_height = (
            TOP_PADDING
            + HEADER_HEIGHT
            + MARGIN
            + num_matches_r1 * MATCH_HEIGHT
            + (num_matches_r1 - 1) * VERTICAL_GAP
            + BOTTOM_PADDING
        )

        # Ensure minimum dimensions
        img_width = max(img_width, 400)
        img_height = max(img_height, 300)

        # Create image
        img = Image.new("RGB", (img_width, img_height), COLORS["background"])
        draw = ImageDraw.Draw(img)

        # Draw header
        self._draw_header(draw, snapshot, img_width)

        # Draw matches by round
        for round_num in range(1, num_rounds + 1):
            matches = snapshot.matches_by_round.get(round_num, [])
            self._draw_round(draw, round_num, matches, num_rounds, img_height)

        # Draw connectors between rounds
        self._draw_connectors(draw, snapshot, img_height)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer.getvalue()

    def _draw_header(self, draw, snapshot, img_width):
        """Draw the tournament header cleanly with no duplication."""

        header_top = TOP_PADDING
        header_bottom = TOP_PADDING + HEADER_HEIGHT

        # Background
        draw.rectangle(
            [(0, header_top), (img_width, header_bottom)],
            fill=COLORS["header_bg"],
        )

        # Title
        title = f"🏆 {snapshot.tournament_name}"
        if snapshot.winner_name:
            title += f" – Winner: {snapshot.winner_name}"

        font = self._font_large or ImageFont.load_default()

        # Vertically center the title inside the header rectangle
        text_y = header_top + 8
        draw.text((MARGIN, text_y), title, fill=COLORS["text"], font=font)

        # Subtitle
        subtitle = f"{snapshot.format} • {snapshot.participant_count} players"
        small_font = self._font_small or ImageFont.load_default()

        subtitle_y = text_y + FONT_SIZE_LARGE + 6
        draw.text(
            (MARGIN, subtitle_y), subtitle, fill=COLORS["text_dim"], font=small_font
        )

    def _draw_round(
        self,
        draw: "ImageDraw.Draw",
        round_num: int,
        matches: list,
        total_rounds: int,
        img_height: int,
    ):
        """Draw all matches in a round."""
        if not matches:
            return

        x = MARGIN + (round_num - 1) * (MATCH_WIDTH + ROUND_GAP)

        # Vertical placement region
        top = TOP_PADDING + HEADER_HEIGHT + MARGIN
        bottom = img_height - BOTTOM_PADDING

        available = bottom - top
        count = len(matches)

        total_match_height = count * MATCH_HEIGHT
        total_gap = max(available - total_match_height, 0)
        gap = total_gap / (count + 1)

        for i, match in enumerate(matches):
            y = top + gap * (i + 1) + MATCH_HEIGHT * i
            self._draw_match(draw, match, x, int(y))

    def _draw_match(self, draw: "ImageDraw.Draw", match, x: int, y: int):
        """Draw a single match box."""
        from services.bracket_snapshot import BracketMatchSnapshot

        if not isinstance(match, BracketMatchSnapshot):
            return

        # Store render position for connectors / later use
        match._render_x = x
        match._render_y = y
        match._render_cx = x + MATCH_WIDTH  # right edge (where connectors attach)
        match._render_cy = y + MATCH_HEIGHT // 2  # vertical center

        # Determine border color based on status
        if match.status == "completed":
            border_color = COLORS["match_border_completed"]
        elif match.status == "bye":
            border_color = COLORS["match_border_bye"]
        else:
            border_color = COLORS["match_border_pending"]

        # Draw match box
        box_coords = [(x, y), (x + MATCH_WIDTH, y + MATCH_HEIGHT)]
        draw.rectangle(
            box_coords, fill=COLORS["match_bg"], outline=border_color, width=2
        )

        font = self._font_medium or ImageFont.load_default()
        small_font = self._font_small or ImageFont.load_default()

        # Player 1 line
        p1_name = match.player1_name or "TBD"
        p1_color = COLORS["text"] if match.player1_name else COLORS["text_dim"]

        # Highlight winner
        if match.winner_slot == 1:
            p1_name = f"🏆 {p1_name}"
            p1_color = COLORS["winner_highlight"]

        # Truncate long names
        if len(p1_name) > 18:
            p1_name = p1_name[:15] + "..."

        p1_score_str = ""
        if match.player1_score is not None:
            p1_score_str = f" ({match.player1_score})"

        draw.text((x + 8, y + 8), p1_name + p1_score_str, fill=p1_color, font=font)

        # Player 2 line
        p2_name = match.player2_name or "TBD"
        p2_color = COLORS["text"] if match.player2_name else COLORS["text_dim"]

        if match.winner_slot == 2:
            p2_name = f"🏆 {p2_name}"
            p2_color = COLORS["winner_highlight"]

        if len(p2_name) > 18:
            p2_name = p2_name[:15] + "..."

        p2_score_str = ""
        if match.player2_score is not None:
            p2_score_str = f" ({match.player2_score})"

        draw.text(
            (x + 8, y + MATCH_HEIGHT // 2 + 4),
            p2_name + p2_score_str,
            fill=p2_color,
            font=font,
        )

        # Match ID (small, in corner)
        match_id_str = f"M{match.match_id}"
        draw.text(
            (x + MATCH_WIDTH - 30, y + 4),
            match_id_str,
            fill=COLORS["text_dim"],
            font=small_font,
        )

    def _draw_connectors(self, draw, snapshot, img_height):
        """Draw visual bracket connector lines between rounds."""

        for round_num, matches in snapshot.matches_by_round.items():
            next_round = snapshot.matches_by_round.get(round_num + 1)
            if not next_round:
                continue

            x1 = MARGIN + (round_num - 1) * (MATCH_WIDTH + ROUND_GAP) + MATCH_WIDTH
            x2 = x1 + ROUND_GAP

            # Build map of next round match centers
            next_centers = []
            for nm in next_round:
                y_top = nm._render_y
                y_mid = y_top + MATCH_HEIGHT // 2
                next_centers.append(y_mid)

            for i, match in enumerate(matches):
                y_top = match._render_y
                y_mid = y_top + MATCH_HEIGHT // 2

                # Horizontal line from match edge
                draw.line((x1, y_mid, x2, y_mid), fill=COLORS["connector"], width=2)

                # Vertical drop to destination match center
                dest = next_centers[i // 2]  # parent match index
                draw.line(
                    (x2, min(y_mid, dest), x2, max(y_mid, dest)),
                    fill=COLORS["connector"],
                    width=2,
                )


# Singleton instance
_instance: BracketRenderService | None = None


def get_bracket_render_service() -> BracketRenderService:
    """Get the singleton BracketRenderService instance."""
    global _instance
    if _instance is None:
        _instance = BracketRenderService()
    return _instance
