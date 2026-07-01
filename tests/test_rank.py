from reports.rank import rank

def test_cost_overlay_default_and_weighted():
    groups = {"a": {"signature": ("phantom_action", "dispute_charge", "file_dispute", "txn_not_found", "filed"),
                    "members": [1, 2]},
              "b": {"signature": ("ungrounded", "policy_question", "policy_search", "low_score", "60 days"),
                    "members": [1, 2, 3, 4]}}
    default = rank(groups)
    assert default[0]["signature"][0] == "ungrounded"          # 4×3=12 > 2×5=10
    weighted = rank(groups, cost_weights={"phantom_action": 3.0})
    assert weighted[0]["signature"][0] == "phantom_action"     # 2×5×3=30
