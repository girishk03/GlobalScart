# Re-export transactional lifecycle tests under a discoverable filename.
# Interviewers/reviewers often look for tests/test_orders.py first.

from test_checkout_lifecycle import *  # noqa: F401,F403
