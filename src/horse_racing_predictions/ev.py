def is_value_candidate(prediction, min_ev, min_probability, min_confidence):
    if prediction.predicted_win_probability < min_probability:
        return False, "probability_below_threshold"
    if prediction.confidence < min_confidence:
        return False, "confidence_below_threshold"
    if prediction.expected_return_multiple < min_ev:
        return False, "ev_below_threshold"
    return True, "eligible"
