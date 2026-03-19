"""
Project Nobi — Privacy Configuration (Phase C)

All privacy parameters are centralized here for easy auditing and tuning.
"""

PRIVACY_CONFIG = {
    # Differential privacy parameters
    "epsilon": 1.0,                    # Privacy parameter (lower = more private, noisier)
    "delta": 1e-5,                     # Probability of privacy breach (for (ε,δ)-DP)
    "noise_mechanism": "gaussian",     # gaussian | laplace

    # Sensitivity / clipping
    "max_signal_norm": 1.0,            # Clip signals to this norm (bounded sensitivity)
    "adapter_weight_clip": 0.1,        # Max change per federated round

    # Aggregation
    "min_aggregation_size": 5,         # Minimum signals for k-anonymity
    "federated_round_interval": 100,   # Steps between aggregation rounds

    # Privacy budget
    "privacy_budget_total": 10.0,      # Total ε budget before refusing queries

    # Audit
    "audit_log_path": "/root/.nobi/privacy_audit.log",

    # Preference signal categories
    "topic_categories": [
        "general", "tech", "health", "finance", "education",
        "entertainment", "lifestyle", "science", "creative", "other",
    ],

    # Salt for user ID hashing (rotated periodically)
    "user_id_salt": "nobi-phase-c-privacy-salt-v1",
}
