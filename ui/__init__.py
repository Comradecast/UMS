"""
ui/ — Discord UI components for UMS Bot Core
=============================================
Contains:
- View and Modal classes
- Embed builder functions
- No database access or business logic
"""

# Match card components
from ui.match_views import (
    MatchCardView,
    WinnerButton,
    OverrideButton,
    CompletedMatchView,
)

# Match modals
from ui.match_modals import (
    MatchOverrideModal,
    ReportResultModal,
)

# Tournament dashboard and admin panel
from ui.tournament_views import (
    DashboardView,
    AdminControlPanel,
    DeleteTournamentConfirmView,
    CreateTournamentModal,
)

# Tournament embeds
from ui.tournament_embeds import (
    build_dashboard_embed,
)

# Registration components (TournamentService flow)
from ui.registration_views import (
    Registration1v1View,
    Registration2v2View,
    TeamRegistrationModal,
    # Legacy registration components
    RegisterButton,
    UnregisterButton,
    RefreshButton,
    RegionMismatchView,
    ManualRegisterModal,
    KickPlayerModal,
    AddDummiesModal,
    RegistrationView,
    EditTournamentModal,
    AdminControlsView,
)

# Registration embeds
from ui.registration_embeds import (
    build_public_registration_embed,
    build_admin_registration_embed,
    build_region_mismatch_embed,
)

# Bracket components
from ui.bracket_views import (
    ScoreModal,
    ScoreSubmissionView,
    ScoreVerificationView,
)

# Bracket embeds
from ui.bracket_embeds import (
    build_bracket_embed,
    build_score_submit_embed,
    build_verification_embed,
    build_standings_embed,
)

__all__ = [
    # Match card views
    "MatchCardView",
    "WinnerButton",
    "OverrideButton",
    "CompletedMatchView",
    # Match modals
    "MatchOverrideModal",
    "ReportResultModal",
    # Tournament views
    "DashboardView",
    "AdminControlPanel",
    "DeleteTournamentConfirmView",
    "CreateTournamentModal",
    # Tournament embeds
    "build_dashboard_embed",
    # Registration views (TournamentService flow)
    "Registration1v1View",
    "Registration2v2View",
    "TeamRegistrationModal",
    # Registration views (Legacy RegistrationCog flow)
    "RegisterButton",
    "UnregisterButton",
    "RefreshButton",
    "RegionMismatchView",
    "ManualRegisterModal",
    "KickPlayerModal",
    "AddDummiesModal",
    "RegistrationView",
    "EditTournamentModal",
    "AdminControlsView",
    # Registration embeds
    "build_public_registration_embed",
    "build_admin_registration_embed",
    "build_region_mismatch_embed",
    # Bracket views
    "ScoreModal",
    "ScoreSubmissionView",
    "ScoreVerificationView",
    # Bracket embeds
    "build_bracket_embed",
    "build_score_submit_embed",
    "build_verification_embed",
    "build_standings_embed",
]
