ESSENTIAL = "essential"
NON_ESSENTIAL = "non_essential"


def classify_attribute(is_core: bool, active_binding_count: int) -> str:
    if is_core or active_binding_count > 0:
        return ESSENTIAL
    return NON_ESSENTIAL
